from __future__ import annotations

import json
from typing import Any

from flask import Blueprint
from flask.views import MethodView

import ckan.plugins.toolkit as tk

from ckanext.scheming_dynamic.logic.schema import DEFAULT_ENTITY_TYPE
from ckanext.scheming_dynamic.model import SchemingPreset, SchemingSchema
from ckanext.scheming_dynamic.preset_resolve import (
    PresetBaseNotFoundError,
    PresetCycleError,
)
from ckanext.scheming_dynamic.render import render_preset_field, render_schema_form
from ckanext.scheming_dynamic.schema import SCHEMA_CLASSES, PresetSchema
from ckanext.scheming_dynamic.validator import error_location, iter_errors

ADMIN_BP = "scheming_dynamic_admin"


bp = Blueprint(ADMIN_BP, __name__, url_prefix="/ckan-admin/scheming")


def _sysadmin_or_403() -> None:
    try:
        tk.check_access("sysadmin", _action_context())
    except tk.NotAuthorized:
        tk.abort(403, tk._("Need to be system administrator to administer"))


def _action_context() -> Any:
    return {"user": tk.current_user.name, "auth_user_obj": tk.current_user}


def _meta_schema() -> dict[str, Any]:
    return SCHEMA_CLASSES[DEFAULT_ENTITY_TYPE]().build()


def _preset_meta_schema(exclude_preset_name: str | None = None) -> dict[str, Any]:
    return PresetSchema(exclude_preset_name=exclude_preset_name).build()


def index() -> str:
    return tk.render(
        "scheming_dynamic/index.html",
        {
            "schemas": SchemingSchema.get_schemas_of_type(DEFAULT_ENTITY_TYPE),
            "active_tab": "schemas",
        },
    )


class CreateView(MethodView):
    def get(
        self,
        data: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
        error_summary: dict[str, Any] | None = None,
    ) -> str:
        return tk.render(
            "scheming_dynamic/schema_form.html",
            {
                "data": data or {},
                "errors": errors or {},
                "error_summary": error_summary or {},
                "meta_schema": _meta_schema(),
                "is_new": True,
            },
        )

    def post(self) -> str | Any:
        data = {
            "definition": tk.request.form.get("definition", ""),
        }

        try:
            row = tk.get_action("scheming_schema_create")(_action_context(), dict(data))
        except tk.ValidationError as e:
            return self.get(data, e.error_dict, e.error_summary)

        tk.h.flash_success(tk._("Schema '{}' created.").format(row["schema_type"]))
        return tk.redirect_to(f"{ADMIN_BP}.index")


class EditView(MethodView):
    def get(
        self,
        schema_type: str,
        data: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
        error_summary: dict[str, Any] | None = None,
    ) -> str:
        schema = SchemingSchema.get(DEFAULT_ENTITY_TYPE, schema_type)
        if not schema:
            return tk.abort(404, tk._("Schema not found"))

        if data is None:
            data = {
                "schema_type": schema_type,
                "definition": json.dumps(schema.definition, indent=2),
            }

        return tk.render(
            "scheming_dynamic/schema_form.html",
            {
                "data": data,
                "errors": errors or {},
                "error_summary": error_summary or {},
                "meta_schema": _meta_schema(),
                "is_new": False,
                "schema_type": schema_type,
            },
        )

    def post(self, schema_type: str) -> str | Any:
        data = {
            "schema_type": schema_type,
            "definition": tk.request.form.get("definition", ""),
        }

        try:
            tk.get_action("scheming_schema_update")(_action_context(), dict(data))
        except tk.ObjectNotFound:
            return tk.abort(404, tk._("Schema not found"))
        except tk.ValidationError as e:
            return self.get(schema_type, data, e.error_dict, e.error_summary)

        tk.h.flash_success(tk._("Schema '{}' updated.").format(schema_type))
        return tk.redirect_to(f"{ADMIN_BP}.index")


def preview() -> Any:
    """Render unsaved schema definition as a preview.

    Returns an HTML fragment: either the rendered form fields or the list
    of validation errors (with a 400 status) when the definition cannot be
    rendered.
    """
    raw = tk.request.form.get("definition", "")

    try:
        definition = json.loads(raw)
    except ValueError:
        return _preview_errors([tk._("Could not parse as valid JSON")])

    errors = [
        f"{error_location(e)}: {e.message}"
        for e in iter_errors(definition, SCHEMA_CLASSES[DEFAULT_ENTITY_TYPE]())
    ]
    if errors:
        return _preview_errors(errors)

    # TODO: works for dataset schemas only
    dataset_type = definition["dataset_type"]

    try:
        return render_schema_form(dataset_type, definition)
    except Exception as e:  # noqa: BLE001
        return _preview_errors([tk._("Schema cannot be rendered: {}").format(e)])


def _preview_errors(messages: list[str]) -> Any:
    body = tk.render(
        "scheming_dynamic/snippets/schema_preview.html",
        {"preview_errors": messages},
    )
    return body, 400


def delete(schema_type: str) -> Any:
    try:
        tk.get_action("scheming_schema_delete")(
            _action_context(), {"schema_type": schema_type}
        )
    except tk.ValidationError as e:
        tk.h.flash_error("; ".join(e.error_summary.values()))
    else:
        tk.h.flash_success(tk._("Schema '{}' has been deleted.").format(schema_type))

    return tk.redirect_to(f"{ADMIN_BP}.index")


