from __future__ import annotations

import dataclasses
from typing import Any, cast

import ckan.plugins.toolkit as tk
from ckan import model, types
from ckan.lib import plugins as lib_plugins

from ckanext.scheming.plugins import _expand_schemas
from ckanext.scheming_dynamic.model import SchemingSchemaPin, SchemingSchemaVersion
from ckanext.scheming_dynamic.schema_migration.diff import (
    CONSTANT,
    COPY,
    DATASET_GROUP,
    DEFAULT,
    RESOURCE_GROUP,
)
from ckanext.scheming_dynamic.schema_migration.model import MigrationRunItem


@dataclasses.dataclass
class ItemResult:
    entity_id: str
    status: str
    errors: dict[str, Any] | None = None
    changes: dict[str, Any] | None = None


def expanded_definition(
    entity_type: str, schema_type: str, version: int
) -> dict[str, Any]:
    row = SchemingSchemaVersion.get(entity_type, schema_type, version)

    if row is None:
        raise tk.ObjectNotFound(
            tk._("Version {} of '{}' not found").format(version, schema_type)
        )

    return _expand_schemas({schema_type: row.definition})[schema_type]


def datasets_at_version(schema_type: str, version: int) -> list[str]:
    return [
        row[0]
        for row in model.Session.query(model.Package.id)
        .join(SchemingSchemaPin, SchemingSchemaPin.entity_id == model.Package.id)
        .filter(
            model.Package.type == schema_type,
            model.Package.state == model.State.ACTIVE,
            SchemingSchemaPin.entity_type == "dataset",
            SchemingSchemaPin.schema_type == schema_type,
            SchemingSchemaPin.version == version,
        )
        .all()
    ]


class Migrator:
    """Moves datasets of one schema type from one version to another."""

    entity_type = "dataset"

    def __init__(  # noqa: PLR0913
        self,
        schema_type: str,
        from_version: int,
        to_version: int,
        mapping: dict[str, Any],
        user: str,
        dry_run: bool = False,
    ):
        self.schema_type = schema_type
        self.from_version = from_version
        self.to_version = to_version
        self.mapping = mapping
        self.user = user
        self.dry_run = dry_run

        self.source_schema = expanded_definition(
            self.entity_type, schema_type, from_version
        )
        self.target_schema = expanded_definition(
            self.entity_type, schema_type, to_version
        )

    def run_one(self, entity_id: str) -> ItemResult:
        pin = SchemingSchemaPin.get(self.entity_type, entity_id)

        if pin is None or pin.version == self.to_version:
            return ItemResult(entity_id, MigrationRunItem.SKIPPED)

        if pin.version != self.from_version:
            return ItemResult(
                entity_id,
                MigrationRunItem.SKIPPED,
                errors={"pin": [f"pinned to version {pin.version}"]},
            )

        before = tk.get_action("package_show")(self._read_context(), {"id": entity_id})
        data = self._build(before)

        pin.version = self.to_version
        model.Session.flush()

        if self.dry_run:
            return self._validate_only(entity_id, data)

        try:
            after = tk.get_action("package_update")(self._context(), data)
        except tk.ValidationError as e:
            model.Session.rollback()
            return ItemResult(entity_id, MigrationRunItem.FAILED, errors=e.error_dict)

        return ItemResult(
            entity_id,
            MigrationRunItem.OK,
            changes=self._changes(before, after),
        )

    def _build(self, before: dict[str, Any]) -> dict[str, Any]:
        return build_target_data(
            before, self.mapping, self.source_schema, self.target_schema
        )

    def failure(self, entity_id: str, message: str) -> ItemResult:
        return ItemResult(
            entity_id, MigrationRunItem.FAILED, errors={"migration": [message]}
        )

    def _validate_only(self, entity_id: str, data: dict[str, Any]) -> ItemResult:
        """Run the target version's validators without writing anything."""
        plugin = lib_plugins.lookup_package_plugin(self.schema_type)

        if self.schema_type not in plugin.package_types():
            return self.failure(
                entity_id,
                f"'{self.schema_type}' is not registered with a scheming plugin, "
                "so it cannot be validated",
            )

        context = self._context()
        context["package"] = cast("model.Package", model.Package.get(entity_id))

        try:
            _, errors = lib_plugins.plugin_validate(
                plugin,
                context,
                data,
                plugin.update_package_schema(),
                "package_update",
            )
        finally:
            model.Session.rollback()

        if errors:
            return ItemResult(entity_id, MigrationRunItem.FAILED, errors=errors)

        return ItemResult(entity_id, MigrationRunItem.OK)

    def _changes(
        self, before: dict[str, Any], after: dict[str, Any]
    ) -> dict[str, Any] | None:
        dataset_names = self._tracked_names(DATASET_GROUP)
        resource_names = self._tracked_names(RESOURCE_GROUP)

        dataset = _changed_fields(before, after, dataset_names)
        after_resources = {r["id"]: r for r in after.get("resources", [])}
        resources = {}

        for resource in before.get("resources", []):
            changed = _changed_fields(
                resource, after_resources.get(resource["id"], {}), resource_names
            )
            if changed:
                resources[resource["id"]] = changed

        if not dataset and not resources:
            return None

        return {"dataset": dataset, "resources": resources}

    def _tracked_names(self, group: str) -> set[str]:
        return _field_names(self.source_schema, group) | _field_names(
            self.target_schema, group
        )

    def _context(self) -> types.Context:
        return types.Context(
            user=self.user,
            ignore_auth=True,
            session=model.Session,
        )

    def _read_context(self) -> types.Context:
        """Read the dataset the way the edit form does.

        Without ``for_edit`` an uploaded resource's ``url`` comes back fully
        qualified, and writing that back would replace the stored filename
        with an absolute URL.
        """
        context = self._context()
        context["for_edit"] = True
        return context


