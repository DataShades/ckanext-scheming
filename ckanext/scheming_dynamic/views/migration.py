from __future__ import annotations

from typing import Any

from flask import Blueprint
from flask.views import MethodView

import ckan.plugins.toolkit as tk
from ckan import model
from ckan.views.admin import before_request

from ckanext.scheming_dynamic.schema_migration import mapping as mapping_lib
from ckanext.scheming_dynamic.schema_migration.apply import expanded_definition
from ckanext.scheming_dynamic.schema_migration.diff import (
    CONSTANT,
    COPY,
    DATASET_GROUP,
    FIELD_GROUPS,
)

MIGRATION_BP = "scheming_dynamic_migration"

bp = Blueprint(MIGRATION_BP, __name__, url_prefix="/ckan-admin/scheming/migrations")


def index() -> str:
    return tk.render(
        "scheming_dynamic/migration/index.html",
        {
            "rows": tk.get_action("scheming_migration_status")({}, {}),
            "active_tab": "migrations",
        },
    )


class MappingView(MethodView):
    def get(
        self,
        schema_type: str,
        from_version: int,
        to_version: int,
        errors: list[str] | None = None,
    ) -> str:
        try:
            plan = _mapping_show(schema_type, from_version, to_version)
        except tk.ValidationError as e:
            return tk.abort(404, "; ".join(e.error_summary.values()))

        return tk.render(
            "scheming_dynamic/migration/mapping.html",
            {
                "plan": plan,
                "sources": _source_names(plan),
                "errors": errors or [],
                "active_tab": "migrations",
            },
        )

    def post(self, schema_type: str, from_version: int, to_version: int) -> Any:
        plan = _mapping_show(schema_type, from_version, to_version)

        try:
            tk.get_action("scheming_migration_mapping_update")(
                {},
                {
                    "schema_type": schema_type,
                    "from_version": from_version,
                    "to_version": to_version,
                    "mapping": _mapping_from_form(plan, tk.request.form),
                },
            )
        except tk.ValidationError as e:
            return self.get(
                schema_type, from_version, to_version, list(e.error_summary.values())
            )

        tk.h.flash_success(tk._("Mapping saved."))

        return tk.redirect_to(
            f"{MIGRATION_BP}.mapping",
            schema_type=schema_type,
            from_version=from_version,
            to_version=to_version,
        )


def apply_all(schema_type: str, from_version: int, to_version: int) -> Any:
    try:
        run = tk.get_action("scheming_migration_apply")(
            {},
            {
                "schema_type": schema_type,
                "from_version": from_version,
                "to_version": to_version,
                "dry_run": tk.request.form.get("dry_run") == "1",
            },
        )
    except tk.ValidationError as e:
        tk.h.flash_error("; ".join(e.error_summary.values()))
        return tk.redirect_to(
            f"{MIGRATION_BP}.mapping",
            schema_type=schema_type,
            from_version=from_version,
            to_version=to_version,
        )

    return tk.redirect_to(f"{MIGRATION_BP}.run", run_id=run["id"])


class DatasetView(MethodView):
    """Guided migration of a single dataset, asking only the open questions."""

    def get(
        self,
        schema_type: str,
        from_version: int,
        to_version: int,
        pkg_id: str,
        errors: dict[str, Any] | None = None,
    ) -> str:
        plan = _mapping_show(schema_type, from_version, to_version)

        return tk.render(
            "scheming_dynamic/migration/dataset.html",
            {
                "plan": plan,
                "dataset": tk.get_action("package_show")({}, {"id": pkg_id}),
                "questions": _open_questions(plan),
                "errors": errors or {},
                "licenses": model.Package.get_license_options(),
                "active_tab": "migrations",
            },
        )

    def post(
        self, schema_type: str, from_version: int, to_version: int, pkg_id: str
    ) -> Any:
        plan = _mapping_show(schema_type, from_version, to_version)
        questions = _open_questions(plan)

        values = {
            DATASET_GROUP: {
                field["field_name"]: tk.request.form.get(field["field_name"], "")
                for field in questions
            }
        }

        try:
            run = tk.get_action("scheming_migration_apply")(
                {},
                {
                    "schema_type": schema_type,
                    "from_version": from_version,
                    "to_version": to_version,
                    "id": pkg_id,
                    "values": values,
                },
            )
        except tk.ValidationError as e:
            return self.get(schema_type, from_version, to_version, pkg_id, e.error_dict)

        item = tk.get_action("scheming_migration_run_show")({}, {"id": run["id"]})[
            "items"
        ][0]

        if item["status"] != "ok":
            return self.get(schema_type, from_version, to_version, pkg_id, item["errors"])

        tk.h.flash_success(tk._("Dataset migrated to version {}.").format(to_version))
        return tk.redirect_to(f"{MIGRATION_BP}.run", run_id=run["id"])


