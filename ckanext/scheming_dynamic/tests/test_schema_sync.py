from __future__ import annotations

import pytest
from freezegun import freeze_time

import ckan.plugins.toolkit as tk
from ckan.lib.plugins import lookup_package_plugin
from ckan.tests import helpers

from ckanext.scheming.plugins import SchemingDatasetsPlugin
from ckanext.scheming_dynamic.model import SchemingSchemaVersion


@pytest.fixture
def schema_definition(schema_definition):
    return {
        **schema_definition,
        "dataset_fields": [{"field_name": "custom_title", "label": "Custom title"}],
    }


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets scheming_dynamic")
@pytest.mark.ckan_config(
    "scheming.dataset_schemas", "ckanext.scheming:ckan_dataset.yaml"
)
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestDynamicSchemaSync:
    def test_new_type_appears_without_restart(
        self, schema_definition, test_request_context
    ):
        assert "test-type" not in tk.h.scheming_dataset_schemas()

        with test_request_context():
            helpers.call_action(
                "scheming_schema_create",
                schema_type="test-type",
                definition=schema_definition,
            )

        schemas = tk.h.scheming_dataset_schemas()
        assert "test-type" in schemas
        assert "dataset" in schemas

    def test_new_type_resolves_to_scheming_plugin(
        self, schema_definition, test_request_context
    ):
        definition = {**schema_definition, "dataset_type": "lookup-test-type"}

        assert (
            lookup_package_plugin("lookup-test-type")
            is not SchemingDatasetsPlugin.instance
        )

        with test_request_context():
            helpers.call_action(
                "scheming_schema_create",
                schema_type="lookup-test-type",
                definition=definition,
            )
        tk.h.scheming_dataset_schemas()  # trigger the lazy DB sync

        assert (
            lookup_package_plugin("lookup-test-type") is SchemingDatasetsPlugin.instance
        )

    def test_deleted_type_stops_resolving_to_scheming_plugin(
        self, schema_definition, test_request_context
    ):
        definition = {**schema_definition, "dataset_type": "test-deleted"}

        with test_request_context():
            helpers.call_action(
                "scheming_schema_create",
                schema_type="test-deleted",
                definition=definition,
            )
        tk.h.scheming_dataset_schemas()
        assert lookup_package_plugin("test-deleted") is SchemingDatasetsPlugin.instance

        helpers.call_action("scheming_schema_delete", schema_type="test-deleted")
        tk.h.scheming_dataset_schemas()

        # once the schema is gone, this plugin must stop claiming the type:
        # its templates unconditionally assume scheming_get_dataset_schema()
        # returns a definition, and would crash otherwise
        assert (
            lookup_package_plugin("test-deleted") is not SchemingDatasetsPlugin.instance
        )

    def test_db_schema_overrides_file_schema(
        self, schema_definition, test_request_context
    ):
        definition = {**schema_definition, "dataset_type": "dataset"}

        with test_request_context():
            helpers.call_action(
                "scheming_schema_create",
                schema_type="dataset",
                definition=definition,
            )

        schema = tk.h.scheming_get_dataset_schema("dataset")
        assert [f["field_name"] for f in schema["dataset_fields"]] == ["custom_title"]

    def test_update_is_visible_immediately(
        self, schema_definition, test_request_context
    ):
        with test_request_context():
            helpers.call_action(
                "scheming_schema_create",
                schema_type="test-type",
                definition=schema_definition,
            )

        updated = {**schema_definition, "dataset_fields": [{"field_name": "renamed"}]}
        with test_request_context():
            helpers.call_action(
                "scheming_schema_update",
                schema_type="test-type",
                definition=updated,
            )

        schema = tk.h.scheming_get_dataset_schema("test-type")
        assert [f["field_name"] for f in schema["dataset_fields"]] == ["renamed"]

    def test_delete_falls_back_to_file_schema(
        self, schema_definition, test_request_context
    ):
        definition = {**schema_definition, "dataset_type": "dataset"}
        with test_request_context():
            helpers.call_action(
                "scheming_schema_create",
                schema_type="dataset",
                definition=definition,
            )
        assert (
            tk.h.scheming_get_dataset_schema("dataset")["dataset_fields"][0][
                "field_name"
            ]
            == "custom_title"
        )

        helpers.call_action("scheming_schema_delete", schema_type="dataset")

        schema = tk.h.scheming_get_dataset_schema("dataset")
        field_names = [f["field_name"] for f in schema["dataset_fields"]]
        assert "custom_title" not in field_names
        assert "title" in field_names

    def test_presets_are_expanded(self, schema_definition, test_request_context):
        definition = {
            **schema_definition,
            "dataset_fields": [{"field_name": "x", "preset": "title"}],
        }

        with test_request_context():
            helpers.call_action(
                "scheming_schema_create",
                schema_type="test-type",
                definition=definition,
            )

        schema = tk.h.scheming_get_dataset_schema("test-type")
        # form_snippet comes from the expanded title preset
        assert "form_snippet" in schema["dataset_fields"][0]

    def test_dynamic_type_is_listed_in_package_types(self, schema_definition):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)

        assert "test-type" in helpers.call_action("scheming_dataset_schema_list")

    def test_group_rows_do_not_leak_into_dataset_schemas(self, schema_definition):
        SchemingSchemaVersion.create("group", "test-group", schema_definition)

        assert "test-group" not in tk.h.scheming_dataset_schemas()

    def test_delete_then_create_at_the_same_instant_is_still_detected(
        self, schema_definition, test_request_context
    ):
        anchor = {**schema_definition, "dataset_type": "anchor"}
        a = {**schema_definition, "dataset_type": "a"}
        b = {**schema_definition, "dataset_type": "b"}

        with freeze_time("2024-01-01T00:00:00Z"):
            with test_request_context():
                helpers.call_action(
                    "scheming_schema_create", schema_type="anchor", definition=anchor
                )
            with test_request_context():
                helpers.call_action(
                    "scheming_schema_create", schema_type="a", definition=a
                )

        # sync once so the fingerprint has "seen" this state
        assert "a" in tk.h.scheming_dataset_schemas()

        with freeze_time("2024-01-01T00:00:00Z"):
            helpers.call_action("scheming_schema_delete", schema_type="a")
            with test_request_context():
                helpers.call_action(
                    "scheming_schema_create", schema_type="b", definition=b
                )

        schemas = tk.h.scheming_dataset_schemas()
        assert "b" in schemas
        assert "a" not in schemas
