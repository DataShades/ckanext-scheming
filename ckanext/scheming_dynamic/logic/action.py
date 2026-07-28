from __future__ import annotations

from typing import Any

import ckan.plugins.toolkit as tk
from ckan.logic import validate

from ckanext.scheming_dynamic.logic import schema
from ckanext.scheming_dynamic.model import SchemingSchema
from ckanext.scheming_dynamic.schema import SCHEMA_TYPES
from ckanext.scheming_dynamic.validator import error_location, iter_errors

TYPE_FIELDS = {
    "dataset": "dataset_type",
    "group": "group_type",
    "organization": "organization_type",
}


@validate(schema.scheming_schema_create)
def scheming_schema_create(context: Any, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Create a dynamic schema.

    :param schema_type: the type name this schema applies to, must match the
        type field inside the definition (e.g. ``dataset_type``)
    :type schema_type: string
    :param entity_type: the entity this schema applies to (default: ``dataset``)
    :type entity_type: string
    :param definition: the ckanext-scheming schema definition
    :type definition: dict
    """
    tk.check_access("scheming_schema_create", context, data_dict)

    entity_type = data_dict["entity_type"]
    schema_type = data_dict["schema_type"]
    definition = data_dict["definition"]

    _validate_definition(definition, entity_type, schema_type)

    if SchemingSchema.get(entity_type, schema_type):
        raise tk.ValidationError(
            {"schema_type": [tk._(f"Schema for '{schema_type}' already exists")]}
        )

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

    _validate_definition(definition, entity_type, schema_type)

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


def _validate_definition(definition: Any, entity_type: str, schema_type: str) -> None:
    schema_cls = SCHEMA_TYPES.get(entity_type)

    if not schema_cls:
        raise tk.ValidationError(
            {"entity_type": [tk._(f"Entity type '{entity_type}' is not supported")]}
        )

    errors = list(iter_errors(definition, schema_cls()))

    if errors:
        raise tk.ValidationError({error_location(e): [e.message] for e in errors})

    type_field = TYPE_FIELDS[entity_type]
    if definition[type_field] != schema_type:
        raise tk.ValidationError(
            {"definition": [tk._(f"'{type_field}' must match schema_type '{schema_type}'")]}
        )
