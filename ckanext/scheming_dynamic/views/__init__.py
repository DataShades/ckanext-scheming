"""Catch-all dataset routes for schema types created at runtime.

CKAN registers one blueprint per dataset type at startup, named after the
type (that is also what makes ``url_for("<type>.read")`` work). A type
created in the database after startup has no such blueprint, so:

- two catch-all blueprints with a ``/<package_type>`` prefix serve its
  pages. Static blueprint prefixes always win in werkzeug routing, so these
  only receive types that got no dedicated blueprint at startup. Types
  without a matching database schema get a 404.
- a Flask ``url_build_error_handler`` rebuilds ``url_for("<type>.read")``
  style calls through the catch-all blueprints.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint
from flask import url_for as flask_url_for
from sqlalchemy.exc import DBAPIError
from werkzeug.routing import BuildError

import ckan.plugins.toolkit as tk
from ckan import model, types
from ckan.views.dataset import dataset, register_dataset_plugin_rules
from ckan.views.resource import (
    register_dataset_plugin_rules as register_resource_rules,
)
from ckan.views.resource import resource

from ckanext.scheming.plugins import SchemingDatasetsPlugin
from ckanext.scheming.views import add_paged_form_rules
from ckanext.scheming_dynamic.model import SchemingSchemaVersion

from .admin import bp as admin_bp
from .migration import bp as migration_bp

DATASET_BP = "scheming_dynamic"
RESOURCE_BP = "scheming_dynamic_resource"


def get_blueprints() -> list[Blueprint]:
    dataset_bp = Blueprint(
        DATASET_BP, dataset.import_name, url_prefix="/<package_type>"
    )
    add_paged_form_rules(dataset_bp)
    register_dataset_plugin_rules(dataset_bp)
    dataset_bp.before_request(_dynamic_type_or_404)

    resource_bp = Blueprint(
        RESOURCE_BP, resource.import_name, url_prefix="/<package_type>/<id>/resource"
    )
    register_resource_rules(resource_bp)
    resource_bp.before_request(_dynamic_type_or_404)

    return [dataset_bp, resource_bp, admin_bp, migration_bp]


def build_dynamic_type_url(
    app: types.CKANApp,
    error: BuildError,
    endpoint: str,
    values: dict[str, Any],
) -> str | None:
    """Rebuild dataset URLs for types that exist only in the database.

    Registered as a Flask url_build_error_handler: returning None re-raises
    the original BuildError.
    """
    name, _, view = endpoint.partition(".")

    if not view or name in app.blueprints:
        return None

    # `name` is ambiguous when a dataset type itself ends in "_resource"
    # (e.g. "water_resource.read" could be the dataset type "water_resource"
    # or the resource blueprint for type "water"): try it as a dataset type
    # first, since that's the type actually registered in the database.
    if _dynamic_schema_exists(name):
        return flask_url_for(f"{DATASET_BP}.{view}", **{**values, "package_type": name})

    if name.endswith("_resource"):
        package_type = name[: -len("_resource")]
        if _dynamic_schema_exists(package_type):
            return flask_url_for(
                f"{RESOURCE_BP}.{view}", **{**values, "package_type": package_type}
            )

    return None


def _dynamic_schema_exists(package_type: str) -> bool:
    # An unsaved schema being previewed (admin.py:preview) has no database
    # row yet, so it needs this escape hatch to still resolve its own URLs.
    if package_type == getattr(tk.g, "scheming_dynamic_preview_type", None):
        return True

    try:
        with model.Session.begin_nested():
            return SchemingSchemaVersion.head_version("dataset", package_type) > 0
    except DBAPIError:
        return False


def _dynamic_type_or_404() -> None:
    view_args = tk.request.view_args or {}
    package_type = view_args.get("package_type")

    if not package_type or not SchemingSchemaVersion.head_version(
        "dataset", package_type
    ):
        tk.abort(404, tk._("Dataset type not found"))

    _sync_scheming_datasets_plugin()


def _sync_scheming_datasets_plugin() -> None:
    """Force SchemingDatasetsPlugin to claim this request's package_type.

    ``ckan.views.dataset`` resolves the form/template plugin via
    ``lookup_package_plugin(package_type)`` as one of the very first things
    it does (e.g. building the ``package_form`` snippet), which reads a
    dict SchemingDatasetsPlugin only updates as a side effect of its own
    lazy DB sync (``SchemingDatasetsPlugin._schemas``/``_expanded_schemas``).
    Nothing else guarantees that sync has run yet on a freshly created
    type's very first request in a worker -- without this, that request
    still sees the default IDatasetForm/templates.
    """
    plugin = SchemingDatasetsPlugin.instance

    if plugin is not None:
        plugin._sync_dynamic_schemas()
