from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from flask import g, has_request_context
from sqlalchemy.exc import DBAPIError, UnboundExecutionError

from ckan import model

from ckanext.scheming_dynamic.model import SchemingSchema

log = logging.getLogger(__name__)

_fingerprint: tuple[int, datetime | None] | None = None
_pending_fingerprint: tuple[int, datetime | None] | None = None


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
        log.debug("skipping database check in this request")
        return None

    try:
        # savepoint keeps a failed query from aborting the caller's transaction
        with model.Session.begin_nested():
            fingerprint = _current_fingerprint()
    except (DBAPIError, UnboundExecutionError):
        log.debug("cannot read the scheming_schema table")
        return None

    if fingerprint == _fingerprint:
        log.debug("no database changes since last check")
        return None

    merged = dict(static_schemas)

    for row in SchemingSchema.get_schemas_of_type(entity_type="dataset"):
        merged[row.schema_type] = row.definition

    global _pending_fingerprint  # noqa: PLW0603
    _pending_fingerprint = fingerprint

    return merged


def confirm_applied() -> None:
    """Confirm a successful sync of the dynamic schemas.

    Record that the schemas from the last ``dataset_schemas_if_changed``
    call were successfully applied, so that unchanged database state isn't
    re-merged on the next check.

    Must not be called after a failed merge: the fingerprint would advance
    without the failing schema ever being retried.
    """
    global _fingerprint  # noqa: PLW0603
    _fingerprint = _pending_fingerprint


def reset() -> None:
    """Forget the cached fingerprint, forcing a re-merge on next access."""
    global _fingerprint, _pending_fingerprint  # noqa: PLW0603
    _fingerprint = None
    _pending_fingerprint = None


def _current_fingerprint() -> tuple[int, datetime | None]:
    # count catches deleted rows, max(updated) catches created/changed ones
    count, updated = (
        model.Session.query(
            sa.func.count(SchemingSchema.schema_type),
            sa.func.max(SchemingSchema.updated),
        )
        .filter(SchemingSchema.entity_type == "dataset")
        .one()
    )
    return count, updated


def _checked_in_this_request() -> bool:
    if not has_request_context():
        return False

    if g.get("scheming_dynamic_checked"):
        return True

    g.scheming_dynamic_checked = True
    return False
