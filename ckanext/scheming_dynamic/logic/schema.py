from ckan import types
from ckan.logic.schema import validator_args

DEFAULT_ENTITY_TYPE = "dataset"
# TODO: group/organization dynamic schemas are not supported yet
ENTITY_TYPES = [DEFAULT_ENTITY_TYPE]


@validator_args
def scheming_schema_create(  # noqa: PLR0913
    not_missing: types.Validator,
    unicode_safe: types.Validator,
    convert_to_json_if_string: types.Validator,
    one_of: types.ValidatorFactory,
    default: types.ValidatorFactory,
) -> types.Schema:
    return {
        "schema_type": [not_missing, unicode_safe],
        "entity_type": [
            default(DEFAULT_ENTITY_TYPE),
            unicode_safe,
            one_of(ENTITY_TYPES),
        ],
        "definition": [not_missing, convert_to_json_if_string],
    }


@validator_args
def scheming_schema_update(
    not_missing: types.Validator,
    unicode_safe: types.Validator,
    scheming_schema_exists: types.DataValidator,
) -> types.Schema:
    schema = scheming_schema_create()

    schema["schema_type"] = [not_missing, unicode_safe, scheming_schema_exists]

    return schema


@validator_args
def scheming_schema_delete(  # noqa: PLR0913
    scheming_schema_not_in_use: types.DataValidator,
    not_missing: types.Validator,
    unicode_safe: types.Validator,
    scheming_schema_exists: types.DataValidator,
    one_of: types.ValidatorFactory,
    default: types.ValidatorFactory,
) -> types.Schema:
    return {
        "schema_type": [
            not_missing,
            unicode_safe,
            scheming_schema_exists,
            scheming_schema_not_in_use,
        ],
        "entity_type": [
            default(DEFAULT_ENTITY_TYPE),
            unicode_safe,
            one_of(ENTITY_TYPES),
        ],
    }
