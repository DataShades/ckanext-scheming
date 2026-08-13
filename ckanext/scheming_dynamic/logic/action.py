from __future__ import annotations

from typing import Any

import ckan.plugins.toolkit as tk
from ckan.logic import validate

from ckanext.scheming_dynamic.logic import schema
from ckanext.scheming_dynamic.model import SchemingPreset, SchemingSchema
from ckanext.scheming_dynamic.preset_resolve import (
    PresetBaseNotFoundError,
    PresetCycleError,
)
from ckanext.scheming_dynamic.render import render_preset_field, render_schema_form

TYPE_FIELDS = {
    "dataset": "dataset_type",
    "group": "group_type",
    "organization": "organization_type",
}


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

    schema_type = definition[TYPE_FIELDS[entity_type]]

    if SchemingSchema.get(entity_type, schema_type):
        raise tk.ValidationError(
            {"schema_type": [tk._(f"Schema for '{schema_type}' already exists")]}
        )

    _check_schema_renders(schema_type, definition)

    row = SchemingSchema.create(entity_type, schema_type, definition)

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

    schema = SchemingSchema.get(entity_type, schema_type)
    if not schema:
        raise tk.ObjectNotFound(tk._(f"Schema for '{schema_type}' not found"))

    type_field = TYPE_FIELDS[entity_type]
    if definition[type_field] != schema_type:
        raise tk.ValidationError(
            {
                "definition": [
                    tk._(f"'{type_field}' must match schema_type '{schema_type}'")
                ]
            }
        )

    _check_schema_renders(schema_type, definition)

    schema.update_definition(definition)

    return schema.as_dict()


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

    schema = SchemingSchema.get(entity_type, schema_type)
    if not schema:
        raise tk.ObjectNotFound(tk._(f"Schema for '{schema_type}' not found"))

    schema.delete()

    return True


def _check_schema_renders(schema_type: str, definition: dict[str, Any]) -> None:
    """Raise ValidationError if a dataset schema's form can't render.

    Mirrors the /preview check, so a schema broken the same way can't be
    saved through the create/update actions either.
    """
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
