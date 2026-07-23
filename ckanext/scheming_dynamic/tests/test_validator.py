from __future__ import annotations

import json

from ckanext.scheming_dynamic.schema import DatasetSchema
from ckanext.scheming_dynamic.validator import error_location, iter_errors, load_data

MINIMAL_DATASET = {
    "about_url": "https://example.com",
    "dataset_type": "test-type",
    "dataset_fields": [{"field_name": "title"}],
    "resource_fields": [{"field_name": "url"}],
}


def errors_for(data):
    return list(iter_errors(data, DatasetSchema()))


class TestIterErrors:
    def test_minimal_valid_schema_has_no_errors(self):
        assert errors_for(MINIMAL_DATASET) == []

    def test_missing_root_keys_are_reported(self):
        errors = errors_for({})
        messages = {e.message for e in errors}
        assert "'about_url' is a required property" in messages
        assert "'dataset_type' is a required property" in messages
        assert "'dataset_fields' is a required property" in messages
        assert "'resource_fields' is a required property" in messages
        assert all(error_location(e) == "<root>" for e in errors)

    def test_missing_field_name_is_reported(self):
        data = {**MINIMAL_DATASET, "dataset_fields": [{"label": "No name here"}]}
        errors = errors_for(data)
        assert any(
            error_location(e) == "dataset_fields/0" and "field_name" in e.message
            for e in errors
        )

    def test_field_name_wrong_type_is_reported(self):
        data = {**MINIMAL_DATASET, "dataset_fields": [{"field_name": 123}]}
        errors = errors_for(data)
        assert any(error_location(e) == "dataset_fields/0/field_name" for e in errors)

    def test_required_wrong_type_is_reported(self):
        data = {**MINIMAL_DATASET, "dataset_fields": [{"field_name": "x", "required": "yes"}]}
        errors = errors_for(data)
        assert any(error_location(e) == "dataset_fields/0/required" for e in errors)

    def test_unknown_preset_is_reported(self):
        data = {
            **MINIMAL_DATASET,
            "dataset_fields": [{"field_name": "x", "preset": "not_a_real_preset"}],
        }
        errors = errors_for(data)
        assert any(error_location(e) == "dataset_fields/0/preset" for e in errors)

    def test_known_preset_is_accepted(self):
        data = {**MINIMAL_DATASET, "dataset_fields": [{"field_name": "x", "preset": "title"}]}
        assert errors_for(data) == []

    def test_multilang_label_is_accepted(self):
        data = {
            **MINIMAL_DATASET,
            "dataset_fields": [{"field_name": "x", "label": {"en": "Title", "fr": "Titre"}}],
        }
        assert errors_for(data) == []

    def test_multilang_label_with_non_string_value_is_rejected(self):
        data = {
            **MINIMAL_DATASET,
            "dataset_fields": [{"field_name": "x", "label": {"en": "Title", "fr": 5}}],
        }
        errors = errors_for(data)
        assert any(error_location(e) == "dataset_fields/0/label" for e in errors)

    def test_null_label_is_accepted(self):
        data = {**MINIMAL_DATASET, "dataset_fields": [{"field_name": "x", "label": None}]}
        assert errors_for(data) == []

    def test_boolean_choice_label_is_rejected(self):
        data = {
            **MINIMAL_DATASET,
            "dataset_fields": [
                {
                    "field_name": "x",
                    "preset": "select",
                    "choices": [{"value": False, "label": False}],
                }
            ],
        }
        errors = errors_for(data)
        assert any(error_location(e) == "dataset_fields/0/choices/0/label" for e in errors)

    def test_choices_missing_label_is_accepted(self):
        # scheming_choices_label() falls back to `c.get('label', value)`.
        data = {**MINIMAL_DATASET, "dataset_fields": [{"field_name": "x", "choices": [{"value": "a"}]}]}
        assert errors_for(data) == []

    def test_choices_missing_value_is_rejected(self):
        data = {**MINIMAL_DATASET, "dataset_fields": [{"field_name": "x", "choices": [{"label": "A"}]}]}
        errors = errors_for(data)
        assert any(error_location(e) == "dataset_fields/0/choices/0" for e in errors)

    def test_choices_with_non_scalar_value_is_accepted(self):
        data = {
            **MINIMAL_DATASET,
            "dataset_fields": [
                {
                    "field_name": "x",
                    "choices": [
                        {
                            "value": {"type": "Point", "coordinates": [1, 2]},
                            "label": "A place",
                        }
                    ],
                }
            ],
        }
        assert errors_for(data) == []

    def test_default_accepts_any_scalar_type(self):
        for default in ("abc", 1, True, None):
            data = {**MINIMAL_DATASET, "dataset_fields": [{"field_name": "x", "default": default}]}
            assert errors_for(data) == []

    def test_unknown_field_keys_are_ignored(self):
        data = {
            **MINIMAL_DATASET,
            "dataset_fields": [
                {
                    "field_name": "x",
                    "form_snippet": "markdown.html",
                    "msf_group": "General info",
                    "validators": "ignore_missing unicode_safe",
                }
            ],
        }
        assert errors_for(data) == []


class TestLoadData:
    def test_load_yaml(self, tmp_path):
        path = tmp_path / "schema.yaml"
        path.write_text("about_url: https://example.com\ndataset_type: foo\n")
        assert load_data(path) == {"about_url": "https://example.com", "dataset_type": "foo"}

    def test_load_yml_extension(self, tmp_path):
        path = tmp_path / "schema.yml"
        path.write_text("about_url: https://example.com\n")
        assert load_data(path) == {"about_url": "https://example.com"}

    def test_load_json(self, tmp_path):
        path = tmp_path / "schema.json"
        path.write_text(json.dumps({"about_url": "https://example.com"}))
        assert load_data(path) == {"about_url": "https://example.com"}


class TestErrorLocation:
    def test_root_error_location(self):
        errors = errors_for({})
        assert errors
        assert all(error_location(e) == "<root>" for e in errors)

    def test_nested_error_location(self):
        data = {**MINIMAL_DATASET, "resource_fields": [{"field_name": "x", "required": "yes"}]}
        errors = errors_for(data)
        assert any(error_location(e) == "resource_fields/0/required" for e in errors)
