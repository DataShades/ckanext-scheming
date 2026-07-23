import logging
from typing import Any

import ckan.plugins.toolkit as tk
from ckan import types

from ckanext.scheming_dynamic.model import SchemingSchema

log = logging.getLogger(__name__)


def scheming_schema_exists(
    key: types.FlattenKey,
    data: types.FlattenDataDict,
    errors: types.FlattenErrorDict,
    context: types.Context,
) -> Any:
    if SchemingSchema.get(data[("entity_type",)], data[("schema_type",)]):
        return

    raise tk.Invalid(
        "Scheming schema {}:{} not found.".format(
            data[("entity_type",)], data[("schema_type",)]
        )
    )


def get_validators():
    return {
        "scheming_schema_exists": scheming_schema_exists,
    }
