from __future__ import annotations

import json

import pytest

from ckan.cli.cli import ckan


def write_schema(tmp_path, data, name="schema.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "with_extended_cli")
class TestSchemaCommand:
    def test_default_type_is_dataset(self, cli):
        result = cli.invoke(ckan, ["scheming-dynamic", "validation-schema"])
        assert not result.exit_code, result.output
        built = json.loads(result.output)
        assert built["required"] == [
            "about",
            "dataset_type",
            "dataset_fields",
            "resource_fields",
        ]

    @pytest.mark.parametrize(
        ("schema_type", "required_key"),
        [("group", "group_type"), ("organization", "organization_type")],
    )
    def test_type_option(self, cli, schema_type, required_key):
        result = cli.invoke(
            ckan, ["scheming-dynamic", "validation-schema", "--type", schema_type]
        )
        assert not result.exit_code, result.output
        built = json.loads(result.output)
        assert required_key in built["required"]

    def test_invalid_type_option_is_rejected(self, cli):
        result = cli.invoke(
            ckan, ["scheming-dynamic", "validation-schema", "--type", "not-a-type"]
        )
        assert result.exit_code != 0


@pytest.mark.ckan_config("ckan.plugins", "scheming_dynamic")
@pytest.mark.usefixtures("with_plugins", "with_extended_cli")
class TestValidateCommand:
    def test_valid_schema_exits_zero(self, cli, tmp_path, schema_definition):
        path = write_schema(tmp_path, schema_definition)
        result = cli.invoke(ckan, ["scheming-dynamic", "validate", str(path)])
        assert result.exit_code == 0, result.output
        assert "OK - no schema violations" in result.output

    def test_invalid_schema_exits_nonzero(self, cli, tmp_path, schema_definition):
        data = {
            **schema_definition,
            "dataset_fields": [{"field_name": "x", "preset": "not_a_real_preset"}],
        }
        path = write_schema(tmp_path, data)
        result = cli.invoke(ckan, ["scheming-dynamic", "validate", str(path)])
        assert result.exit_code == 1
        assert "not_a_real_preset" in result.output

    def test_multiple_files_are_all_reported(self, cli, tmp_path, schema_definition):
        valid = write_schema(tmp_path, schema_definition, "valid.json")
        invalid = write_schema(tmp_path, {"about": "Example schema"}, "invalid.json")

        result = cli.invoke(
            ckan, ["scheming-dynamic", "validate", str(valid), str(invalid)]
        )

        assert result.exit_code == 1
        assert "OK - no schema violations" in result.output
        assert "is a required property" in result.output

    def test_missing_file_argument_is_rejected(self, cli):
        result = cli.invoke(ckan, ["scheming-dynamic", "validate"])
        assert result.exit_code != 0

    def test_nonexistent_file_is_rejected(self, cli):
        result = cli.invoke(
            ckan, ["scheming-dynamic", "validate", "/no/such/file.yaml"]
        )
        assert result.exit_code != 0
