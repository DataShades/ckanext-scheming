"""Create scheming_dataset_schema table

Revision ID: 8d447c8244e1
Revises:
Create Date: 2026-07-23 17:31:17.776601

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "8d447c8244e1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scheming_dataset_schema",
        sa.Column("dataset_type", sa.Text, primary_key=True),
        sa.Column("updated", sa.TIMESTAMP),
        sa.Column("definition", JSONB),
    )
    op.create_index(
        "ix_scheming_dataset_schema_updated", "scheming_dataset_schema", ["updated"]
    )


def downgrade():
    op.drop_index(
        "ix_scheming_dataset_schema_updated", table_name="scheming_dataset_schema"
    )
    op.drop_table("scheming_dataset_schema")