def presets_index() -> str:
    return tk.render(
        "scheming_dynamic/presets_index.html",
        {"presets": SchemingPreset.get_all(), "active_tab": "presets"},
    )


class PresetCreateView(MethodView):
    def get(
        self,
        data: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
        error_summary: dict[str, Any] | None = None,
    ) -> str:
        return tk.render(
            "scheming_dynamic/preset_form.html",
            {
                "data": data or {},
                "errors": errors or {},
                "error_summary": error_summary or {},
                "meta_schema": _preset_meta_schema(),
                "is_new": True,
            },
        )

    def post(self) -> str | Any:
        data = {
            "definition": tk.request.form.get("definition", ""),
        }

        try:
            row = tk.get_action("scheming_preset_create")(_action_context(), dict(data))
        except tk.ValidationError as e:
            return self.get(data, e.error_dict, e.error_summary)

        tk.h.flash_success(tk._("Preset '{}' created.").format(row["preset_name"]))
        return tk.redirect_to(f"{ADMIN_BP}.presets_index")


class PresetEditView(MethodView):
    def get(
        self,
        preset_name: str,
        data: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
        error_summary: dict[str, Any] | None = None,
    ) -> str:
        preset = SchemingPreset.get(preset_name)
        if not preset:
            return tk.abort(404, tk._("Preset not found"))

        if data is None:
            data = {
                "preset_name": preset_name,
                "definition": json.dumps(
                    {"preset_name": preset.preset_name, "values": preset.values},
                    indent=2,
                ),
            }

        return tk.render(
            "scheming_dynamic/preset_form.html",
            {
                "data": data,
                "errors": errors or {},
                "error_summary": error_summary or {},
                "meta_schema": _preset_meta_schema(exclude_preset_name=preset_name),
                "is_new": False,
                "preset_name": preset_name,
            },
        )

    def post(self, preset_name: str) -> str | Any:
        data = {
            "preset_name": preset_name,
            "definition": tk.request.form.get("definition", ""),
        }

        try:
            tk.get_action("scheming_preset_update")(_action_context(), dict(data))
        except tk.ObjectNotFound:
            return tk.abort(404, tk._("Preset not found"))
        except tk.ValidationError as e:
            return self.get(preset_name, data, e.error_dict, e.error_summary)

        tk.h.flash_success(tk._("Preset '{}' updated.").format(preset_name))
        return tk.redirect_to(f"{ADMIN_BP}.presets_index")


def preset_preview() -> Any:
    """Render an unsaved preset definition as a preview.

    Treats the preset's ``values`` as a single field (synthesizing a
    ``field_name`` when the preset doesn't supply its own), resolving any
    base preset chain, then renders it with the same form snippet a real
    dataset/resource field using this preset would get.

    Returns an HTML fragment: either the rendered field or the list of
    validation errors (with a 400 status) when the definition cannot be
    rendered.
    """
    raw = tk.request.form.get("definition", "")

    try:
        definition = json.loads(raw)
    except ValueError:
        return _preset_preview_errors([tk._("Could not parse as valid JSON")])

    errors = [
        f"{error_location(e)}: {e.message}"
        for e in iter_errors(definition, PresetSchema())
    ]
    if errors:
        return _preset_preview_errors(errors)

    preset_name = definition["preset_name"]

    try:
        return render_preset_field(preset_name, definition["values"])
    except PresetCycleError as e:
        return _preset_preview_errors(
            [
                tk._("Preset cycle detected: {}").format(
                    " -> ".join([*e.chain, e.chain[0]])
                )
            ]
        )
    except PresetBaseNotFoundError as e:
        return _preset_preview_errors(
            [tk._(f"Base preset '{e.base}' is not a registered or existing preset")]
        )
    except Exception as e:  # noqa: BLE001
        return _preset_preview_errors(
            [tk._("Form snippet failed to render: {}").format(e)]
        )


def _preset_preview_errors(messages: list[str]) -> Any:
    body = tk.render(
        "scheming_dynamic/snippets/preset_preview.html",
        {"preview_errors": messages},
    )
    return body, 400


def preset_delete(preset_name: str) -> Any:
    try:
        tk.get_action("scheming_preset_delete")(
            _action_context(), {"preset_name": preset_name}
        )
    except tk.ValidationError as e:
        tk.h.flash_error("; ".join(e.error_summary.values()))
    else:
        tk.h.flash_success(tk._("Preset '{}' has been deleted.").format(preset_name))

    return tk.redirect_to(f"{ADMIN_BP}.presets_index")


bp.before_request(_sysadmin_or_403)
bp.add_url_rule("/", view_func=index)
bp.add_url_rule("/new", view_func=CreateView.as_view("new"))
bp.add_url_rule("/<schema_type>/edit", view_func=EditView.as_view("edit"))
bp.add_url_rule("/<schema_type>/delete", view_func=delete, methods=["POST"])
bp.add_url_rule("/preview", view_func=preview, methods=["POST"])
bp.add_url_rule("/presets/", view_func=presets_index)
bp.add_url_rule("/presets/new", view_func=PresetCreateView.as_view("preset_new"))
bp.add_url_rule(
    "/presets/<preset_name>/edit", view_func=PresetEditView.as_view("preset_edit")
)
bp.add_url_rule(
    "/presets/<preset_name>/delete", view_func=preset_delete, methods=["POST"]
)
bp.add_url_rule("/presets/preview", view_func=preset_preview, methods=["POST"])
