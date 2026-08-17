from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from typing_extensions import Self  # noqa: UP035

import ckan.plugins.toolkit as tk
from ckan import model
from ckan.model.types import make_uuid


def _current_datetime() -> datetime:
    return datetime.now(tz=timezone.utc)  # noqa: UP017


class SchemingState(tk.BaseModel):
    """Change counter, one row per named counter channel.

    Bumped explicitly around every dynamic-schema create/update/delete
    (keyed by entity_type) and by ``SchemingPreset``'s
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


class SchemingPreset(tk.BaseModel):
    """A field preset, editable through the admin UI.

    Shares ``SchemingState``'s version counter under the "preset" key:
    presets are a single global registry, not per-entity_type like
    ``SchemingSchemaVersion``.
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


class SchemingSchemaVersion(tk.BaseModel):
    """Schema version history, plus the live definition."""

    __table__ = sa.Table(
        "scheming_schema_version",
        tk.BaseModel.metadata,
        sa.Column("entity_type", sa.Text, primary_key=True),
        sa.Column("schema_type", sa.Text, primary_key=True),
        sa.Column("version", sa.Integer, primary_key=True),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column(
            "created",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            default=_current_datetime,
        ),
    )

    entity_type: Mapped[str]
    schema_type: Mapped[str]
    version: Mapped[int]
    definition: Mapped[dict[str, Any]]
    created: Mapped[datetime]

    @classmethod
    def get(
        cls, entity_type: str, schema_type: str, version: int
    ) -> SchemingSchemaVersion | None:
        return model.Session.get(cls, (entity_type, schema_type, version))

    @classmethod
    def head_version(cls, entity_type: str, schema_type: str) -> int:
        """Highest version number, or 0 if the schema doesn't exist yet."""
        result = (
            model.Session.query(sa.func.max(cls.version))
            .filter(cls.entity_type == entity_type, cls.schema_type == schema_type)
            .scalar()
        )
        return result or 0

    @classmethod
    def head(cls, entity_type: str, schema_type: str) -> Self | None:
        """The current live schema, or None if the schema doesn't exist."""
        version = cls.head_version(entity_type, schema_type)
        if version == 0:
            return None
        return cls.get(entity_type, schema_type, version)

    @classmethod
    def get_heads_of_type(cls, entity_type: str) -> list[Self]:
        """The head-version row of every schema_type under entity_type."""
        heads = (
            model.Session.query(
                cls.schema_type, sa.func.max(cls.version).label("head_version")
            )
            .filter(cls.entity_type == entity_type)
            .group_by(cls.schema_type)
            .subquery()
        )
        return (
            model.Session.query(cls)
            .join(
                heads,
                sa.and_(
                    cls.schema_type == heads.c.schema_type,
                    cls.version == heads.c.head_version,
                ),
            )
            .filter(cls.entity_type == entity_type)
            .all()
        )

    @classmethod
    def lock(
        cls, entity_type: str, schema_type: str, definition: dict[str, Any]
    ) -> SchemingSchemaVersion:
        """Snapshot ``definition`` as the next version for this schema_type."""
        version = cls.head_version(entity_type, schema_type) + 1
        row = cls(
            entity_type=entity_type,
            schema_type=schema_type,
            version=version,
            definition=definition,
        )
        model.Session.add(row)
        model.Session.flush()
        return row

    @classmethod
    def create(
        cls, entity_type: str, schema_type: str, definition: dict[str, Any]
    ) -> SchemingSchemaVersion:
        """Create a brand-new schema by locking its first version."""
        row = cls.lock(entity_type, schema_type, definition)
        SchemingState.bump(entity_type)
        model.Session.commit()
        return row

    @classmethod
    def delete_all(cls, entity_type: str, schema_type: str) -> None:
        """Delete every version row for schema_type (the entire schema).

        Callers should already have confirmed nothing is pinned to this
        schema_type (the create/update/delete actions do, via the
        ``scheming_schema_not_in_use`` validator). If something still is,
        ``SchemingSchemaPin``'s FK acts as a backstop and this raises
        IntegrityError instead of silently orphaning the pin.
        """
        model.Session.query(cls).filter(
            cls.entity_type == entity_type, cls.schema_type == schema_type
        ).delete()

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "schema_type": self.schema_type,
            "version": self.version,
            "definition": self.definition,
            "created": self.created.isoformat(),
        }


