from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flask import g, has_request_context
from sqlalchemy.exc import DBAPIError, UnboundExecutionError

from ckan import model

from ckanext.scheming.plugins import _SchemingMixin
from ckanext.scheming_dynamic.model import SchemingSchema, SchemingSchemaState

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
    if _checked_in_this_request():
        return None

    try:
        fingerprint = _current_fingerprint()
    except (DBAPIError, UnboundExecutionError):
        model.Session.rollback()
        log.debug("cannot read the scheming_schema_state table")
        return None

    if fingerprint == _SchemingMixin._fingerprint:
        return None

    merged = dict(static_schemas)

    for row in SchemingSchema.get_schemas_of_type(entity_type="dataset"):
        merged[row.schema_type] = row.definition

    _SchemingMixin._pending_fingerprint = fingerprint

    return merged


def confirm_applied() -> None:
    """Confirm a successful sync of the dynamic schemas.

    Record that the schemas from the last ``dataset_schemas_if_changed``
    call were successfully applied, so that unchanged database state isn't
    re-merged on the next check.

    Must not be called after a failed merge: the fingerprint would advance
    without the failing schema ever being retried.
    """
    _SchemingMixin._fingerprint = _SchemingMixin._pending_fingerprint


def reset() -> None:
    """Forget the cached fingerprint, forcing a re-merge on next access."""
    _SchemingMixin._fingerprint = None
    _SchemingMixin._pending_fingerprint = None


def _current_fingerprint() -> tuple[int, datetime | None]:
    return SchemingSchemaState.fingerprint("dataset")


def _checked_in_this_request() -> bool:
    if not has_request_context():
        return False

    if g.get("scheming_dynamic_checked"):
        return True

    g.scheming_dynamic_checked = True
    return False
