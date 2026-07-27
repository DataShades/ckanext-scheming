import logging
from typing import Any

import ckan.plugins.toolkit as tk
from ckan import model, types

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


def scheming_schema_not_in_use(
    key: types.FlattenKey,
    data: types.FlattenDataDict,
    errors: types.FlattenErrorDict,
    context: types.Context,
) -> Any:
    """Refuse to delete a schema while a package still uses its type.

    Only "dataset" entities are backed by an actual model row today (see
    ``ENTITY_TYPES`` in ``logic/schema.py``), so this is a no-op for any
    other entity_type.
    """
    entity_type = data.get(("entity_type",))
    if entity_type is tk.missing or not entity_type:
        entity_type = DEFAULT_ENTITY_TYPE

    if entity_type != DEFAULT_ENTITY_TYPE:
        return

    schema_type = data[("schema_type",)]

    in_use = (
        model.Session.query(model.Package.id)
        .filter(model.Package.type == schema_type)
        .first()
        is not None
    )
    if in_use:
        raise tk.Invalid(
            f"Cannot delete schema '{schema_type}': "
            "datasets of this type still exist."
        )


def get_validators():
    return {
        "scheming_schema_exists": scheming_schema_exists,
        "scheming_schema_not_in_use": scheming_schema_not_in_use,
    }
