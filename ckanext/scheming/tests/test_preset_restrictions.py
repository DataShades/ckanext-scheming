import pytest

from ckanext.scheming.errors import SchemingException
from ckanext.scheming.plugins import _SchemingMixin, _expand_schemas


class TestExpandReloadsPresets:
    def test_expand_schemas_reloads_presets_when_cache_was_cleared(self):
        # `plugins_update()` and `sync.reset()` null this cache for a lazy
        # reload; `_expand_schemas` used to crash on the None instead of reloading.
        _SchemingMixin._presets = None
        try:
            result = _expand_schemas(
                {
                    "test-type": {
                        "dataset_type": "test-type",
                        "dataset_fields": [
                            {"field_name": "title", "preset": "title"}
                        ],
                    }
                }
            )
        finally:
            _SchemingMixin._presets = None

        field = result["test-type"]["dataset_fields"][0]
        assert field["form_snippet"] == "large_text.html"


class TestRestrictToField:
    @pytest.mark.parametrize(
        ("preset", "field_name"),
        [
            ("title", "title"),
            ("dataset_slug", "name"),
            ("tag_string_autocomplete", "tag_string"),
            ("dataset_organization", "owner_org"),
        ],
    )
    def test_allowed_on_its_own_dataset_field(self, preset, field_name):
        _expand_dataset_field({"field_name": field_name, "preset": preset})

    @pytest.mark.parametrize(
        ("preset", "field_name"),
        [
            ("title", "title"),
            ("dataset_slug", "name"),
            ("tag_string_autocomplete", "tag_string"),
            ("dataset_organization", "owner_org"),
        ],
    )
    def test_rejected_on_a_different_dataset_field(self, preset, field_name):
        field = {"field_name": "not_" + field_name, "preset": preset}
        with pytest.raises(SchemingException):
            _expand_dataset_field(field)

    @pytest.mark.parametrize(
        ("preset", "field_name"),
        [("resource_url_upload", "url"), ("resource_format_autocomplete", "format")],
    )
    def test_allowed_on_its_own_resource_field(self, preset, field_name):
        _expand_resource_field({"field_name": field_name, "preset": preset})

    @pytest.mark.parametrize(
        ("preset", "field_name"),
        [("resource_url_upload", "url"), ("resource_format_autocomplete", "format")],
    )
    def test_rejected_on_a_different_resource_field(self, preset, field_name):
        field = {"field_name": "not_" + field_name, "preset": preset}
        with pytest.raises(SchemingException):
            _expand_resource_field(field)

    def test_resource_preset_rejected_on_matching_dataset_field_name(self):
        # same field_name, wrong entity_type
        field = {"field_name": "url", "preset": "resource_url_upload"}
        with pytest.raises(SchemingException):
            _expand_dataset_field(field)

    def test_organization_url_upload_allowed_on_organization_image_url(self):
        field = {"field_name": "image_url", "preset": "organization_url_upload"}
        _expand_organization_field(field)

    def test_organization_url_upload_rejected_on_group_image_url(self):
        # same field_name, wrong entity_type
        field = {"field_name": "image_url", "preset": "organization_url_upload"}
        with pytest.raises(SchemingException):
            _expand_group_field(field)

    def test_organization_url_upload_rejected_on_different_organization_field(self):
        field = {"field_name": "logo", "preset": "organization_url_upload"}
        with pytest.raises(SchemingException):
            _expand_organization_field(field)


def _expand_dataset_field(field, resource_fields=None):
    _expand_schemas(
        {
            "test-type": {
                "dataset_type": "test-type",
                "dataset_fields": [field],
                "resource_fields": resource_fields or [],
            }
        }
    )


def _expand_resource_field(field):
    _expand_dataset_field({"field_name": "unrelated"}, resource_fields=[field])


def _expand_organization_field(field):
    _expand_schemas(
        {"test-org-type": {"organization_type": "test-org-type", "fields": [field]}}
    )


def _expand_group_field(field):
    _expand_schemas(
        {"test-group-type": {"group_type": "test-group-type", "fields": [field]}}
    )


class TestRequiresOneOf:
    @pytest.mark.parametrize(
        "preset", ["select", "multiple_checkbox", "multiple_select", "radio"]
    )
    def test_rejected_without_choices_or_choices_helper(self, preset):
        with pytest.raises(SchemingException):
            _expand_dataset_field({"field_name": "category", "preset": preset})

    @pytest.mark.parametrize(
        "preset", ["select", "multiple_checkbox", "multiple_select", "radio"]
    )
    def test_allowed_with_choices(self, preset):
        _expand_dataset_field(
            {
                "field_name": "category",
                "preset": preset,
                "choices": [{"value": "a", "label": "A"}],
            }
        )

    @pytest.mark.parametrize(
        "preset", ["select", "multiple_checkbox", "multiple_select", "radio"]
    )
    def test_allowed_with_choices_helper(self, preset):
        _expand_dataset_field(
            {
                "field_name": "category",
                "preset": preset,
                "choices_helper": "some_helper",
            }
        )
