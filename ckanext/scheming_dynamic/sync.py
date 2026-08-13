from __future__ import annotations

import logging
from typing import Any

from flask import g, has_request_context
from sqlalchemy.exc import DBAPIError, UnboundExecutionError

import ckan.plugins.toolkit as tk
from ckan import model

from ckanext.scheming.plugins import _SchemingMixin
from ckanext.scheming_dynamic.model import (
    SchemingPreset,
    SchemingSchema,
    SchemingState,
)
from ckanext.scheming_dynamic.preset_resolve import (
    PresetBaseNotFoundError,
    PresetCycleError,
    resolve_preset_values,
)

log = logging.getLogger(__name__)


def dataset_schemas_if_changed(
    static_schemas: dict[str, Any],
) -> dict[str, Any] | None:
    """Return a copy of ``static_schemas`` overlaid with the database schemas.

    When the database changed since the last call, all dataset schemas are
    rebuilt from the file-defined ones overlaid with the database rows. The
    check runs at most once per request and once per worker process, which is
    how changes made in one worker propagate to the others.

    The fingerprint is only advanced once the caller confirms the merged
    schemas were applied successfully (see ``confirm_applied``) — otherwise a
    schema that fails to expand would never be retried until some unrelated
    write bumped the fingerprint again.
    """
    if _checked_in_this_request("scheming_dynamic_schema_checked"):
        return None

    # dataset fields can reference DB-defined presets: their expansion below
    # needs _SchemingMixin._presets to be current first.
    ensure_presets_synced()

    state = _SchemingMixin.dynamic_scheming["schema"]

    try:
        fingerprint = SchemingState.fingerprint("dataset")
    except (DBAPIError, UnboundExecutionError):
        model.Session.rollback()
        log.debug("cannot read the scheming_state table")
        return None

    if fingerprint == state["fingerprint"]:
        return None

    merged = dict(static_schemas)

    for row in SchemingSchema.get_schemas_of_type(entity_type="dataset"):
        merged[row.schema_type] = row.definition

    state["pending_fingerprint"] = fingerprint

    return merged


def confirm_applied() -> None:
    """Confirm a successful sync of the dynamic schemas.

    Record that the schemas from the last ``dataset_schemas_if_changed``
    call were successfully applied, so that unchanged database state isn't
    re-merged on the next check.

    Must not be called after a failed merge: the fingerprint would advance
    without the failing schema ever being retried.
    """
    state = _SchemingMixin.dynamic_scheming["schema"]
    state["fingerprint"] = state["pending_fingerprint"]


def get_static_presets() -> dict[str, dict[str, Any]]:
    """Return the file/config-registered presets, capturing them if needed."""
    ensure_presets_synced()
    return dict(_SchemingMixin.dynamic_scheming["preset"]["static"] or {})


def ensure_presets_synced() -> None:
    """Overlay the database presets onto ``_SchemingMixin._presets``.

    Mirrors ``dataset_schemas_if_changed``: runs at most once per
    request/worker check, keyed off the ``scheming_state`` row for the
    "preset" key. A preset whose base chain fails to resolve
    (cycle or missing base) is dropped and logged rather than breaking
    every other preset.
    """
    if _checked_in_this_request("scheming_dynamic_preset_checked"):
        return

    state = _SchemingMixin.dynamic_scheming["preset"]

    if state["static"] is None:
        state["static"] = dict(_SchemingMixin.get_presets(tk.config) or {})

    try:
        fingerprint = SchemingState.fingerprint(SchemingPreset.PRESET_STATE_ENTITY_TYPE)
    except (DBAPIError, UnboundExecutionError):
        model.Session.rollback()
        log.debug("cannot read the scheming_state table")
        return

    if fingerprint == state["fingerprint"]:
        return

    try:
        raw = {row.preset_name: row.values for row in SchemingPreset.get_all()}
    except (DBAPIError, UnboundExecutionError):
        model.Session.rollback()
        log.debug("cannot read the scheming_preset table")
        return

    merged = dict(state["static"])
    for name in raw:
        try:
            merged[name] = resolve_preset_values(name, raw, state["static"])
        except (PresetCycleError, PresetBaseNotFoundError):
            log.exception("dropping preset '%s': cannot resolve its base chain", name)

    _SchemingMixin._presets = merged
    state["fingerprint"] = fingerprint


def reset() -> None:
    """Forget cached fingerprints/snapshots, for test isolation."""
    _SchemingMixin.dynamic_scheming["schema"] = {
        "fingerprint": None,
        "pending_fingerprint": None,
    }
    _SchemingMixin.dynamic_scheming["preset"] = {"fingerprint": None, "static": None}
    _SchemingMixin._presets = None


def _checked_in_this_request(flag: str) -> bool:
    if not has_request_context():
        return False

    if g.get(flag):
        return True

    setattr(g, flag, True)
    return False
