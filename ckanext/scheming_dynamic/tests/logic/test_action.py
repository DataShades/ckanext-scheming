from __future__ import annotations

import pytest

import ckan.plugins.toolkit as tk
from ckan.tests import factories, helpers

from ckanext.scheming_dynamic.model import (
    SchemingPreset,
    SchemingSchemaActivity,
    SchemingSchemaVersion,
)
from ckanext.scheming_dynamic.tests import factories as scheming_factories


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db", "with_request_context")
class TestSchemingSchemaCreate:
    def test_create_returns_schema_dict(self, schema_definition):
        result = helpers.call_action(
            "scheming_schema_create",
            definition=schema_definition,
        )

        assert result["entity_type"] == "dataset"
        assert result["schema_type"] == "test-type"
        assert result["definition"] == schema_definition
        assert result["version"] == 1
        assert result["created"]

    def test_created_schema_is_persisted(self, schema_definition):
        helpers.call_action(
            "scheming_schema_create",
            definition=schema_definition,
        )

        row = SchemingSchemaVersion.head("dataset", "test-type")
        assert row
        assert row.definition == schema_definition

    def test_duplicate_schema_is_rejected(self, schema_definition):
        helpers.call_action(
            "scheming_schema_create",
            definition=schema_definition,
        )

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_create",
                definition=schema_definition,
            )

        assert "already exists" in str(err.value.error_dict["schema_type"])

    def test_missing_definition_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_create")

    def test_invalid_entity_type_is_rejected(self, schema_definition):
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_schema_create",
                entity_type="user",
                definition=schema_definition,
            )

    def test_unserved_entity_type_is_rejected(self):
        # group/organization schemas aren't merged or routed yet
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_schema_create",
                entity_type="group",
                definition={
                    "about": "Example schema",
                    "group_type": "test-group",
                    "fields": [{"field_name": "title"}],
                },
            )

    def test_dataset_type_ending_in_resource_is_rejected(self, schema_definition):
        # "_resource" is the suffix CKAN appends to build a type-specific
        # resource blueprint name; a real type named that way collides with
        # it (see build_dynamic_type_url) and can misroute URLs for either
        # type, or crash schema rendering outright
        definition = {**schema_definition, "dataset_type": "test-type_resource"}

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_schema_create", definition=definition)

        assert "must not end with '_resource'" in str(
            err.value.error_dict["definition"]
        )

    def test_empty_definition_is_rejected(self):
        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_schema_create", definition={})

        assert "<root>" in str(err.value.error_dict["definition"])

    def test_definition_with_invalid_field_is_rejected(self, schema_definition):
        definition = {
            **schema_definition,
            "dataset_fields": [{"label": "No field_name here"}],
        }

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_create",
                definition=definition,
            )

        assert "dataset_fields/0" in str(err.value.error_dict["definition"])

    def test_schema_that_fails_to_render_is_rejected(self, schema_definition):
        # select.html needs choices/choices_helper to iterate over; without
        # one it blows up mid-render instead of failing validation
        definition = {
            **schema_definition,
            "dataset_fields": [
                *schema_definition["dataset_fields"],
                {"field_name": "broken", "form_snippet": "select.html"},
            ],
        }

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_schema_create", definition=definition)

        assert "cannot be rendered" in str(err.value.error_dict["definition"]).lower()
        assert SchemingSchemaVersion.head_version("dataset", "test-type") == 0


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db", "with_request_context")
class TestSchemingSchemaUpdate:
    def test_update_changes_definition(self, schema_definition):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)

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

        row = SchemingSchemaVersion.head("dataset", "test-type")
        assert row
        assert row.definition == updated

    def test_update_with_unchanged_definition_is_a_noop(self, schema_definition):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)

        result = helpers.call_action(
            "scheming_schema_update",
            schema_type="test-type",
            definition=schema_definition,
        )

        assert result["version"] == 1
        assert SchemingSchemaVersion.head_version("dataset", "test-type") == 1

    def test_update_with_unchanged_definition_still_logs_activity(
        self, schema_definition
    ):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)
        before = SchemingSchemaActivity.count_history("dataset", "test-type")

        helpers.call_action(
            "scheming_schema_update",
            schema_type="test-type",
            definition=schema_definition,
        )

        after = SchemingSchemaActivity.count_history("dataset", "test-type")
        assert after == before + 1

    def test_update_with_unchanged_definition_does_not_fork_pinned_version(
        self, schema_definition
    ):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)
        factories.Dataset(type="test-type")  # locks/pins version 1

        result = helpers.call_action(
            "scheming_schema_update",
            schema_type="test-type",
            definition=schema_definition,
        )

        assert result["version"] == 1
        assert SchemingSchemaVersion.head_version("dataset", "test-type") == 1

    def test_update_missing_schema_is_rejected(self, schema_definition):
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_schema_update",
                schema_type="test-type",
                definition=schema_definition,
            )

    def test_update_with_invalid_definition_is_rejected(self, schema_definition):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_schema_update", schema_type="test-type", definition={}
            )
        assert "<root>" in str(err.value.error_dict["definition"])

    def test_update_missing_definition_is_rejected(self, schema_definition):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)

        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_update", schema_type="test-type")


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaDelete:
    def test_delete_removes_schema(self, schema_definition):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)

        result = helpers.call_action("scheming_schema_delete", schema_type="test-type")

        assert result is True
        assert SchemingSchemaVersion.head_version("dataset", "test-type") == 0

    def test_delete_only_removes_requested_schema_type(self, schema_definition):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)
        SchemingSchemaVersion.create("dataset", "other-type", schema_definition)

        helpers.call_action("scheming_schema_delete", schema_type="other-type")

        assert SchemingSchemaVersion.head_version("dataset", "other-type") == 0
        assert SchemingSchemaVersion.head("dataset", "test-type")

    def test_delete_missing_schema_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_delete", schema_type="test-type")

    def test_delete_missing_schema_type_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_delete")

    def test_delete_is_rejected_when_packages_of_type_exist(self, schema_definition):
        SchemingSchemaVersion.create("dataset", "test-type", schema_definition)
        factories.Dataset(type="test-type")

        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_schema_delete", schema_type="test-type")

        assert SchemingSchemaVersion.head("dataset", "test-type")

    def test_delete_unsupported_entity_type(self):
        with pytest.raises(tk.ValidationError, match="Value must be one of"):
            helpers.call_action(
                "scheming_schema_delete", schema_type="test-type", entity_type="study"
            )


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db", "with_request_context")
class TestSchemingPresetCreate:
    def test_create_returns_preset_dict(self, preset_definition):
        result = helpers.call_action(
            "scheming_preset_create",
            definition=preset_definition,
        )

        assert result["preset_name"] == "test-preset"
        assert result["values"] == preset_definition["values"]
        assert result["updated"]

    def test_created_preset_is_persisted(self, preset_definition):
        helpers.call_action(
            "scheming_preset_create",
            definition=preset_definition,
        )

        row = SchemingPreset.get("test-preset")
        assert row
        assert row.values == preset_definition["values"]

    def test_duplicate_preset_is_rejected(self, preset_definition):
        helpers.call_action(
            "scheming_preset_create",
            definition=preset_definition,
        )

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_preset_create",
                definition=preset_definition,
            )

        assert "already exists" in str(err.value.error_dict["preset_name"])

    def test_missing_definition_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_preset_create")

    def test_definition_missing_preset_name_is_rejected(self):
        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_preset_create", definition={"values": {}})

        assert "preset_name" in str(err.value.error_dict["definition"])

    def test_definition_with_invalid_values_is_rejected(self, preset_definition):
        definition = {
            **preset_definition,
            "values": {"repeating_subfields": "notalist"},
        }

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_preset_create", definition=definition)

        assert "values" in str(err.value.error_dict["definition"])

    def test_self_reference_on_a_not_yet_created_preset_is_rejected(
        self, preset_definition
    ):
        # "test-preset" isn't registered yet, so it can't be its own base
        # either way: caught by the preset enum, not the cycle resolver
        definition = {**preset_definition, "values": {"preset": "test-preset"}}

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_preset_create", definition=definition)

        assert "is not one of" in str(err.value.error_dict["definition"])

    def test_unknown_base_preset_is_rejected(self, preset_definition):
        definition = {**preset_definition, "values": {"preset": "not-a-real-preset"}}

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_preset_create", definition=definition)

        assert "not-a-real-preset" in str(err.value.error_dict["definition"])

    def test_base_on_builtin_preset_is_accepted(self, preset_definition):
        definition = {**preset_definition, "values": {"preset": "title"}}

        result = helpers.call_action("scheming_preset_create", definition=definition)

        assert result["values"] == {"preset": "title"}

    def test_preset_that_fails_to_render_is_rejected(self, preset_definition):
        # select.html needs choices/choices_helper to iterate over; without
        # one it blows up mid-render instead of failing validation
        definition = {**preset_definition, "values": {"form_snippet": "select.html"}}

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_preset_create", definition=definition)

        assert "failed to render" in str(err.value.error_dict["definition"]).lower()
        assert SchemingPreset.get("test-preset") is None

    def test_name_shadowing_a_builtin_preset_is_accepted(self):
        # deliberate override, same as a DB schema overriding a file schema
        # of the same type: no uniqueness check against static presets
        definition = {
            "preset_name": "title",
            "values": {"validators": "not_empty unicode_safe"},
        }

        result = helpers.call_action("scheming_preset_create", definition=definition)

        assert result["preset_name"] == "title"
        assert result["values"] == definition["values"]


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db", "with_request_context")
class TestSchemingPresetUpdate:
    def test_update_changes_values(self, preset_definition):
        scheming_factories.Preset(
            preset_name="test-preset", values=preset_definition["values"]
        )

        updated = {**preset_definition, "values": {"form_snippet": "text.html"}}
        result = helpers.call_action(
            "scheming_preset_update",
            preset_name="test-preset",
            definition=updated,
        )

        assert result["values"] == {"form_snippet": "text.html"}

        row = SchemingPreset.get("test-preset")
        assert row
        assert row.values == {"form_snippet": "text.html"}

    def test_update_missing_preset_is_rejected(self, preset_definition):
        with pytest.raises(tk.ValidationError):
            helpers.call_action(
                "scheming_preset_update",
                preset_name="test-preset",
                definition=preset_definition,
            )

    def test_update_preset_name_mismatch_is_rejected(self, preset_definition):
        scheming_factories.Preset(
            preset_name="test-preset", values=preset_definition["values"]
        )

        other = {**preset_definition, "preset_name": "other-preset"}
        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_preset_update",
                preset_name="test-preset",
                definition=other,
            )

        assert "must match preset_name" in str(err.value.error_dict["definition"])

    def test_update_with_invalid_values_is_rejected(self, preset_definition):
        scheming_factories.Preset(
            preset_name="test-preset", values=preset_definition["values"]
        )

        invalid = {**preset_definition, "values": {"repeating_subfields": "notalist"}}
        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_preset_update", preset_name="test-preset", definition=invalid
            )

        assert "values" in str(err.value.error_dict["definition"])

    def test_update_missing_definition_is_rejected(self, preset_definition):
        scheming_factories.Preset(
            preset_name="test-preset", values=preset_definition["values"]
        )

        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_preset_update", preset_name="test-preset")

    def test_update_creating_a_cycle_is_rejected(self, preset_definition):
        # "test-preset" starts with no base, and "a" bases on it, so both
        # currently resolve fine; editing "test-preset" to base on "a" is
        # what closes the loop
        scheming_factories.Preset(
            preset_name="test-preset", values=preset_definition["values"]
        )
        scheming_factories.Preset(preset_name="a", values={"preset": "test-preset"})

        definition = {**preset_definition, "values": {"preset": "a"}}
        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action(
                "scheming_preset_update",
                preset_name="test-preset",
                definition=definition,
            )

        assert "cycle" in str(err.value.error_dict["definition"]).lower()
        row = SchemingPreset.get("test-preset")
        assert row
        assert row.values == preset_definition["values"]


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingPresetDelete:
    def test_delete_removes_preset(self, preset_definition):
        scheming_factories.Preset(
            preset_name="test-preset", values=preset_definition["values"]
        )

        result = helpers.call_action(
            "scheming_preset_delete", preset_name="test-preset"
        )

        assert result is True
        assert SchemingPreset.get("test-preset") is None

    def test_delete_missing_preset_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_preset_delete", preset_name="test-preset")

    def test_delete_missing_preset_name_is_rejected(self):
        with pytest.raises(tk.ValidationError):
            helpers.call_action("scheming_preset_delete")

    def test_delete_is_rejected_when_another_preset_bases_on_it(
        self, preset_definition
    ):
        scheming_factories.Preset(
            preset_name="test-preset", values=preset_definition["values"]
        )
        scheming_factories.Preset(
            preset_name="dependent-preset", values={"preset": "test-preset"}
        )

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_preset_delete", preset_name="test-preset")

        assert "dependent-preset" in str(err.value.error_dict["preset_name"])
        assert SchemingPreset.get("test-preset")

    def test_delete_is_rejected_when_used_by_a_schema(
        self, preset_definition, schema_definition
    ):
        scheming_factories.Preset(
            preset_name="test-preset", values=preset_definition["values"]
        )
        definition = {
            **schema_definition,
            "dataset_fields": [{"field_name": "x", "preset": "test-preset"}],
        }
        SchemingSchemaVersion.create("dataset", "test-type", definition)

        with pytest.raises(tk.ValidationError) as err:
            helpers.call_action("scheming_preset_delete", preset_name="test-preset")

        assert "test-type" in str(err.value.error_dict["preset_name"])
        assert SchemingPreset.get("test-preset")
