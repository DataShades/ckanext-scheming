from __future__ import annotations

import pytest

import ckan.plugins.toolkit as tk
from ckan.tests import factories, helpers

from ckanext.scheming_dynamic.model import SchemingSchema


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaCreate:
    def test_create_returns_schema_dict(self, schema_definition):
        result = helpers.call_action(
            "scheming_schema_create",
            schema_type="test-type",
            definition=schema_definition,
        )

        assert result["entity_type"] == "dataset"
        assert result["schema_type"] == "test-type"
        assert result["definition"] == schema_definition
        assert result["updated"]

    def test_created_schema_is_persisted(self, schema_definition):
        helpers.call_action(
            "scheming_schema_create",
            schema_type="test-type",
            definition=schema_definition,
        )

        row = SchemingSchema.get("dataset", "test-type")
        assert row
        assert row.definition == schema_definition

    def test_duplicate_schema_is_rejected(self, schema_definition):
        helpers.call_action(
            "scheming_schema_create",
            schema_type="test-type",
            definition=schema_definition,
        )

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_create",
                schema_type="test-type",
                definition=schema_definition,
            )

        assert "already exists" in str(err.value.error_dict["schema_type"])

    def test_missing_schema_type_is_rejected(self, schema_definition):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_create", definition=schema_definition)

    def test_missing_definition_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_create", schema_type="test-type")

    def test_invalid_entity_type_is_rejected(self, schema_definition):
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_schema_create",
                entity_type="user",
                schema_type="test-type",
                definition=schema_definition,
            )

    def test_unserved_entity_type_is_rejected(self):
        # group/organization schemas aren't merged or routed yet
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_schema_create",
                entity_type="group",
                schema_type="test-group",
                definition={
                    "about": "Example schema",
                    "group_type": "test-group",
                    "fields": [{"field_name": "title"}],
                },
            )

    def test_mismatched_definition_type_is_rejected(self, schema_definition):
        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_create",
                schema_type="other-type",
                definition=schema_definition,
            )

        assert "must match schema_type" in str(err.value.error_dict["definition"])

    def test_empty_definition_is_rejected(self):
        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_create", schema_type="test-type", definition={}
            )

        assert "<root>" in err.value.error_dict

    def test_definition_with_invalid_field_is_rejected(self, schema_definition):
        definition = {
            **schema_definition,
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
    def test_update_changes_definition(self, schema_definition):
        SchemingSchema.create("dataset", "test-type", schema_definition)

        updated = {
            **schema_definition,
            "dataset_fields": [{"field_name": "title"}, {"field_name": "notes"}],
        }
        result = helpers.call_action(
            "scheming_schema_update",
            schema_type="test-type",
            definition=updated,
        )

        assert result["definition"] == updated

        row = SchemingSchema.get("dataset", "test-type")
        assert row
        assert row.definition == updated

    def test_update_missing_schema_is_rejected(self, schema_definition):
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_schema_update",
                schema_type="test-type",
                definition=schema_definition,
            )

    def test_update_with_invalid_definition_is_rejected(self, schema_definition):
        SchemingSchema.create("dataset", "test-type", schema_definition)

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_update", schema_type="test-type", definition={}
            )
        assert "<root>" in err.value.error_dict

    def test_update_missing_definition_is_rejected(self, schema_definition):
        SchemingSchema.create("dataset", "test-type", schema_definition)

        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_update", schema_type="test-type")


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaDelete:
    def test_delete_removes_schema(self, schema_definition):
        SchemingSchema.create("dataset", "test-type", schema_definition)

        result = helpers.call_action("scheming_schema_delete", schema_type="test-type")

        assert result is True
        assert SchemingSchema.get("dataset", "test-type") is None

    def test_delete_only_removes_requested_schema_type(self, schema_definition):
        SchemingSchema.create("dataset", "test-type", schema_definition)
        SchemingSchema.create("dataset", "other-type", schema_definition)

        helpers.call_action("scheming_schema_delete", schema_type="other-type")

        assert SchemingSchema.get("dataset", "other-type") is None
        assert SchemingSchema.get("dataset", "test-type")

    def test_delete_missing_schema_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_delete", schema_type="test-type")

    def test_delete_missing_schema_type_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_delete")

    def test_delete_is_rejected_when_packages_of_type_exist(self, schema_definition):
        SchemingSchema.create("dataset", "test-type", schema_definition)
        factories.Dataset(type="test-type")

        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_delete", schema_type="test-type")

        assert SchemingSchema.get("dataset", "test-type")
