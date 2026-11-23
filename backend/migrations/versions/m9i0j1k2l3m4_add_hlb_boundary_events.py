"""add_hlb_boundary_events

Revision ID: m9i0j1k2l3m4
Revises: l8h9i0j1k2l3
Create Date: 2026-11-13 09:30:00.000000

"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m9i0j1k2l3m4"
down_revision: str | Sequence[str] | None = "l8h9i0j1k2l3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "hlb_boundary_events" not in existing_tables:
        op.create_table(
            "hlb_boundary_events",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "hlb_id",
                sa.Uuid(),
                sa.ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "enumerator_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("event_type", sa.String(), nullable=False, default="EXIT", index=True),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("accuracy_meters", sa.Float(), nullable=True),
            sa.Column("distance_to_boundary_meters", sa.Float(), nullable=True),
            sa.Column("boundary_status", sa.String(), nullable=False, default="OUTSIDE"),
            sa.Column("device_id", sa.String(), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("supervisor_notified", sa.Boolean(), nullable=False, default=False),
            sa.Column("notification_details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("hlb_boundary_events")

