from __future__ import annotations

import pytest

from ckanext.scheming_dynamic.schema import (
    ENTITY_TYPES,
    DatasetSchema,
    GroupSchema,
    OrganizationSchema,
)


class TestSchemaTypes:
    @pytest.mark.parametrize(
        ("schema_cls", "expected_required"),
        [
            (
                DatasetSchema,
                ["about", "dataset_type", "dataset_fields", "resource_fields"],
            ),
            (GroupSchema, ["about", "group_type", "fields"]),
            (OrganizationSchema, ["about", "organization_type", "fields"]),
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
            (OrganizationSchema, ["fields"]),
        ],
    )
    def test_field_list_properties_reference_shared_field_def(
        self, schema_cls, field_list_keys
    ):
        built = schema_cls().build()
        for key in field_list_keys:
            assert built["properties"][key]["items"] == {
                "type": "object",
                "$ref": "#/$defs/field",
            }

    def test_registry_matches_classes(self):
        assert ENTITY_TYPES["dataset"] is DatasetSchema
        assert ENTITY_TYPES["group"] is GroupSchema
        assert ENTITY_TYPES["organization"] is OrganizationSchema

    def test_common_root_properties_are_shared(self):
        for schema_cls in ENTITY_TYPES.values():
            props = schema_cls().build()["properties"]
            assert props["about"] == {
                "type": "string",
                "title": "About",
                "minLength": 1,
            }

    def test_field_def_is_identical_across_schema_types(self):
        built = [
            schema_cls().build()["$defs"]["field"]
            for schema_cls in ENTITY_TYPES.values()
        ]
        assert all(field_def == built[0] for field_def in built)

    def test_builtin_preset_names_include_known_presets(self):
        enum = DatasetSchema().build()["$defs"]["preset"]["enum"]
        assert "title" in enum
        assert "select" in enum
        assert "not_a_real_preset" not in enum

    def test_form_snippet_names_come_from_existing_templates(self):
        template, hidden = DatasetSchema().build()["$defs"]["form_snippet"]["oneOf"]
        assert hidden["type"] == "null"
        assert "large_text.html" in template["enum"]
        assert "markdown.html" in template["enum"]
        assert "_organization_select.html" not in template["enum"]
        assert "not_a_real_snippet.html" not in template["enum"]

    def test_display_snippet_names_come_from_existing_templates(self):
        template, hidden = DatasetSchema().build()["$defs"]["display_snippet"]["oneOf"]
        assert hidden["type"] == "null"
        assert "link.html" in template["enum"]
        assert "not_a_real_snippet.html" not in template["enum"]

    def test_schema_is_valid_jsonschema(self):
        jsonschema = pytest.importorskip("jsonschema")
        for schema_cls in ENTITY_TYPES.values():
            jsonschema.Draft202012Validator.check_schema(schema_cls().build())

    def test_draft_fields_required_is_optional_boolean(self):
        props = DatasetSchema().build()["properties"]
        assert props["draft_fields_required"]["type"] == "boolean"
        assert "draft_fields_required" not in DatasetSchema().required()

    def test_repeating_subfields_reference_shared_field_def(self):
        field_def = DatasetSchema().build()["$defs"]["field"]
        assert field_def["properties"]["repeating_subfields"]["items"] == {
            "$ref": "#/$defs/field"
        }

    def test_repeating_subfields_validate(self):
        jsonschema = pytest.importorskip("jsonschema")
        built = DatasetSchema().build()
        instance = {
            "about": "https://example.com/schema",
            "dataset_type": "dataset",
            "dataset_fields": [
                {
                    "field_name": "contacts",
                    "label": "Contacts",
                    "repeating_label": "Contact",
                    "repeating_subfields": [
                        {"field_name": "address", "label": "Address", "required": True},
                        {"field_name": "phone", "label": "Phone Number"},
                    ],
                },
            ],
            "resource_fields": [{"field_name": "url"}],
        }
        jsonschema.Draft202012Validator(built).validate(instance)
