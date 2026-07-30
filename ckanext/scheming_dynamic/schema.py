from __future__ import annotations

from pathlib import Path
from typing import Any

import ckan.plugins.toolkit as tk

import ckanext.scheming


class BaseSchema:
    """Base class for dataset, group, and organization schemas.

    Shared root keys (`about`) and all field-level $defs. Subclasses
    add the root keys specific to their schema type.
    """

    schema_id: str
    title: str
    description: str

    ANYTYPE = {"type": ["string", "number", "boolean", "object", "array", "null"]}

    I18N_TEXT = {
        "title": tk._("Label"),
        "description": tk._(
            "A label/help_text value: a plain string (translated via gettext), an "
            "object mapping language codes to strings, or null/empty for fields "
            "that render no visible label (e.g. a hidden field with a custom "
            "form_snippet). ckanext-scheming's scheming_language_text() helper "
            "explicitly treats any falsy value as ''."
        ),
        "oneOf": [
            {"title": tk._("Text"), "type": "string"},
            {
                "title": tk._("Translations (language code to text)"),
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
            {"title": tk._("No label"), "type": "null"},
        ],
    }

    CHOICE = {
        "type": "object",
        "required": ["value"],
        "properties": {
            "value": {"type": "string"},
            "label": {"$ref": "#/$defs/i18n_text"},
        },
        "additionalProperties": True,
    }

    FIELD = {
        "type": "object",
        "title": tk._("Field"),
        "required": ["field_name"],
        "properties": {
            "field_name": {
                "type": "string",
                "minLength": 1,
                "title": tk._("Field name"),
            },
            "label": {"$ref": "#/$defs/i18n_text", "title": tk._("Label")},
            "required": {"type": "boolean", "title": tk._("Required")},
            "default": {"$ref": "#/$defs/anytype", "title": tk._("Default")},
            "preset": {"$ref": "#/$defs/preset", "title": tk._("Preset")},
            "form_snippet": {
                "$ref": "#/$defs/form_snippet",
                "title": tk._("Form snippet"),
            },
            "display_snippet": {
                "$ref": "#/$defs/display_snippet",
                "title": tk._("Display snippet"),
            },
            "help_text": {"$ref": "#/$defs/i18n_text", "title": tk._("Help text")},
            "form_placeholder": {
                "$ref": "#/$defs/i18n_text",
                "title": tk._("Form placeholder"),
            },
            "choices": {
                "type": "array",
                "items": {"$ref": "#/$defs/choice"},
                "title": tk._("Choices"),
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
            "options": {"disable_collapse": True},
            "required": self.required(),
            "properties": self.properties(),
            "additionalProperties": True,
            "$defs": self.defs(),
        }

    def required(self) -> list[str]:
        return ["about"]

    def properties(self) -> dict[str, Any]:
        return {
            "about": {"type": "string", "title": tk._("About"), "minLength": 1},
        }

    def defs(self) -> dict[str, Any]:
        return {
            "anytype": self.ANYTYPE,
            "i18n_text": self.I18N_TEXT,
            "choice": self.CHOICE,
            "preset": {
                "type": "string",
                "description": tk._(
                    "Must be one of the presets registered at startup via "
                    "the scheming.presets config option."
                ),
                "enum": self._registered_preset_names(),
            },
            "form_snippet": {
                "description": tk._(
                    "Form snippet rendered for the field: one of the "
                    "scheming/form_snippets/*.html templates available in "
                    "the registered template directories, or null to hide "
                    "the field from forms."
                ),
                "oneOf": [
                    {
                        "title": "Snippet template",
                        "type": "string",
                        "enum": self._available_snippets("form_snippets"),
                    },
                    {"title": "Hide field from forms", "type": "null"},
                ],
            },
            "display_snippet": {
                "description": tk._(
                    "Display snippet rendered for the field: one of the "
                    "scheming/display_snippets/*.html templates available "
                    "in the registered template directories, or null to "
                    "hide the field from display pages."
                ),
                "oneOf": [
                    {
                        "title": "Snippet template",
                        "type": "string",
                        "enum": self._available_snippets("display_snippets"),
                    },
                    {"title": "Hide field from display pages", "type": "null"},
                ],
            },
            "field": self.FIELD,
        }

    @staticmethod
    def _available_snippets(kind: str) -> list[str]:
        """Get the names of snippets available for the given kind.

        Return the names of scheming/<kind>/*.html templates found in
        every registered template directory.

        Falls back to ckanext-scheming's own templates when the app config
        is not available (e.g. building the schema outside a CKAN app).
        Underscore-prefixed templates are partials included by other
        snippets and are not offered.
        """
        template_dirs = list(tk.config.get("computed_template_paths") or [])
        template_dirs.append(str(Path(ckanext.scheming.__file__).parent / "templates"))

        names = {
            path.name
            for directory in template_dirs
            for path in Path(directory, "scheming", kind).glob("*.html")
            if not path.name.startswith("_")
        }
        return sorted(names)

    @staticmethod
    def _registered_preset_names() -> list[str]:
        """Return the names of all presets registered at startup.

        Preset names ckanext-scheming itself would accept: the presets
        loaded at startup from the scheming.presets config option.
        """
        from ckanext.scheming.plugins import _SchemingMixin  # noqa: PLC0415

        return sorted(_SchemingMixin.get_presets(tk.config))


class DatasetSchema(BaseSchema):
    schema_id = "https://github.com/ckan/ckanext-scheming/scheming_dynamic/dataset_schema.schema.json"
    title = "ckanext-scheming dataset schema"
    description = "Validates the minimal shape of a ckanext-scheming dataset schema file (YAML or JSON)"

    def required(self) -> list[str]:
        return super().required() + [
            "dataset_type",
            "dataset_fields",
            "resource_fields",
        ]

    def properties(self) -> dict[str, Any]:
        return {
            **super().properties(),
            "dataset_type": {
                "type": "string",
                "title": tk._("Dataset type"),
                "minLength": 1,
            },
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


class OrganizationSchema(BaseSchema):
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


ENTITY_TYPES: dict[str, type[BaseSchema]] = {
    "dataset": DatasetSchema,
    "group": GroupSchema,
    "organization": OrganizationSchema,
}