def build_target_data(
    before: dict[str, Any],
    mapping: dict[str, Any],
    source_schema: dict[str, Any],
    target_schema: dict[str, Any],
) -> dict[str, Any]:
    """The dataset as it should look under the target schema.

    Source-schema fields are stripped first, so a field the mapping does not
    carry over leaves no leftover extra behind.
    """
    data = _apply_group(before, DATASET_GROUP, mapping, source_schema, target_schema)

    data["resources"] = [
        _apply_group(resource, RESOURCE_GROUP, mapping, source_schema, target_schema)
        for resource in before.get("resources", [])
    ]

    return data


def _apply_group(
    source_data: dict[str, Any],
    group: str,
    mapping: dict[str, Any],
    source_schema: dict[str, Any],
    target_schema: dict[str, Any],
) -> dict[str, Any]:
    data = {
        key: value
        for key, value in source_data.items()
        if key not in _field_names(source_schema, group)
    }
    data.pop("resources", None)

    target_fields = {f["field_name"]: f for f in target_schema.get(group, [])}

    for field_name, entry in mapping.get(group, {}).items():
        target_field = target_fields.get(field_name)
        if target_field is None:
            continue

        value = _mapped_value(entry, source_data, target_field)
        if value is not None:
            data[field_name] = value

    return data


def _field_names(schema: dict[str, Any], group: str) -> set[str]:
    return {f["field_name"] for f in schema.get(group, [])}


def _changed_fields(
    before: dict[str, Any], after: dict[str, Any], names: set[str]
) -> dict[str, Any]:
    return {
        name: {"before": before.get(name), "after": after.get(name)}
        for name in names
        if before.get(name) != after.get(name)
    }


def _mapped_value(
    entry: dict[str, Any], source_data: dict[str, Any], target_field: dict[str, Any]
) -> Any:
    action = entry.get("action")

    if action == COPY:
        return _remap(source_data.get(entry["source"]), entry.get("value_map"))

    if action == CONSTANT:
        return entry.get("value")

    if action == DEFAULT:
        return target_field.get("default")

    return None


def _remap(value: Any, value_map: dict[str, Any] | None) -> Any:
    if not value_map:
        return value

    if isinstance(value, list):
        return [value_map.get(item, item) for item in value]

    return value_map.get(value, value)
