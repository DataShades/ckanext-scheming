"""How far the datasets of each schema type lag behind its live version."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from ckan import model

from ckanext.scheming_dynamic.model import SchemingSchemaPin, SchemingSchemaVersion


def for_schema_type(
    entity_type: str, schema_type: str, head_version: int
) -> dict[str, Any]:
    distribution = _distribution(entity_type, schema_type)

    return {
        "entity_type": entity_type,
        "schema_type": schema_type,
        "live_version": head_version,
        "distribution": distribution,
        "behind": sum(
            count for version, count in distribution.items() if version != head_version
        ),
        "unpinned": _unpinned_count(schema_type),
    }


def all_schema_types(entity_type: str) -> list[dict[str, Any]]:
    return [
        for_schema_type(entity_type, row.schema_type, row.version)
        for row in SchemingSchemaVersion.get_heads_of_type(entity_type)
    ]


def _distribution(entity_type: str, schema_type: str) -> dict[int, int]:
    rows = (
        model.Session.query(
            SchemingSchemaPin.version, sa.func.count(SchemingSchemaPin.entity_id)
        )
        .join(model.Package, model.Package.id == SchemingSchemaPin.entity_id)
        .filter(
            SchemingSchemaPin.entity_type == entity_type,
            SchemingSchemaPin.schema_type == schema_type,
            model.Package.state == model.State.ACTIVE,
        )
        .group_by(SchemingSchemaPin.version)
        .all()
    )
    return {version: count for version, count in rows} # noqa C416


def _unpinned_count(schema_type: str) -> int:
    return (
        model.Session.query(model.Package.id)
        .filter(
            model.Package.type == schema_type,
            model.Package.state == model.State.ACTIVE,
            ~model.Session.query(SchemingSchemaPin)
            .filter(SchemingSchemaPin.entity_id == model.Package.id)
            .exists(),
        )
        .count()
    )
