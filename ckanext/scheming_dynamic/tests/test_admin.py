from __future__ import annotations

import json
from typing import Any

import pytest

import ckan.plugins.toolkit as tk
from ckan.tests import factories, helpers

from ckanext.scheming_dynamic.model import SchemingPreset, SchemingSchemaVersion
from ckanext.scheming_dynamic.tests import factories as scheming_factories

STATUS_OK = 200
STATUS_REDIRECT = 302
STATUS_BAD_REQUEST = 400
STATUS_FORBIDDEN = 403
STATUS_NOT_FOUND = 404

pytestmark = [
    pytest.mark.ckan_config("ckan.plugins", "scheming_datasets scheming_dynamic"),
    pytest.mark.ckan_config(
        "scheming.dataset_schemas", "ckanext.scheming:ckan_dataset.yaml"
    ),
    pytest.mark.ckan_config("scheming.dataset_fallback", "true"),
    pytest.mark.usefixtures("with_plugins", "clean_db"),
]


def _sysadmin_headers() -> dict[str, str]:
    return {"Authorization": factories.SysadminWithToken()["token"]}


class TestAdminAccess:
    def test_anonymous_is_forbidden(self, app):
        app.get(tk.url_for("scheming_dynamic_admin.index"), status=STATUS_FORBIDDEN)
        app.get(tk.url_for("scheming_dynamic_admin.new"), status=STATUS_FORBIDDEN)
        app.get(
            tk.url_for("scheming_dynamic_admin.presets_index"),
            status=STATUS_FORBIDDEN,
        )
        app.get(
            tk.url_for("scheming_dynamic_admin.preset_new"), status=STATUS_FORBIDDEN
        )

    def test_regular_user_is_forbidden(self, app):
        headers = {"Authorization": factories.UserWithToken()["token"]}

        app.get(
            tk.url_for("scheming_dynamic_admin.index"),
            headers=headers,
            status=STATUS_FORBIDDEN,
        )
        app.get(
            tk.url_for("scheming_dynamic_admin.new"),
            headers=headers,
            status=STATUS_FORBIDDEN,
        )
        app.post(
            tk.url_for("scheming_dynamic_admin.preview"),
            headers=headers,
            data={"definition": "{}"},
            status=STATUS_FORBIDDEN,
        )
        app.get(
            tk.url_for("scheming_dynamic_admin.presets_index"),
            headers=headers,
            status=STATUS_FORBIDDEN,
        )
        app.get(
            tk.url_for("scheming_dynamic_admin.preset_new"),
            headers=headers,
            status=STATUS_FORBIDDEN,
        )
        app.post(
            tk.url_for("scheming_dynamic_admin.preset_preview"),
            headers=headers,
            data={"definition": "{}"},
            status=STATUS_FORBIDDEN,
        )

    def test_sysadmin_sees_the_listing(self, app):
        resp = app.get(
            tk.url_for("scheming_dynamic_admin.index"), headers=_sysadmin_headers()
        )

        assert resp.status_code == STATUS_OK
        assert "Dataset schemas" in resp.body

    def test_sysadmin_sees_the_presets_listing(self, app):
        resp = app.get(
            tk.url_for("scheming_dynamic_admin.presets_index"),
            headers=_sysadmin_headers(),
        )

        assert resp.status_code == STATUS_OK
        assert "Field presets" in resp.body


class TestSchemaList:
    def test_created_schema_is_listed(self, app, dataset_schema: dict[str, Any]):
        resp = app.get(
            tk.url_for("scheming_dynamic_admin.index"), headers=_sysadmin_headers()
        )

        assert "test-type" in resp.body

    def test_empty_listing_shows_hint(self, app):
        resp = app.get(
            tk.url_for("scheming_dynamic_admin.index"), headers=_sysadmin_headers()
        )

        assert "No dynamic schemas" in resp.body


