from __future__ import annotations

import json
from typing import Any

from flask import Blueprint
from flask.views import MethodView

import ckan.plugins.toolkit as tk
from ckan import model

from ckanext.scheming.plugins import _expand_schemas
from ckanext.scheming_dynamic.logic.schema import DEFAULT_ENTITY_TYPE
from ckanext.scheming_dynamic.model import SchemingSchema
from ckanext.scheming_dynamic.schema import ENTITY_TYPES
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
    return ENTITY_TYPES[DEFAULT_ENTITY_TYPE]().build()


def index() -> str:
    return tk.render(
        "scheming_dynamic/index.html",
        {"schemas": SchemingSchema.get_schemas_of_type(DEFAULT_ENTITY_TYPE)},
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
        for e in iter_errors(definition, ENTITY_TYPES[DEFAULT_ENTITY_TYPE]())
    ]
    if errors:
        return _preview_errors(errors)

    # expand presets the same way scheming does for registered schemas, so
    # the preview uses the exact form snippets the real dataset form will
    dataset_type = definition["dataset_type"]
    expanded = _expand_schemas({dataset_type: definition})[dataset_type]

    return tk.render(
        "scheming_dynamic/snippets/schema_preview.html",
        {
            "schema": expanded,
            "licenses": model.Package.get_license_options(),
        },
    )


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


bp.before_request(_sysadmin_or_403)
bp.add_url_rule("/", view_func=index)
bp.add_url_rule("/new", view_func=CreateView.as_view("new"))
bp.add_url_rule("/<schema_type>/edit", view_func=EditView.as_view("edit"))
bp.add_url_rule("/<schema_type>/delete", view_func=delete, methods=["POST"])
bp.add_url_rule("/preview", view_func=preview, methods=["POST"])
