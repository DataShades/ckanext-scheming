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
        sa.Column("definition", JSONB),
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
        model.Session.commit()
        return row

    def update_definition(self, definition: dict[str, Any]) -> None:
        self.definition = definition
        model.Session.commit()

    def delete(self) -> None:
        model.Session.delete(self)
        model.Session.commit()

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "schema_type": self.schema_type,
            "definition": self.definition,
            "updated": self.updated.isoformat(),
        }