class TestSchemaCreate:
    def test_form_renders(self, app):
        resp = app.get(
            tk.url_for("scheming_dynamic_admin.new"), headers=_sysadmin_headers()
        )

        assert resp.status_code == STATUS_OK
        assert 'name="definition"' in resp.body

    def test_valid_definition_creates_schema(self, app, schema_definition):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.new"),
            headers=_sysadmin_headers(),
            data={
                "schema_type": "test-type",
                "definition": json.dumps(schema_definition),
            },
            follow_redirects=False,
        )

        assert resp.status_code == STATUS_REDIRECT
        assert SchemingSchemaVersion.head("dataset", "test-type") is not None

    def test_missing_field_name_is_reported(self, app, schema_definition):
        definition = {**schema_definition, "dataset_fields": [{"label": "No name"}]}

        resp = app.post(
            tk.url_for("scheming_dynamic_admin.new"),
            headers=_sysadmin_headers(),
            data={
                "schema_type": "test-type",
                "definition": json.dumps(definition),
            },
        )

        assert resp.status_code == STATUS_OK
        assert "is a required property" in resp.body
        assert SchemingSchemaVersion.head("dataset", "test-type") is None

    def test_malformed_json_is_reported(self, app):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.new"),
            headers=_sysadmin_headers(),
            data={"schema_type": "test-type", "definition": "{not json"},
        )

        assert resp.status_code == STATUS_OK
        assert "Could not parse as valid JSON" in resp.body

    def test_unknown_form_snippet_is_reported(self, app, schema_definition):
        definition = {
            **schema_definition,
            "dataset_fields": [
                {"field_name": "custom_title", "form_snippet": "nope.html"}
            ],
        }

        resp = app.post(
            tk.url_for("scheming_dynamic_admin.new"),
            headers=_sysadmin_headers(),
            data={
                "schema_type": "test-type",
                "definition": json.dumps(definition),
            },
        )

        assert resp.status_code == STATUS_OK
        assert "is not valid under any of the given schemas" in resp.body
        assert SchemingSchemaVersion.head("dataset", "test-type") is None

    def test_known_form_snippet_is_accepted(self, app, schema_definition):
        definition = {
            **schema_definition,
            "dataset_fields": [
                {"field_name": "custom_title", "form_snippet": "markdown.html"}
            ],
        }

        resp = app.post(
            tk.url_for("scheming_dynamic_admin.new"),
            headers=_sysadmin_headers(),
            data={
                "schema_type": "test-type",
                "definition": json.dumps(definition),
            },
        )

        assert resp.status_code == STATUS_OK
        assert SchemingSchemaVersion.head("dataset", "test-type") is not None

    def test_duplicate_schema_is_reported(
        self, app, dataset_schema: dict[str, Any], schema_definition
    ):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.new"),
            headers=_sysadmin_headers(),
            data={
                "schema_type": "test-type",
                "definition": json.dumps(schema_definition),
            },
        )

        assert resp.status_code == STATUS_OK
        assert "already exists" in resp.body


class TestSchemaEdit:
    def test_form_is_prefilled(self, app, dataset_schema: dict[str, Any]):
        resp = app.get(
            tk.h.url_for("scheming_dynamic_admin.edit", schema_type="test-type"),
            headers=_sysadmin_headers(),
        )

        assert resp.status_code == STATUS_OK
        assert "temporal_coverage" in resp.body

    def test_unknown_schema_is_not_found(self, app):
        app.get(
            tk.h.url_for("scheming_dynamic_admin.edit", schema_type="no-such-type"),
            headers=_sysadmin_headers(),
            status=STATUS_NOT_FOUND,
        )

    def test_valid_definition_updates_schema(
        self, app, dataset_schema: dict[str, Any], schema_definition
    ):
        updated = {
            **schema_definition,
            "dataset_fields": [{"field_name": "renamed_field"}],
        }

        resp = app.post(
            tk.h.url_for("scheming_dynamic_admin.edit", schema_type="test-type"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(updated)},
        )

        assert resp.status_code == STATUS_OK
        schema = SchemingSchemaVersion.head("dataset", "test-type")
        assert schema
        assert schema.definition["dataset_fields"][0]["field_name"] == "renamed_field"

    def test_invalid_definition_is_reported(
        self, app, dataset_schema: dict[str, Any], schema_definition
    ):
        invalid = {**schema_definition, "dataset_fields": [{"label": "No name"}]}

        resp = app.post(
            tk.h.url_for("scheming_dynamic_admin.edit", schema_type="test-type"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(invalid)},
        )

        assert resp.status_code == STATUS_OK
        assert "is a required property" in resp.body
        schema = SchemingSchemaVersion.head("dataset", "test-type")
        assert schema
        assert schema.definition == schema_definition


class TestSchemaDelete:
    def test_schema_is_deleted(self, app, dataset_schema: dict[str, Any]):
        resp = app.post(
            tk.h.url_for("scheming_dynamic_admin.delete", schema_type="test-type"),
            headers=_sysadmin_headers(),
        )

        assert resp.status_code == STATUS_OK
        assert SchemingSchemaVersion.head("dataset", "test-type") is None

    def test_unknown_schema_is_not_found(self, app):
        schema_type = "no-such-type"
        resp = app.post(
            tk.h.url_for("scheming_dynamic_admin.delete", schema_type=schema_type),
            headers=_sysadmin_headers(),
        )

        assert f"Scheming schema dataset:{schema_type} not found" in resp.body
        assert SchemingSchemaVersion.head("dataset", schema_type) is None

    def test_schema_in_use_is_not_deleted(self, app, dataset_schema: dict[str, Any]):
        factories.Dataset(type="test-type")

        resp = app.post(
            tk.h.url_for("scheming_dynamic_admin.delete", schema_type="test-type"),
            headers=_sysadmin_headers(),
        )

        assert "datasets of this type still exist" in resp.body
        assert SchemingSchemaVersion.head("dataset", "test-type") is not None


