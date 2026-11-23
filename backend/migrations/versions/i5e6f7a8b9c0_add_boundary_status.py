"""add_boundary_status_to_areas_layouts_and_hlbs

Revision ID: i5e6f7a8b9c0
Revises: h4d5e6f7a8b9
Create Date: 2026-11-12 17:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "h4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())
    is_sqlite = bind.dialect.name == "sqlite"

    target_tables = ["administrative_areas", "layouts", "layout_versions", "houselisting_blocks"]

    for table_name in target_tables:
        if table_name in existing_tables:
            cols = {c["name"] for c in insp.get_columns(table_name)}
            if "boundary_status" not in cols:
                if is_sqlite:
                    with op.batch_alter_table(table_name) as batch_op:
                        batch_op.add_column(
                            sa.Column("boundary_status", sa.String(), server_default="PROVISIONAL", nullable=False)
                        )
                else:
                    op.add_column(
                        table_name,
                        sa.Column("boundary_status", sa.String(), server_default="PROVISIONAL", nullable=False),
                    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())
    is_sqlite = bind.dialect.name == "sqlite"

    target_tables = ["administrative_areas", "layouts", "layout_versions", "houselisting_blocks"]

    for table_name in target_tables:
        if table_name in existing_tables:
            cols = {c["name"] for c in insp.get_columns(table_name)}
            if "boundary_status" in cols:
                if is_sqlite:
                    with op.batch_alter_table(table_name) as batch_op:
                        batch_op.drop_column("boundary_status")
                else:
                    op.drop_column(table_name, "boundary_status")