class SchemingSchemaPin(tk.BaseModel):
    """Entity schema version pinning."""

    __table__ = sa.Table(
        "scheming_schema_pin",
        tk.BaseModel.metadata,
        sa.Column("entity_type", sa.Text, primary_key=True),
        sa.Column("entity_id", sa.Text, primary_key=True),
        sa.Column("schema_type", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(
            ["entity_type", "schema_type", "version"],
            [
                "scheming_schema_version.entity_type",
                "scheming_schema_version.schema_type",
                "scheming_schema_version.version",
            ],
        ),
    )

    entity_type: Mapped[str]
    entity_id: Mapped[str]
    schema_type: Mapped[str]
    version: Mapped[int]

    @classmethod
    def get(cls, entity_type: str, entity_id: str) -> SchemingSchemaPin | None:
        return model.Session.get(cls, (entity_type, entity_id))

    @classmethod
    def pin(
        cls, entity_type: str, entity_id: str, schema_type: str, version: int
    ) -> SchemingSchemaPin:
        row = cls(
            entity_type=entity_type,
            entity_id=entity_id,
            schema_type=schema_type,
            version=version,
        )
        model.Session.add(row)
        model.Session.flush()
        return row

    @classmethod
    def is_version_locked(
        cls, entity_type: str, schema_type: str, version: int
    ) -> bool:
        return (
            model.Session.query(cls.entity_id)
            .filter(
                cls.entity_type == entity_type,
                cls.schema_type == schema_type,
                cls.version == version,
            )
            .first()
            is not None
        )


class SchemingSchemaActivity(tk.BaseModel):
    """Audit log entry for a schema create/update/delete action."""

    __table__ = sa.Table(
        "scheming_schema_activity",
        tk.BaseModel.metadata,
        sa.Column("id", sa.Text, primary_key=True, default=make_uuid),
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("schema_type", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("actor", sa.Text, nullable=False),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("version", sa.Integer, nullable=True),
        sa.Column(
            "created",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            default=_current_datetime,
        ),
    )

    id: Mapped[str]
    entity_type: Mapped[str]
    schema_type: Mapped[str]
    action: Mapped[str]
    actor: Mapped[str]
    definition: Mapped[dict[str, Any]]
    version: Mapped[int | None]
    created: Mapped[datetime]

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    @classmethod
    def record( # noqa: PLR0913
        cls,
        entity_type: str,
        schema_type: str,
        action: str,
        actor: str,
        definition: dict[str, Any],
        version: int | None = None,
    ) -> SchemingSchemaActivity:
        row = cls(
            entity_type=entity_type,
            schema_type=schema_type,
            action=action,
            actor=actor,
            definition=definition,
            version=version,
        )
        model.Session.add(row)
        model.Session.flush()
        return row

    @classmethod
    def get(cls, id: str) -> Self | None:
        return model.Session.get(cls, id)

    @classmethod
    def get_history(cls, entity_type: str, schema_type: str) -> list[Self]:
        """All activity rows for a schema_type, oldest first."""
        return (
            model.Session.query(cls)
            .filter(cls.entity_type == entity_type, cls.schema_type == schema_type)
            .order_by(cls.created)
            .all()
        )

    @classmethod
    def get_schema_types(cls, entity_type: str) -> list[str]:
        """Every schema_type with recorded activity, live or deleted."""
        rows = (
            model.Session.query(cls.schema_type, sa.func.max(cls.created))
            .filter(cls.entity_type == entity_type)
            .group_by(cls.schema_type)
            .order_by(sa.func.max(cls.created).desc())
            .all()
        )
        return [schema_type for schema_type, _ in rows]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "schema_type": self.schema_type,
            "action": self.action,
            "actor": self.actor,
            "definition": self.definition,
            "version": self.version,
            "created": self.created.isoformat(),
        }
