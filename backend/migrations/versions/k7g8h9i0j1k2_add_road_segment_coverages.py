"""add_road_segment_coverages

Revision ID: k7g8h9i0j1k2
Revises: j6f7a8b9c0d1
Create Date: 2026-11-12 23:30:00.000000

"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k7g8h9i0j1k2"
down_revision: str | Sequence[str] | None = "j6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "road_segment_coverages" not in existing_tables:
        op.create_table(
            "road_segment_coverages",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "hlb_id",
                sa.Uuid(),
                sa.ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("segment_id", sa.String(), nullable=False, index=True),
            sa.Column("osm_way_id", sa.String(), nullable=True, index=True),
            sa.Column("highway_type", sa.String(), nullable=True),
            sa.Column("road_name", sa.String(), nullable=True),
            sa.Column(
                "enumerator_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("device_id", sa.String(), nullable=True),
            sa.Column(
                "survey_status",
                sa.Enum(
                    "NOT_VISITED",
                    "IN_PROGRESS",
                    "SURVEYED",
                    "NEEDS_REVISIT",
                    name="road_segment_survey_status_enum",
                ),
                nullable=False,
                default="NOT_VISITED",
                index=True,
            ),
            sa.Column("total_length_m", sa.Float(), nullable=False, default=0.0),
            sa.Column("surveyed_length_m", sa.Float(), nullable=False, default=0.0),
            sa.Column("coverage_percentage", sa.Float(), nullable=False, default=0.0),
            sa.Column("gps_trace", sa.JSON(), nullable=True),
            sa.Column("segment_geometry", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column(
                "sync_status",
                sa.Enum(
                    "PENDING",
                    "SYNCED",
                    name="road_coverage_sync_status_enum",
                ),
                nullable=False,
                default="SYNCED",
                index=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("hlb_id", "segment_id", name="uq_hlb_road_segment"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "road_segment_coverages" in existing_tables:
        op.drop_table("road_segment_coverages")

