from __future__ import annotations

import pytest

import ckan.plugins.toolkit as tk
from ckan.tests import factories

from ckanext.scheming_dynamic.logic.validators import (
    scheming_definition_valid,
    scheming_schema_exists,
    scheming_schema_not_in_use,
)
from ckanext.scheming_dynamic.model import SchemingSchema


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaExists:
    def call_validator(self, entity_type: str, schema_type: str) -> None:
        data = {
            ("entity_type",): entity_type,
            ("schema_type",): schema_type,
        }
        return scheming_schema_exists(("schema_type",), data, {}, {})

    def test_existing_schema_passes(self, schema_definition):
        SchemingSchema.create("dataset", "test-type", schema_definition)

        assert self.call_validator("dataset", "test-type") is None

    def test_missing_schema_raises_invalid(self):
        with pytest.raises(tk.Invalid, match="not found"):
            self.call_validator("dataset", "test-type")

    def test_schema_for_other_entity_type_does_not_count(self, schema_definition):
        SchemingSchema.create("group", "test-type", schema_definition)

        with pytest.raises(tk.Invalid, match="not found"):
            self.call_validator("dataset", "test-type")


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaNotInUse:
    def _call_not_in_use_validator(self, entity_type: str, schema_type: str) -> None:
        data = {
            ("entity_type",): entity_type,
            ("schema_type",): schema_type,
        }
        return scheming_schema_not_in_use(("schema_type",), data, {}, {})

    def test_passes_when_no_package_of_type_exists(self):
        assert self._call_not_in_use_validator("dataset", "test-type") is None

    def test_raises_invalid_when_package_of_type_exists(self):
        factories.Dataset(type="test-type")

        with pytest.raises(tk.Invalid, match="still exist"):
            self._call_not_in_use_validator("dataset", "test-type")


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingDefinitionValid:
    def call_definition_validator(self, definition: dict) -> None:
        data = {
            ("entity_type",): "dataset",
            ("definition",): definition,
        }
        return scheming_definition_valid(("definition",), data, {}, {})

    def test_valid_definition_passes(self, schema_definition):
        assert self.call_definition_validator(schema_definition) is None

    def test_valid_repeating_subfields_passes(self, schema_definition):
        schema_definition["dataset_fields"] = [
            {
                "field_name": "citation",
                "repeating_subfields": [{"field_name": "originator"}],
            }
        ]

        assert self.call_definition_validator(schema_definition) is None

    def test_unknown_entity_type_raises_invalid(self):
        with pytest.raises(tk.Invalid, match="not supported"):
            scheming_definition_valid(
                ("definition",),
                {("entity_type",): "bogus", ("definition",): {}},
                {},
                {},
            )

    def test_missing_required_key_raises_invalid(self, schema_definition):
        del schema_definition["dataset_type"]

        with pytest.raises(tk.Invalid, match="dataset_type"):
            self.call_definition_validator(schema_definition)

    def test_unknown_preset_raises_invalid(self, schema_definition):
        schema_definition["dataset_fields"] = [
            {"field_name": "title", "preset": "not_a_real_preset"}
        ]

        with pytest.raises(tk.Invalid, match="is not one of"):
            self.call_definition_validator(schema_definition)

    @pytest.mark.parametrize(
        "bad_repeating_subfields",
        [
            {"field_name": "originator"},
            "notalist",
            ["originator"],
        ],
        ids=["dict-instead-of-list", "plain-string", "list-of-strings"],
    )
    def test_malformed_repeating_subfields_raises_invalid(
        self, schema_definition, bad_repeating_subfields
    ):
        schema_definition["dataset_fields"] = [
            {"field_name": "citation", "repeating_subfields": bad_repeating_subfields}
        ]

        with pytest.raises(tk.Invalid, match="is not of type"):
            self.call_definition_validator(schema_definition)
