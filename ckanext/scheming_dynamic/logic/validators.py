import logging
from typing import Any

import ckan.plugins.toolkit as tk
from ckan import types

from ckanext.scheming_dynamic.logic.schema import DEFAULT_ENTITY_TYPE
from ckanext.scheming_dynamic.model import SchemingSchema

log = logging.getLogger(__name__)


def scheming_schema_exists(
    key: types.FlattenKey,
    data: types.FlattenDataDict,
    errors: types.FlattenErrorDict,
    context: types.Context,
) -> Any:
    # entity_type may not have passed through its default() validator yet
    entity_type = data.get(("entity_type",))
    if entity_type is tk.missing or not entity_type:
        entity_type = DEFAULT_ENTITY_TYPE

    schema_type = data[("schema_type",)]

    if SchemingSchema.get(entity_type, schema_type):
        return

    raise tk.Invalid(f"Scheming schema {entity_type}:{schema_type} not found.")


def get_validators():
    return {
        "scheming_schema_exists": scheming_schema_exists,
    }
