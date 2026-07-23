from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped

import ckan.plugins.toolkit as tk


class SchemingDatasetSchema(tk.BaseModel):
    __table__ = sa.Table(
        "scheming_dataset_schema",
        tk.BaseModel.metadata,
        sa.Column("dataset_type", sa.Text, primary_key=True),
        sa.Column("updated", sa.TIMESTAMP, index=True),
        sa.Column("definition", JSONB),
    )

    dataset_type: Mapped[str]
    updated: Mapped[datetime]
    definition: Mapped[dict[str, Any]]
