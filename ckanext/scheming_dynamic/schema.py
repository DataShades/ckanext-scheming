from __future__ import annotations

from typing import Any

import ckan.plugins.toolkit as tk


class BaseSchema:
    """Base class for dataset, group, and organization schemas.

    Shared root keys (`about_url`, `about`, `scheming_version`) and all
    field-level $defs. Subclasses add the root keys specific to their
    schema type.
    """

    schema_id: str
    title: str
    description: str

    ANYTYPE = {"type": ["string", "number", "boolean", "object", "array", "null"]}

    I18N_TEXT = {
        "description": (
            "A label/help_text value: a plain string (translated via gettext), an "
            "object mapping language codes to strings, or null/empty for fields "
            "that render no visible label (e.g. a hidden field with a custom "
            "form_snippet). ckanext-scheming's scheming_language_text() helper "
            "explicitly treats any falsy value as ''."
        ),
        "oneOf": [
            {"type": "null"},
            {"type": "string"},
            {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": {"type": "string"},
            },
        ],
    }

    CHOICE = {
        "type": "object",
        "required": ["value"],
        "description": (
            "`label` is optional: ckanext-scheming's own "
            "scheming_choices_label() helper falls back to the value "
            "itself (c.get('label', value)) when a choice has no label."
        ),
        "properties": {
            "value": {"$ref": "#/$defs/anytype"},
            "label": {"$ref": "#/$defs/i18n_text"},
        },
        "additionalProperties": True,
    }

    FIELD = {
        "type": "object",
        "required": ["field_name"],
        "properties": {
            "field_name": {"type": "string", "minLength": 1},
            "label": {"$ref": "#/$defs/i18n_text"},
            "required": {"type": "boolean"},
            "default": {"$ref": "#/$defs/anytype"},
            "preset": {"$ref": "#/$defs/preset"},
            "help_text": {"$ref": "#/$defs/i18n_text"},
            "choices": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/choice"},
            },
        },
        "additionalProperties": True,
    }

    FIELD_LIST = {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/field"}}

    def build(self) -> dict[str, Any]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": self.schema_id,
            "title": self.title,
            "description": self.description,
            "type": "object",
            "required": self.required(),
            "properties": self.properties(),
            "additionalProperties": True,
            "$defs": self.defs(),
        }

    def required(self) -> list[str]:
        return ["about_url"]

    def properties(self) -> dict[str, Any]:
        return {
            "about_url": {"type": "string", "format": "uri", "minLength": 1},
            "about": {"type": "string"},
            "scheming_version": {"type": "integer"},
        }

    def defs(self) -> dict[str, Any]:
        return {
            "anytype": self.ANYTYPE,
            "i18n_text": self.I18N_TEXT,
            "choice": self.CHOICE,
            "preset": {
                "type": "string",
                "description": (
                    "Must be one of the presets registered at startup: the "
                    "built-in ckanext/scheming/presets.json plus any files "
                    "listed in the scheming.presets config option."
                ),
                "enum": self._registered_preset_names(),
            },
            "field": self.FIELD,
        }

    @staticmethod
    def _registered_preset_names() -> list[str]:
        """Return the names of all presets registered at startup.

        Preset names ckanext-scheming itself would accept: the presets
        loaded at startup from the scheming.presets config option.
        """
        from ckanext.scheming.plugins import _SchemingMixin  # noqa: PLC0415

        if _SchemingMixin._presets is None:
            _SchemingMixin._load_presets(tk.config)

        return sorted(_SchemingMixin._presets)  # type: ignore


class DatasetSchema(BaseSchema):
    schema_id = "https://github.com/ckan/ckanext-scheming/scheming_dynamic/dataset_schema.schema.json"
    title = "ckanext-scheming dataset schema"
    description = "Validates the minimal shape of a ckanext-scheming dataset schema file (YAML or JSON)"

    def required(self) -> list[str]:
        return super().required() + ["dataset_type", "dataset_fields", "resource_fields"]

    def properties(self) -> dict[str, Any]:
        return {
            **super().properties(),
            "dataset_type": {"type": "string", "minLength": 1},
            "dataset_fields": self.FIELD_LIST,
            "resource_fields": self.FIELD_LIST,
        }


class GroupSchema(BaseSchema):
    schema_id = "https://github.com/ckan/ckanext-scheming/scheming_dynamic/group_schema.schema.json"
    title = "ckanext-scheming group schema"
    description = "Validates the minimal shape of a ckanext-scheming group schema file (YAML or JSON)"

    def required(self) -> list[str]:
        return super().required() + ["group_type", "fields"]

    def properties(self) -> dict[str, Any]:
        return {
            **super().properties(),
            "group_type": {"type": "string", "minLength": 1},
            "fields": self.FIELD_LIST,
        }


class OrganisationSchema(BaseSchema):
    schema_id = "https://github.com/ckan/ckanext-scheming/scheming_dynamic/organization_schema.schema.json"
    title = "ckanext-scheming organization schema"
    description = "Validates the minimal shape of a ckanext-scheming organization schema file (YAML or JSON)"

    def required(self) -> list[str]:
        return super().required() + ["organization_type", "fields"]

    def properties(self) -> dict[str, Any]:
        return {
            **super().properties(),
            "organization_type": {"type": "string", "minLength": 1},
            "fields": self.FIELD_LIST,
        }


SCHEMA_TYPES: dict[str, type[BaseSchema]] = {
    "dataset": DatasetSchema,
    "group": GroupSchema,
    "organization": OrganisationSchema,
}
