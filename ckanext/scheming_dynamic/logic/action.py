from __future__ import annotations

from contextlib import nullcontext
from typing import Any, cast

from click import get_current_context
from flask import has_app_context

import ckan.plugins.toolkit as tk
from ckan import model
from ckan.logic import validate

from ckanext.scheming_dynamic.logic import schema
from ckanext.scheming_dynamic.model import (
    SchemingPreset,
    SchemingSchemaActivity,
    SchemingSchemaPin,
    SchemingSchemaVersion,
    SchemingState,
)
from ckanext.scheming_dynamic.preset_resolve import (
    PresetBaseNotFoundError,
    PresetCycleError,
)
from ckanext.scheming_dynamic.render import render_preset_field, render_schema_form


@validate(schema.scheming_schema_create)
def scheming_schema_create(context: Any, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Create a dynamic schema.

    :param entity_type: the entity this schema applies to (default: ``dataset``)
    :type entity_type: string
    :param definition: the ckanext-scheming schema definition; the schema
        type is taken from its type field (e.g. ``dataset_type``)
    :type definition: dict
    """
    tk.check_access("scheming_schema_create", context, data_dict)

    entity_type = data_dict["entity_type"]
    definition = data_dict["definition"]

    schema_type = definition[schema.TYPE_FIELDS[entity_type]]

    if SchemingSchemaVersion.head_version(entity_type, schema_type):
        raise tk.ValidationError(
            {"schema_type": [tk._(f"Schema for '{schema_type}' already exists")]}
        )

    _check_schema_renders(schema_type, definition)

    # locked first: the activity row's FK needs version 1 to already exist
    row = SchemingSchemaVersion.lock(entity_type, schema_type, definition)
    SchemingSchemaActivity.record(
        entity_type,
        schema_type,
        SchemingSchemaActivity.CREATE,
        context["user"],
        definition,
        version=row.version,
    )
    SchemingState.bump(entity_type)
    model.Session.commit()

    return row.as_dict()


@validate(schema.scheming_schema_update)
def scheming_schema_update(context: Any, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Update a dynamic schema.

    :param schema_type: the schema type whose schema should be updated
    :type schema_type: string
    :param entity_type: the entity this schema applies to (default: ``dataset``)
    :type entity_type: string
    :param definition: the schema definition
    :type definition: dict
    """
    tk.check_access("scheming_schema_update", context, data_dict)

    entity_type = data_dict["entity_type"]
    schema_type = data_dict["schema_type"]
    definition = data_dict["definition"]

    if not SchemingSchemaVersion.head_version(entity_type, schema_type):
        raise tk.ObjectNotFound(tk._(f"Schema for '{schema_type}' not found"))

    type_field = schema.TYPE_FIELDS[entity_type]
    if definition[type_field] != schema_type:
        raise tk.ValidationError(
            {
                "definition": [
                    tk._(f"'{type_field}' must match schema_type '{schema_type}'")
                ]
            }
        )

    _check_schema_renders(schema_type, definition)

    row = _lock_or_sync_version(entity_type, schema_type, definition)

    SchemingSchemaActivity.record(
        entity_type,
        schema_type,
        SchemingSchemaActivity.UPDATE,
        context["user"],
        definition,
        version=row.version,
    )
    SchemingState.bump(entity_type)
    model.Session.commit()

    return row.as_dict()


def _lock_or_sync_version(
    entity_type: str, schema_type: str, definition: dict[str, Any]
) -> SchemingSchemaVersion:
    """Apply an edit to the schema's current (head) version.

    If the head version is already pinned by an entity, it can't be changed
    -- so this locks ``definition`` as a new version instead. Otherwise
    nothing depends on the head version yet, so it's safe to overwrite its
    definition directly.

    Returns the version row that now holds ``definition``.
    """
    head_version = SchemingSchemaVersion.head_version(entity_type, schema_type)

    if SchemingSchemaPin.is_version_locked(entity_type, schema_type, head_version):
        return SchemingSchemaVersion.lock(entity_type, schema_type, definition)

    existing = cast(
        SchemingSchemaVersion,
        SchemingSchemaVersion.get(entity_type, schema_type, head_version),
    )
    existing.definition = definition
    return existing


@validate(schema.scheming_schema_delete)
def scheming_schema_delete(context: Any, data_dict: dict[str, Any]) -> bool:
    """Delete a dynamic schema.

    :param schema_type: the schema type whose schema should be deleted
    :type schema_type: string
    :param entity_type: the entity this schema applies to (default: ``dataset``)
    :type entity_type: string
    """
    tk.check_access("scheming_schema_delete", context, data_dict)

    entity_type = data_dict["entity_type"]
    schema_type = data_dict["schema_type"]

    head = SchemingSchemaVersion.head(entity_type, schema_type)
    if not head:
        raise tk.ObjectNotFound(tk._(f"Schema for '{schema_type}' not found"))

    SchemingSchemaActivity.record(
        entity_type,
        schema_type,
        SchemingSchemaActivity.DELETE,
        context["user"],
        head.definition,
    )
    SchemingSchemaVersion.delete_all(entity_type, schema_type)
    SchemingState.bump(entity_type)
    model.Session.commit()

    return True


@validate(schema.scheming_schema_activity_list)
def scheming_schema_activity_list(
    context: Any, data_dict: dict[str, Any]
) -> list[dict[str, Any]]:
    """List a dynamic schema's activity history, oldest first.

    :param schema_type: the schema type whose history should be listed
    :type schema_type: string
    :param entity_type: the entity this schema applies to (default: ``dataset``)
    :type entity_type: string
    """
    tk.check_access("scheming_schema_activity_list", context, data_dict)

    entity_type = data_dict["entity_type"]
    schema_type = data_dict["schema_type"]

    return [
        row.as_dict()
        for row in SchemingSchemaActivity.get_history(entity_type, schema_type)
    ]


def _check_schema_renders(schema_type: str, definition: dict[str, Any]) -> None:
    """Raise ValidationError if a dataset schema's form can't render.

    Mirrors the /preview check, so a schema broken the same way can't be
    saved through the create/update actions either.
    """
    # TODO: this is a bit of a hack, but it's the only way to get the
    # render-check of a schema's form work for both CLI (e.g. ckanapi)
    # and web UI.
    if has_app_context():
        ctx = nullcontext()
    else:
        try:
            ctx = get_current_context().meta["flask_app"].test_request_context("/")
        except RuntimeError:
            return

    with ctx:
        try:
            render_schema_form(schema_type, definition)
        except Exception as e:  # noqa: BLE001
            raise tk.ValidationError(
                {"definition": [tk._("Schema cannot be rendered: {}").format(e)]}
            ) from e


def _check_preset_renders(preset_name: str, values: dict[str, Any]) -> None:
    """Raise ValidationError if a preset's field snippet can't render.

    Mirrors the /presets/preview check, so a preset broken the same way
    can't be saved through the create/update actions either.
    """
    try:
        render_preset_field(preset_name, values)
    except PresetCycleError as e:
        raise tk.ValidationError(
            {
                "definition": [
                    tk._("Preset cycle detected: {}").format(
                        " -> ".join([*e.chain, e.chain[0]])
                    )
                ]
            }
        ) from e
    except PresetBaseNotFoundError as e:
        raise tk.ValidationError(
            {
                "definition": [
                    tk._(
                        f"Base preset '{e.base}' is not a registered or existing preset"
                    )
                ]
            }
        ) from e
    except Exception as e:  # noqa: BLE001
        raise tk.ValidationError(
            {"definition": [tk._("Form snippet failed to render: {}").format(e)]}
        ) from e


@validate(schema.scheming_preset_create)
def scheming_preset_create(context: Any, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Create a field preset.

    :param definition: ``{"preset_name": ..., "values": {...}}``; the same
        attribute bag a dataset/resource field can take
    :type definition: dict
    """
    tk.check_access("scheming_preset_create", context, data_dict)

    definition = data_dict["definition"]
    preset_name = definition["preset_name"]

    if SchemingPreset.get(preset_name):
        raise tk.ValidationError(
            {"preset_name": [tk._(f"Preset '{preset_name}' already exists")]}
        )

    _check_preset_renders(preset_name, definition["values"])

    row = SchemingPreset.create(preset_name, definition["values"])

    return row.as_dict()


@validate(schema.scheming_preset_update)
def scheming_preset_update(context: Any, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Update a field preset.

    :param preset_name: the preset to update
    :type preset_name: string
    :param definition: ``{"preset_name": ..., "values": {...}}``
    :type definition: dict
    """
    tk.check_access("scheming_preset_update", context, data_dict)

    preset_name = data_dict["preset_name"]
    definition = data_dict["definition"]

    preset = SchemingPreset.get(preset_name)
    if not preset:
        raise tk.ObjectNotFound(tk._(f"Preset '{preset_name}' not found"))

    if definition["preset_name"] != preset_name:
        raise tk.ValidationError(
            {
                "definition": [
                    tk._(f"'preset_name' must match preset_name '{preset_name}'")
                ]
            }
        )

    _check_preset_renders(preset_name, definition["values"])

    preset.update_values(definition["values"])

    return preset.as_dict()


@validate(schema.scheming_preset_delete)
def scheming_preset_delete(context: Any, data_dict: dict[str, Any]) -> bool:
    """Delete a field preset.

    :param preset_name: the preset to delete
    :type preset_name: string
    """
    tk.check_access("scheming_preset_delete", context, data_dict)

    preset_name = data_dict["preset_name"]

    preset = SchemingPreset.get(preset_name)
    if not preset:
        raise tk.ObjectNotFound(tk._(f"Preset '{preset_name}' not found"))

    preset.delete()

    return True