class TestSchemaHistory:
    def test_anonymous_is_forbidden(self, app, dataset_schema: dict[str, Any]):
        app.get(
            tk.url_for("scheming_dynamic_admin.history", schema_type="test-type"),
            status=STATUS_FORBIDDEN,
        )

    def test_regular_user_is_forbidden(self, app, dataset_schema: dict[str, Any]):
        app.get(
            tk.url_for("scheming_dynamic_admin.history", schema_type="test-type"),
            headers={"Authorization": factories.UserWithToken()["token"]},
            status=STATUS_FORBIDDEN,
        )

    def test_shows_create_entry(self, app, schema_definition):
        with app.flask_app.test_request_context():
            helpers.call_action(
                "scheming_schema_create",
                context={"user": factories.Sysadmin()["name"]},
                definition=schema_definition,
            )

        resp = app.get(
            tk.url_for("scheming_dynamic_admin.history", schema_type="test-type"),
            headers=_sysadmin_headers(),
        )

        assert resp.status_code == STATUS_OK
        assert "create" in resp.body

    def test_unknown_schema_shows_empty_state(self, app):
        resp = app.get(
            tk.url_for("scheming_dynamic_admin.history", schema_type="no-such-type"),
            headers=_sysadmin_headers(),
        )

        assert resp.status_code == STATUS_OK
        assert "No history recorded" in resp.body


class TestSchemaPreview:
    def test_preview_renders_dataset_and_resource_forms(self, app, schema_definition):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preview"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(schema_definition)},
        )

        assert resp.status_code == STATUS_OK
        assert 'name="temporal_coverage"' in resp.body
        assert 'name="url"' in resp.body
        assert "Resource form" in resp.body

    def test_preview_expands_presets(self, app, schema_definition):
        definition = {
            **schema_definition,
            "dataset_fields": [{"field_name": "custom_title", "preset": "title"}],
        }

        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preview"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(definition)},
        )

        assert resp.status_code == STATUS_OK
        assert 'name="custom_title"' in resp.body

    def test_missing_field_name_is_reported(self, app, schema_definition):
        definition = {**schema_definition, "dataset_fields": [{"label": "No name"}]}

        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preview"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(definition)},
            status=STATUS_BAD_REQUEST,
        )

        assert "is a required property" in resp.body

    def test_malformed_json_is_reported(self, app):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preview"),
            headers=_sysadmin_headers(),
            data={"definition": "{oops"},
            status=STATUS_BAD_REQUEST,
        )

        assert "Could not parse as valid JSON" in resp.body


class TestPresetList:
    def test_created_preset_is_listed(self, app, preset: SchemingPreset):
        resp = app.get(
            tk.url_for("scheming_dynamic_admin.presets_index"),
            headers=_sysadmin_headers(),
        )

        assert "test-preset" in resp.body

    def test_empty_listing_shows_hint(self, app):
        resp = app.get(
            tk.url_for("scheming_dynamic_admin.presets_index"),
            headers=_sysadmin_headers(),
        )

        assert "No presets have been created yet." in resp.body


class TestPresetCreate:
    def test_form_renders(self, app):
        resp = app.get(
            tk.url_for("scheming_dynamic_admin.preset_new"),
            headers=_sysadmin_headers(),
        )

        assert resp.status_code == STATUS_OK
        assert 'name="definition"' in resp.body

    def test_valid_definition_creates_preset(self, app, preset_definition):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preset_new"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(preset_definition)},
            follow_redirects=False,
        )

        assert resp.status_code == STATUS_REDIRECT
        assert SchemingPreset.get("test-preset") is not None

    def test_missing_preset_name_is_reported(self, app):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preset_new"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps({"values": {}})},
        )

        assert resp.status_code == STATUS_OK
        assert "is a required property" in resp.body

    def test_malformed_json_is_reported(self, app):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preset_new"),
            headers=_sysadmin_headers(),
            data={"definition": "{not json"},
        )

        assert resp.status_code == STATUS_OK
        assert "Could not parse as valid JSON" in resp.body

    def test_duplicate_preset_is_reported(
        self, app, preset: SchemingPreset, preset_definition: dict
    ):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preset_new"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(preset_definition)},
        )

        assert resp.status_code == STATUS_OK
        assert "already exists" in resp.body


