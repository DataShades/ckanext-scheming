from __future__ import annotations

import pytest

import ckan.plugins.toolkit as tk
from ckan.tests import factories

from ckanext.scheming_dynamic.logic.validators import (
    scheming_schema_exists,
    scheming_schema_not_in_use,
)
from ckanext.scheming_dynamic.model import SchemingSchema


def call_validator(entity_type: str, schema_type: str) -> None:
    data = {
        ("entity_type",): entity_type,
        ("schema_type",): schema_type,
    }
    return scheming_schema_exists(("schema_type",), data, {}, {})


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaExists:
    def test_existing_schema_passes(self, schema_definition):
        SchemingSchema.create("dataset", "test-type", schema_definition)

        assert call_validator("dataset", "test-type") is None

    def test_missing_schema_raises_invalid(self):
        with pytest.raises(tk.Invalid, match="not found"):
            call_validator("dataset", "test-type")

    def test_schema_for_other_entity_type_does_not_count(self, schema_definition):
        SchemingSchema.create("group", "test-type", schema_definition)

        with pytest.raises(tk.Invalid, match="not found"):
            call_validator("dataset", "test-type")

    def test_missing_entity_type_defaults_to_dataset(self, schema_definition):
        SchemingSchema.create("dataset", "test-type", schema_definition)

        data = {("schema_type",): "test-type"}
        assert scheming_schema_exists(("schema_type",), data, {}, {}) is None


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

    def test_other_entity_types_are_not_checked(self):
        factories.Dataset(type="test-type")

        assert self._call_not_in_use_validator("group", "test-type") is None

    def test_missing_entity_type_defaults_to_dataset(self):
        factories.Dataset(type="test-type")

        data = {("schema_type",): "test-type"}
        with pytest.raises(tk.Invalid, match="still exist"):
            scheming_schema_not_in_use(("schema_type",), data, {}, {})
