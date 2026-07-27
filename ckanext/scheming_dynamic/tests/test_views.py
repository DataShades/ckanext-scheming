from __future__ import annotations

import pytest

from ckan.tests import factories, helpers

STATUS_OK = 200
DEFINITION = {
    "about_url": "https://example.com",
    "dataset_type": "test-type",
    "dataset_fields": [{"field_name": "custom_title", "label": "Custom title"}],
    "resource_fields": [{"field_name": "url"}],
}


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets scheming_dynamic")
@pytest.mark.ckan_config("scheming.dataset_schemas", "ckanext.scheming:ckan_dataset.yaml")
@pytest.mark.ckan_config("scheming.dataset_fallback", "true")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestDynamicTypeRoutes:
    def test_unknown_type_is_not_found(self, app):
        app.get("/no-such-type/new", status=404)

    def test_dynamic_type_new_form_renders(self, app):
        user = factories.SysadminWithToken()
        helpers.call_action(
            "scheming_schema_create",
            schema_type="test-type",
            definition=DEFINITION,
        )

        resp = app.get("/test-type/new", headers={"Authorization": user["token"]})

        assert resp.status_code == STATUS_OK
        assert "custom_title" in resp.body

    def test_updated_schema_is_rendered_without_restart(self, app):
        user = factories.SysadminWithToken()
        helpers.call_action(
            "scheming_schema_create",
            schema_type="test-type",
            definition=DEFINITION,
        )
        app.get("/test-type/new", headers={"Authorization": user["token"]})

        updated = {
            **DEFINITION,
            "dataset_fields": [{"field_name": "renamed_field"}],
        }
        helpers.call_action(
            "scheming_schema_update",
            schema_type="test-type",
            definition=updated,
        )

        resp = app.get("/test-type/new", headers={"Authorization": user["token"]})

        assert resp.status_code == STATUS_OK
        assert "renamed_field" in resp.body

    def test_deleted_type_stops_being_served(self, app):
        user = factories.SysadminWithToken()
        helpers.call_action(
            "scheming_schema_create",
            schema_type="test-type",
            definition=DEFINITION,
        )
        helpers.call_action("scheming_schema_delete", schema_type="test-type")

        app.get(
            "/test-type/new",
            headers={"Authorization": user["token"]},
            status=404,
        )
