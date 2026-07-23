from __future__ import annotations

import pytest

from ckanext.scheming_dynamic.schema import (
    SCHEMA_TYPES,
    DatasetSchema,
    GroupSchema,
    OrganisationSchema,
)


class TestSchemaTypes:
    @pytest.mark.parametrize(
        ("schema_cls", "expected_required"),
        [
            (
                DatasetSchema,
                ["about_url", "dataset_type", "dataset_fields", "resource_fields"],
            ),
            (GroupSchema, ["about_url", "group_type", "fields"]),
            (OrganisationSchema, ["about_url", "organization_type", "fields"]),
        ],
    )
    def test_required_keys(self, schema_cls, expected_required):
        built = schema_cls().build()
        assert built["required"] == expected_required

    @pytest.mark.parametrize(
        ("schema_cls", "field_list_keys"),
        [
            (DatasetSchema, ["dataset_fields", "resource_fields"]),
            (GroupSchema, ["fields"]),
            (OrganisationSchema, ["fields"]),
        ],
    )
    def test_field_list_properties_reference_shared_field_def(
        self, schema_cls, field_list_keys
    ):
        built = schema_cls().build()
        for key in field_list_keys:
            assert built["properties"][key]["items"] == {"$ref": "#/$defs/field"}

    def test_registry_matches_classes(self):
        assert SCHEMA_TYPES["dataset"] is DatasetSchema
        assert SCHEMA_TYPES["group"] is GroupSchema
        assert SCHEMA_TYPES["organization"] is OrganisationSchema

    def test_common_root_properties_are_shared(self):
        for schema_cls in SCHEMA_TYPES.values():
            props = schema_cls().build()["properties"]
            assert props["about_url"] == {
                "type": "string",
                "format": "uri",
                "minLength": 1,
            }
            assert props["about"] == {"type": "string"}
            assert props["scheming_version"] == {"type": "integer"}

    def test_field_def_is_identical_across_schema_types(self):
        built = [
            schema_cls().build()["$defs"]["field"]
            for schema_cls in SCHEMA_TYPES.values()
        ]
        assert all(field_def == built[0] for field_def in built)

    def test_builtin_preset_names_include_known_presets(self):
        enum = DatasetSchema().build()["$defs"]["preset"]["enum"]
        assert "title" in enum
        assert "select" in enum
        assert "not_a_real_preset" not in enum

    def test_schema_is_valid_jsonschema(self):
        jsonschema = pytest.importorskip("jsonschema")
        for schema_cls in SCHEMA_TYPES.values():
            jsonschema.Draft202012Validator.check_schema(schema_cls().build())