def _open_questions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """The target fields this dataset still has to answer, with their schema."""
    deferred = {
        problem["field_name"]
        for problem in mapping_lib.manual_fields(plan["mapping"]) + plan["unresolved"]
        if problem["group"] == DATASET_GROUP
    }

    target = expanded_definition(
        plan["entity_type"], plan["schema_type"], plan["to_version"]
    )
    by_name = {f["field_name"]: f for f in target.get(DATASET_GROUP, [])}

    return [by_name[name] for name in sorted(deferred) if name in by_name]


def runs() -> str:
    return tk.render(
        "scheming_dynamic/migration/runs.html",
        {
            "runs": tk.get_action("scheming_migration_run_list")({}, {}),
            "active_tab": "migrations",
        },
    )


def run(run_id: str) -> str:
    try:
        data = tk.get_action("scheming_migration_run_show")({}, {"id": run_id})
    except tk.ObjectNotFound:
        return tk.abort(404, tk._("Migration run not found"))

    return tk.render(
        "scheming_dynamic/migration/run.html",
        {"run": data, "active_tab": "migrations"},
    )


def cancel(run_id: str) -> Any:
    try:
        tk.get_action("scheming_migration_run_cancel")({}, {"id": run_id})
    except tk.ValidationError as e:
        tk.h.flash_error("; ".join(e.error_summary.values()))
    else:
        tk.h.flash_success(tk._("Migration cancelled."))

    return tk.redirect_to(f"{MIGRATION_BP}.run", run_id=run_id)


def _mapping_show(
    schema_type: str, from_version: int, to_version: int
) -> dict[str, Any]:
    return tk.get_action("scheming_migration_mapping_show")(
        {},
        {
            "schema_type": schema_type,
            "from_version": from_version,
            "to_version": to_version,
        },
    )


def _source_names(plan: dict[str, Any]) -> dict[str, list[str]]:
    """Field names available as a copy source, per group."""
    names = {}

    for group in FIELD_GROUPS:
        group_diff = plan["diff"][group]
        carried = {
            change["source"] for change in group_diff["fields"] if change["source"]
        }
        names[group] = sorted(carried | set(group_diff["dropped"]))

    return names


def _mapping_from_form(plan: dict[str, Any], form: Any) -> dict[str, Any]:
    """Overlay the admin's decisions onto the auto-derived suggestion."""
    mapping = {group: dict(plan["suggested"].get(group, {})) for group in FIELD_GROUPS}
    mapping["dropped"] = {
        group: form.getlist(f"dropped.{group}") for group in FIELD_GROUPS
    }

    for group in FIELD_GROUPS:
        for change in plan["diff"][group]["fields"]:
            entry = _entry_from_form(group, change, form)
            if entry:
                mapping[group][change["field_name"]] = entry

    return mapping


def _entry_from_form(
    group: str, change: dict[str, Any], form: Any
) -> dict[str, Any] | None:
    field_name = change["field_name"]
    prefix = f"field.{group}.{field_name}"

    action = form.get(f"{prefix}.action")
    if not action:
        return None

    entry: dict[str, Any] = {"action": action}

    if action == COPY:
        entry["source"] = form.get(f"{prefix}.source") or field_name
        value_map = {
            value: form.get(f"{prefix}.value_map.{value}")
            for value in change["lost_choices"]
            if form.get(f"{prefix}.value_map.{value}")
        }
        if value_map:
            entry["value_map"] = value_map

    if action == CONSTANT:
        entry["value"] = form.get(f"{prefix}.value", "")

    return entry


bp.before_request(before_request)
bp.add_url_rule("/", view_func=index)
bp.add_url_rule("/runs", view_func=runs)
bp.add_url_rule("/runs/<run_id>", view_func=run)
bp.add_url_rule("/runs/<run_id>/cancel", view_func=cancel, methods=["POST"])
bp.add_url_rule(
    "/<schema_type>/<int:from_version>/<int:to_version>",
    view_func=MappingView.as_view("mapping"),
)
bp.add_url_rule(
    "/<schema_type>/<int:from_version>/<int:to_version>/apply",
    view_func=apply_all,
    methods=["POST"],
)
bp.add_url_rule(
    "/<schema_type>/<int:from_version>/<int:to_version>/dataset/<id>",
    view_func=DatasetView.as_view("dataset"),
)