class TestPresetEdit:
    def test_form_is_prefilled(
        self, app, preset: SchemingPreset, preset_definition: dict
    ):
        resp = app.get(
            tk.h.url_for(
                "scheming_dynamic_admin.preset_edit", preset_name="test-preset"
            ),
            headers=_sysadmin_headers(),
        )

        assert resp.status_code == STATUS_OK
        assert "not_empty" in resp.body

    def test_unknown_preset_is_not_found(self, app):
        app.get(
            tk.h.url_for(
                "scheming_dynamic_admin.preset_edit", preset_name="no-such-preset"
            ),
            headers=_sysadmin_headers(),
            status=STATUS_NOT_FOUND,
        )

    def test_valid_definition_updates_preset(
        self, app, preset: SchemingPreset, preset_definition: dict
    ):
        updated = {**preset_definition, "values": {"form_snippet": "text.html"}}

        resp = app.post(
            tk.h.url_for(
                "scheming_dynamic_admin.preset_edit", preset_name="test-preset"
            ),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(updated)},
        )

        assert resp.status_code == STATUS_OK
        row = SchemingPreset.get("test-preset")
        assert row
        assert row.values == {"form_snippet": "text.html"}

    def test_invalid_definition_is_reported(
        self, app, preset: SchemingPreset, preset_definition: dict
    ):
        invalid = {
            **preset_definition,
            "values": {"repeating_subfields": "notalist"},
        }

        resp = app.post(
            tk.h.url_for(
                "scheming_dynamic_admin.preset_edit", preset_name="test-preset"
            ),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(invalid)},
        )

        assert resp.status_code == STATUS_OK
        assert "is not of type" in resp.body
        row = SchemingPreset.get("test-preset")
        assert row
        assert row.values == preset_definition["values"]


class TestPresetDelete:
    def test_preset_is_deleted(self, app, preset: SchemingPreset):
        resp = app.post(
            tk.h.url_for(
                "scheming_dynamic_admin.preset_delete", preset_name="test-preset"
            ),
            headers=_sysadmin_headers(),
        )

        assert resp.status_code == STATUS_OK
        assert SchemingPreset.get("test-preset") is None

    def test_unknown_preset_is_not_found(self, app):
        preset_name = "no-such-preset"
        resp = app.post(
            tk.h.url_for(
                "scheming_dynamic_admin.preset_delete", preset_name=preset_name
            ),
            headers=_sysadmin_headers(),
        )

        # the message quotes preset_name (HTML-escaped on render), so only
        # assert on the quote-free portion
        assert "not found" in resp.body
        assert preset_name in resp.body
        assert SchemingPreset.get(preset_name) is None

    def test_preset_in_use_is_not_deleted(
        self, app, preset: SchemingPreset, schema_definition: dict
    ):
        definition = {
            **schema_definition,
            "dataset_fields": [{"field_name": "x", "preset": "test-preset"}],
        }
        SchemingSchemaVersion.create("dataset", "test-type", definition)

        resp = app.post(
            tk.h.url_for(
                "scheming_dynamic_admin.preset_delete", preset_name="test-preset"
            ),
            headers=_sysadmin_headers(),
        )

        assert "still used by" in resp.body
        assert SchemingPreset.get("test-preset") is not None


class TestPresetPreview:
    def test_preview_renders_the_field(self, app, preset_definition: dict):
        definition = {**preset_definition, "values": {"preset": "title"}}

        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preset_preview"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(definition)},
        )

        assert resp.status_code == STATUS_OK
        assert 'name="preview_field"' in resp.body

    def test_missing_preset_name_is_reported(self, app):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preset_preview"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps({"values": {}})},
            status=STATUS_BAD_REQUEST,
        )

        assert "is a required property" in resp.body

    def test_malformed_json_is_reported(self, app):
        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preset_preview"),
            headers=_sysadmin_headers(),
            data={"definition": "{oops"},
            status=STATUS_BAD_REQUEST,
        )

        assert "Could not parse as valid JSON" in resp.body

    def test_cycle_is_reported(self, app, preset_definition: dict):
        # "test-preset" starts with no base, and "a" bases on it, so both
        # currently resolve fine and "a" is a valid enum choice; previewing
        # "test-preset" based on "a" is what closes the loop
        scheming_factories.Preset(
            preset_name="test-preset", values=preset_definition["values"]
        )
        scheming_factories.Preset(preset_name="a", values={"preset": "test-preset"})

        definition = {**preset_definition, "values": {"preset": "a"}}

        resp = app.post(
            tk.url_for("scheming_dynamic_admin.preset_preview"),
            headers=_sysadmin_headers(),
            data={"definition": json.dumps(definition)},
            status=STATUS_BAD_REQUEST,
        )

        assert "cycle" in resp.body.lower()
