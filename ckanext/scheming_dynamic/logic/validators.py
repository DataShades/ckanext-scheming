import logging
from typing import Any

import ckan.plugins.toolkit as tk
from ckan import model, types
from ckan.lib.navl.dictization_functions import missing

from ckanext.scheming.plugins import _expand_schemas
from ckanext.scheming_dynamic.logic.schema import DEFAULT_ENTITY_TYPE
from ckanext.scheming_dynamic.model import SchemingSchema
from ckanext.scheming_dynamic.schema import ENTITY_TYPES
from ckanext.scheming_dynamic.validator import error_location, iter_errors

log = logging.getLogger(__name__)


def scheming_default_entity_type(
    key: types.FlattenKey,
    data: types.FlattenDataDict,
    errors: types.FlattenErrorDict,
    context: types.Context,
) -> Any:
    entity_type_key = ("entity_type",)
    value = data.get(entity_type_key)

    if value is None or value == "" or value is missing:
        data[entity_type_key] = DEFAULT_ENTITY_TYPE


def scheming_definition_valid(
    key: types.FlattenKey,
    data: types.FlattenDataDict,
    errors: types.FlattenErrorDict,
    context: types.Context,
) -> Any:
    entity_type = data[("entity_type",)]
    definition = data[key]

    schema_cls = ENTITY_TYPES.get(entity_type)
    if not schema_cls:
        raise tk.Invalid(tk._(f"Entity type '{entity_type}' is not supported"))

    errs = list(iter_errors(definition, schema_cls()))
    if errs:
        raise tk.Invalid("; ".join(f"{error_location(e)}: {e.message}" for e in errs))

    try:
        _expand_schemas({definition["dataset_type"]: definition})
    except Exception as e:
        raise tk.Invalid(tk._("Schema cannot be expanded: {}").format(e)) from e


def scheming_schema_exists(
    key: types.FlattenKey,
    data: types.FlattenDataDict,
    errors: types.FlattenErrorDict,
    context: types.Context,
) -> Any:
    entity_type = data[("entity_type",)]
    schema_type = data[("schema_type",)]

    if SchemingSchema.get(entity_type, schema_type):
        return

    raise tk.Invalid(tk._(f"Scheming schema {entity_type}:{schema_type} not found."))


def scheming_schema_not_in_use(
    key: types.FlattenKey,
    data: types.FlattenDataDict,
    errors: types.FlattenErrorDict,
    context: types.Context,
) -> Any:
    """Refuse to delete a schema while a package still uses its type.

    TODO: Only "dataset" dynamic schemas are supported for now.
    """
    schema_type = data[key]

    in_use = (
        model.Session.query(model.Package.id)
        .filter(model.Package.type == schema_type)
        .first()
        is not None
    )
    if in_use:
        raise tk.Invalid(
            tk._(
                f"Cannot delete schema '{schema_type}': datasets of this "
                "type still exist."
            )
        )


def get_validators():
    return {
        "scheming_default_entity_type": scheming_default_entity_type,
        "scheming_definition_valid": scheming_definition_valid,
        "scheming_schema_exists": scheming_schema_exists,
        "scheming_schema_not_in_use": scheming_schema_not_in_use,
    }
