from __future__ import annotations

import pytest

import ckan.plugins.toolkit as tk

from ckanext.scheming_dynamic.logic.validators import scheming_schema_exists
from ckanext.scheming_dynamic.model import SchemingSchema

DEFINITION = {
    "about_url": "https://example.com",
    "dataset_type": "test-type",
    "dataset_fields": [{"field_name": "title"}],
    "resource_fields": [{"field_name": "url"}],
}


def call_validator(entity_type: str, schema_type: str) -> None:
    data = {
        ("entity_type",): entity_type,
        ("schema_type",): schema_type,
    }
    return scheming_schema_exists(("schema_type",), data, {}, {})


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSchemingSchemaExists:
    def test_existing_schema_passes(self):
        SchemingSchema.create("dataset", "dataset", DEFINITION)

        assert call_validator("dataset", "dataset") is None

    def test_missing_schema_raises_invalid(self):
        with pytest.raises(tk.Invalid, match="not found"):
            call_validator("dataset", "dataset")

    def test_schema_for_other_entity_type_does_not_count(self):
        SchemingSchema.create("group", "group", DEFINITION)

        with pytest.raises(tk.Invalid, match="not found"):
            call_validator("dataset", "dataset")
