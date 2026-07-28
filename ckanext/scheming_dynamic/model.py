from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Self

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped

import ckan.plugins.toolkit as tk
from ckan import model


def _current_datetime() -> datetime:
    return datetime.now(tz=timezone.utc)  # noqa: UP017


class SchemingSchemaState(tk.BaseModel):
    """Change counter for ``SchemingSchema`` rows, one per entity_type.

    Bumped explicitly by ``SchemingSchema.create``/``update_definition``/
    ``delete``.
    """

    __table__ = sa.Table(
        "scheming_schema_state",
        tk.BaseModel.metadata,
        sa.Column("entity_type", sa.Text, primary_key=True),
        sa.Column("version", sa.Integer, nullable=False, default=0),
        sa.Column(
            "updated", sa.TIMESTAMP(timezone=True), nullable=False,
            default=_current_datetime,
        ),
    )

    entity_type: Mapped[str]
    version: Mapped[int]
    updated: Mapped[datetime]

    @classmethod
    def bump(cls, entity_type: str) -> None:
        row = model.Session.get(cls, entity_type)
        if row is None:
            row = cls(entity_type=entity_type, version=0)
            model.Session.add(row)

        row.version += 1
        row.updated = _current_datetime()

    @classmethod
    def fingerprint(cls, entity_type: str) -> tuple[int, datetime | None]:
        row = model.Session.get(cls, entity_type)
        if row is None:
            return 0, None

        return row.version, row.updated


class SchemingSchema(tk.BaseModel):
    __table__ = sa.Table(
        "scheming_schema",
        tk.BaseModel.metadata,
        sa.Column("entity_type", sa.Text, primary_key=True),
        sa.Column("schema_type", sa.Text, primary_key=True),
        sa.Column(
            "updated",
            sa.TIMESTAMP(timezone=True),
            index=True,
            default=_current_datetime,
            onupdate=_current_datetime,
        ),
        sa.Column("definition", JSONB, nullable=False),
    )

    entity_type: Mapped[str]
    schema_type: Mapped[str]
    updated: Mapped[datetime]
    definition: Mapped[dict[str, Any]]

    @classmethod
    def get(cls, entity_type: str, schema_type: str) -> SchemingSchema | None:
        return model.Session.get(cls, (entity_type, schema_type))

    @classmethod
    def get_schemas_of_type(cls, entity_type: str) -> list[Self]:
        return model.Session.query(cls).filter(cls.entity_type == entity_type).all()

    @classmethod
    def create(
        cls, entity_type: str, schema_type: str, definition: dict[str, Any]
    ) -> SchemingSchema:
        row = cls(
            entity_type=entity_type, schema_type=schema_type, definition=definition
        )
        model.Session.add(row)
        SchemingSchemaState.bump(entity_type)
        model.Session.commit()
        return row

    def update_definition(self, definition: dict[str, Any]) -> None:
        self.definition = definition
        SchemingSchemaState.bump(self.entity_type)
        model.Session.commit()

    def delete(self) -> None:
        model.Session.delete(self)
        SchemingSchemaState.bump(self.entity_type)
        model.Session.commit()

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "schema_type": self.schema_type,
            "definition": self.definition,
            "updated": self.updated.isoformat(),
        }
