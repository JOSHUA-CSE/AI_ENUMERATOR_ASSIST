"""add_layout_administrative_areas

Revision ID: j6f7a8b9c0d1
Revises: i5e6f7a8b9c0
Create Date: 2026-11-12 18:30:00.000000

"""

from collections.abc import Sequence
import uuid
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "i5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "layout_administrative_areas" not in existing_tables:
        op.create_table(
            "layout_administrative_areas",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "layout_id",
                sa.Uuid(),
                sa.ForeignKey("layouts.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "area_id",
                sa.Uuid(),
                sa.ForeignKey("administrative_areas.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )

        # Backfill existing layouts
        if "layouts" in existing_tables:
            layouts = bind.execute(sa.text("SELECT id, area_id, created_at FROM layouts WHERE area_id IS NOT NULL")).fetchall()
            for row in layouts:
                lid, aid, cat = row[0], row[1], row[2]
                new_id = str(uuid.uuid4())
                bind.execute(
                    sa.text(
                        "INSERT INTO layout_administrative_areas (id, layout_id, area_id, created_at) "
                        "VALUES (:id, :layout_id, :area_id, :created_at)"
                    ),
                    {"id": new_id, "layout_id": str(lid), "area_id": str(aid), "created_at": cat},
                )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "layout_administrative_areas" in existing_tables:
        op.drop_table("layout_administrative_areas")

