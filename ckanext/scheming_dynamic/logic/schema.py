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
    scheming_default_entity_type: types.DataValidator,
    scheming_definition_valid: types.DataValidator,
    one_of: types.ValidatorFactory,
    default: types.ValidatorFactory,
) -> types.Schema:
    return {
        "__before": [scheming_default_entity_type],
        "entity_type": [
            default(DEFAULT_ENTITY_TYPE),
            unicode_safe,
            one_of(ENTITY_TYPES),
        ],
        "definition": [
            not_missing,
            convert_to_json_if_string,
            scheming_definition_valid,
        ],
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


@validator_args
def scheming_preset_create(
    not_missing: types.Validator,
    convert_to_json_if_string: types.Validator,
    scheming_preset_definition_valid: types.DataValidator,
) -> types.Schema:
    return {
        "definition": [
            not_missing,
            convert_to_json_if_string,
            scheming_preset_definition_valid,
        ],
    }


@validator_args
def scheming_preset_update(
    not_missing: types.Validator,
    unicode_safe: types.Validator,
    scheming_preset_exists: types.DataValidator,
) -> types.Schema:
    schema = scheming_preset_create()

    schema["preset_name"] = [not_missing, unicode_safe, scheming_preset_exists]

    return schema


@validator_args
def scheming_preset_delete(
    scheming_preset_not_in_use: types.DataValidator,
    not_missing: types.Validator,
    unicode_safe: types.Validator,
    scheming_preset_exists: types.DataValidator,
) -> types.Schema:
    return {
        "preset_name": [
            not_missing,
            unicode_safe,
            scheming_preset_exists,
            scheming_preset_not_in_use,
        ],
    }
