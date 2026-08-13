from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from typing_extensions import Self  # noqa: UP035

import ckan.plugins.toolkit as tk
from ckan import model


def _current_datetime() -> datetime:
    return datetime.now(tz=timezone.utc)  # noqa: UP017


class SchemingState(tk.BaseModel):
    """Change counter, one row per named counter channel.

    Bumped explicitly by ``SchemingSchema.create``/``update_definition``/
    ``delete`` (keyed by entity_type) and by ``SchemingPreset``'s
    create/update/delete (keyed by ``SchemingPreset.PRESET_STATE_ENTITY_TYPE``).
    """

    __table__ = sa.Table(
        "scheming_state",
        tk.BaseModel.metadata,
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("version", sa.Integer, nullable=False, default=0),
        sa.Column(
            "updated",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            default=_current_datetime,
        ),
    )

    key: Mapped[str]
    version: Mapped[int]
    updated: Mapped[datetime]

    @classmethod
    def bump(cls, key: str) -> None:
        """Increment the version counter for ``key``.

        ``with_for_update`` locks the row for the rest of the transaction,
        so a second concurrent bump on the same key blocks until this one
        commits instead of reading the same pre-increment version and
        clobbering it (lost update). Only the very first bump for a
        never-before-seen key is unprotected, since there's no row yet to
        lock.
        """
        row = model.Session.get(cls, key, with_for_update=True)
        if row is None:
            row = cls(key=key, version=0)
            model.Session.add(row)

        row.version += 1
        row.updated = _current_datetime()

    @classmethod
    def fingerprint(cls, key: str) -> tuple[int, datetime | None]:
        row = model.Session.get(cls, key)
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
        SchemingState.bump(entity_type)
        model.Session.commit()
        return row

    def update_definition(self, definition: dict[str, Any]) -> None:
        self.definition = definition
        SchemingState.bump(self.entity_type)
        model.Session.commit()

    def delete(self) -> None:
        model.Session.delete(self)
        SchemingState.bump(self.entity_type)
        model.Session.commit()

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "schema_type": self.schema_type,
            "definition": self.definition,
            "updated": self.updated.isoformat(),
        }


class SchemingPreset(tk.BaseModel):
    """A field preset, editable through the admin UI.

    Shares ``SchemingState``'s version counter under the "preset" key:
    presets are a single global registry, not per-entity_type like
    ``SchemingSchema``.
    """

    PRESET_STATE_ENTITY_TYPE = "preset"

    __table__ = sa.Table(
        "scheming_preset",
        tk.BaseModel.metadata,
        sa.Column("preset_name", sa.Text, primary_key=True),
        sa.Column(
            "updated",
            sa.TIMESTAMP(timezone=True),
            index=True,
            default=_current_datetime,
            onupdate=_current_datetime,
        ),
        sa.Column("values", JSONB, nullable=False),
    )

    preset_name: Mapped[str]
    updated: Mapped[datetime]
    values: Mapped[dict[str, Any]]

    @classmethod
    def get(cls, preset_name: str) -> SchemingPreset | None:
        return model.Session.get(cls, preset_name)

    @classmethod
    def get_all(cls) -> list[Self]:
        return model.Session.query(cls).all()

    @classmethod
    def create(cls, preset_name: str, values: dict[str, Any]) -> SchemingPreset:
        row = cls(preset_name=preset_name, values=values)
        model.Session.add(row)
        SchemingState.bump(cls.PRESET_STATE_ENTITY_TYPE)
        model.Session.commit()
        return row

    def update_values(self, values: dict[str, Any]) -> None:
        self.values = values
        SchemingState.bump(self.PRESET_STATE_ENTITY_TYPE)
        model.Session.commit()

    def delete(self) -> None:
        model.Session.delete(self)
        SchemingState.bump(self.PRESET_STATE_ENTITY_TYPE)
        model.Session.commit()

    def as_dict(self) -> dict[str, Any]:
        return {
            "preset_name": self.preset_name,
            "values": self.values,
            "updated": self.updated.isoformat(),
        }
