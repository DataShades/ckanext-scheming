from __future__ import annotations

import pytest

import ckan.plugins.toolkit as tk
from ckan.tests import helpers

from ckanext.scheming_dynamic.model import SchemingSchema

VALID_DEFINITION = {
    "about_url": "https://example.com",
    "dataset_type": "test-type",
    "dataset_fields": [{"field_name": "title"}],
    "resource_fields": [{"field_name": "url"}],
}

UPDATED_DEFINITION = {
    **VALID_DEFINITION,
    "dataset_fields": [{"field_name": "title"}, {"field_name": "notes"}],
}


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaCreate:
    def test_create_returns_schema_dict(self):
        result = helpers.call_action(
            "scheming_schema_create",
            schema_type="test-type",
            definition=VALID_DEFINITION,
        )

        assert result["entity_type"] == "dataset"
        assert result["schema_type"] == "test-type"
        assert result["definition"] == VALID_DEFINITION
        assert result["updated"]

    def test_created_schema_is_persisted(self):
        helpers.call_action(
            "scheming_schema_create",
            schema_type="test-type",
            definition=VALID_DEFINITION,
        )

        row = SchemingSchema.get("dataset", "test-type")
        assert row
        assert row.definition == VALID_DEFINITION

    def test_duplicate_schema_is_rejected(self):
        helpers.call_action(
            "scheming_schema_create",
            schema_type="test-type",
            definition=VALID_DEFINITION,
        )

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_create",
                schema_type="test-type",
                definition=VALID_DEFINITION,
            )

        assert "already exists" in str(err.value.error_dict["schema_type"])

    def test_missing_schema_type_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_create", definition=VALID_DEFINITION)

    def test_missing_definition_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_create", schema_type="test-type")

    def test_invalid_entity_type_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_schema_create",
                entity_type="user",
                schema_type="test-type",
                definition=VALID_DEFINITION,
            )

    def test_unserved_entity_type_is_rejected(self):
        # group/organization schemas aren't merged or routed yet
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_schema_create",
                entity_type="group",
                schema_type="test-group",
                definition={
                    "about_url": "https://example.com",
                    "group_type": "test-group",
                    "fields": [{"field_name": "title"}],
                },
            )

    def test_mismatched_definition_type_is_rejected(self):
        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_create",
                schema_type="other-type",
                definition=VALID_DEFINITION,
            )

        assert "must match schema_type" in str(err.value.error_dict["definition"])

    def test_empty_definition_is_rejected(self):
        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_schema_create", schema_type="test-type", definition={})

        assert "<root>" in err.value.error_dict

    def test_definition_with_invalid_field_is_rejected(self):
        definition = {
            **VALID_DEFINITION,
            "dataset_fields": [{"label": "No field_name here"}],
        }

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_create",
                schema_type="test-type",
                definition=definition,
            )

        assert "dataset_fields/0" in err.value.error_dict


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaUpdate:
    def test_update_changes_definition(self):
        SchemingSchema.create("dataset", "test-type", VALID_DEFINITION)

        result = helpers.call_action(
            "scheming_schema_update",
            schema_type="test-type",
            definition=UPDATED_DEFINITION,
        )

        assert result["definition"] == UPDATED_DEFINITION

        row = SchemingSchema.get("dataset", "test-type")
        assert row
        assert row.definition == UPDATED_DEFINITION

    def test_update_missing_schema_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_schema_update",
                schema_type="test-type",
                definition=VALID_DEFINITION,
            )

    def test_update_with_invalid_definition_is_rejected(self):
        SchemingSchema.create("dataset", "test-type", VALID_DEFINITION)

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_schema_update", schema_type="test-type", definition={})
        assert "<root>" in err.value.error_dict

    def test_update_missing_definition_is_rejected(self):
        SchemingSchema.create("dataset", "test-type", VALID_DEFINITION)

        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_update", schema_type="test-type")


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaDelete:
    def test_delete_removes_schema(self):
        SchemingSchema.create("dataset", "test-type", VALID_DEFINITION)

        result = helpers.call_action("scheming_schema_delete", schema_type="test-type")

        assert result is True
        assert SchemingSchema.get("dataset", "test-type") is None

    def test_delete_only_removes_requested_schema_type(self):
        SchemingSchema.create("dataset", "test-type", VALID_DEFINITION)
        SchemingSchema.create("dataset", "other-type", VALID_DEFINITION)

        helpers.call_action("scheming_schema_delete", schema_type="other-type")

        assert SchemingSchema.get("dataset", "other-type") is None
        assert SchemingSchema.get("dataset", "test-type")

    def test_delete_missing_schema_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_delete", schema_type="test-type")

    def test_delete_missing_schema_type_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_delete")
