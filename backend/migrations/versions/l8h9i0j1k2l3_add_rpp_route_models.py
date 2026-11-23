"""add_rpp_route_models

Revision ID: l8h9i0j1k2l3
Revises: k7g8h9i0j1k2
Create Date: 2026-11-13 06:40:00.000000

"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l8h9i0j1k2l3"
down_revision: str | Sequence[str] | None = "k7g8h9i0j1k2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. road_graphs
    if "road_graphs" not in existing_tables:
        op.create_table(
            "road_graphs",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "area_id",
                sa.Uuid(),
                sa.ForeignKey("administrative_areas.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("source", sa.String(), nullable=False, default="OpenStreetMap"),
            sa.Column("license", sa.String(), nullable=False, default="ODbL"),
            sa.Column("network_version", sa.String(), nullable=False, default="v1.0"),
            sa.Column("acquisition_date", sa.String(), nullable=False, default="2026-11-11T09:42:04Z"),
            sa.Column("node_count", sa.Integer(), nullable=False, default=0),
            sa.Column("edge_count", sa.Integer(), nullable=False, default=0),
            sa.Column("total_length_m", sa.Float(), nullable=False, default=0.0),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    # 2. road_nodes
    if "road_nodes" not in existing_tables:
        op.create_table(
            "road_nodes",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "graph_id",
                sa.Uuid(),
                sa.ForeignKey("road_graphs.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("node_identifier", sa.String(), nullable=False, index=True),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("degree", sa.Integer(), nullable=False, default=0),
            sa.Column("is_intersection", sa.Boolean(), nullable=False, default=False),
        )

    # 3. road_edges
    if "road_edges" not in existing_tables:
        op.create_table(
            "road_edges",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "graph_id",
                sa.Uuid(),
                sa.ForeignKey("road_graphs.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("edge_identifier", sa.String(), nullable=False, index=True),
            sa.Column("osm_way_id", sa.String(), nullable=True, index=True),
            sa.Column("start_node_id", sa.String(), nullable=False),
            sa.Column("end_node_id", sa.String(), nullable=False),
            sa.Column("highway_type", sa.String(), nullable=False, default="residential"),
            sa.Column("road_name", sa.String(), nullable=True),
            sa.Column("surface", sa.String(), nullable=True),
            sa.Column("foot", sa.String(), nullable=True),
            sa.Column("access", sa.String(), nullable=True),
            sa.Column("length_m", sa.Float(), nullable=False, default=0.0),
            sa.Column("walking_cost", sa.Float(), nullable=False, default=0.0),
            sa.Column("is_walkable", sa.Boolean(), nullable=False, default=True),
            sa.Column("coordinates", sa.JSON(), nullable=False),
        )

    # 4. hlb_required_edges
    if "hlb_required_edges" not in existing_tables:
        op.create_table(
            "hlb_required_edges",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "hlb_id",
                sa.Uuid(),
                sa.ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("edge_id", sa.String(), nullable=False, index=True),
            sa.Column("source_way_id", sa.String(), nullable=True, index=True),
            sa.Column("start_node_id", sa.String(), nullable=False),
            sa.Column("end_node_id", sa.String(), nullable=False),
            sa.Column("coordinates", sa.JSON(), nullable=False),
            sa.Column("length_m", sa.Float(), nullable=False, default=0.0),
            sa.Column("walking_cost", sa.Float(), nullable=False, default=0.0),
            sa.Column("highway_type", sa.String(), nullable=False, default="residential"),
            sa.Column("pedestrian_access", sa.String(), nullable=True),
            sa.Column("road_surface", sa.String(), nullable=True),
            sa.Column("boundary_classification", sa.String(), nullable=False, default="INTERNAL"),
            sa.Column("required_status", sa.String(), nullable=False, default="REQUIRED"),
            sa.Column(
                "coverage_status",
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
            sa.Column("graph_version", sa.String(), nullable=False, default="v1.0"),
            sa.Column("source", sa.String(), nullable=False, default="OpenStreetMap"),
            sa.Column("acquired_at", sa.String(), nullable=False, default="2026-11-11T09:42:04Z"),
            sa.Column("requires_two_sided", sa.Boolean(), nullable=False, default=False),
            sa.Column("left_surveyed", sa.Boolean(), nullable=False, default=False),
            sa.Column("right_surveyed", sa.Boolean(), nullable=False, default=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("hlb_id", "edge_id", name="uq_hlb_required_edge"),
        )

    # 5. hlb_route_plans
    if "hlb_route_plans" not in existing_tables:
        op.create_table(
            "hlb_route_plans",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "hlb_id",
                sa.Uuid(),
                sa.ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("route_version", sa.Integer(), nullable=False, default=1),
            sa.Column("graph_version", sa.String(), nullable=False, default="v1.0"),
            sa.Column("status", sa.String(), nullable=False, default="ACTIVE"),
            sa.Column("total_distance_km", sa.Float(), nullable=False, default=0.0),
            sa.Column("estimated_walking_time_minutes", sa.Float(), nullable=False, default=0.0),
            sa.Column("total_required_edges_count", sa.Integer(), nullable=False, default=0),
            sa.Column("surveyed_edges_count", sa.Integer(), nullable=False, default=0),
            sa.Column("coverage_percentage", sa.Float(), nullable=False, default=0.0),
            sa.Column("deadhead_distance_km", sa.Float(), nullable=False, default=0.0),
            sa.Column("deadhead_percentage", sa.Float(), nullable=False, default=0.0),
            sa.Column("disconnected_components_count", sa.Integer(), nullable=False, default=1),
            sa.Column("external_transit_count", sa.Integer(), nullable=False, default=0),
            sa.Column("start_lat", sa.Float(), nullable=True),
            sa.Column("start_lon", sa.Float(), nullable=True),
            sa.Column("end_lat", sa.Float(), nullable=True),
            sa.Column("end_lon", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    # 6. hlb_route_traversals
    if "hlb_route_traversals" not in existing_tables:
        op.create_table(
            "hlb_route_traversals",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "plan_id",
                sa.Uuid(),
                sa.ForeignKey("hlb_route_plans.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("step_index", sa.Integer(), nullable=False, index=True),
            sa.Column("section_index", sa.Integer(), nullable=False, default=1),
            sa.Column("edge_id", sa.String(), nullable=False, index=True),
            sa.Column("is_transit", sa.Boolean(), nullable=False, default=False),
            sa.Column("is_deadhead", sa.Boolean(), nullable=False, default=False),
            sa.Column("from_node", sa.String(), nullable=True),
            sa.Column("to_node", sa.String(), nullable=True),
            sa.Column("direction_forward", sa.Boolean(), nullable=False, default=True),
            sa.Column("cumulative_distance_m", sa.Float(), nullable=False, default=0.0),
            sa.Column("cumulative_walking_time_minutes", sa.Float(), nullable=False, default=0.0),
            sa.Column("coordinates", sa.JSON(), nullable=False),
        )

    # 7. missing_path_submissions
    if "missing_path_submissions" not in existing_tables:
        op.create_table(
            "missing_path_submissions",
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
            sa.Column("coordinates", sa.JSON(), nullable=False),
            sa.Column("highway_type", sa.String(), nullable=False, default="path"),
            sa.Column("road_name", sa.String(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.Enum(
                    "PENDING_REVIEW",
                    "APPROVED",
                    "REJECTED",
                    name="missing_path_status_enum",
                ),
                nullable=False,
                default="PENDING_REVIEW",
                index=True,
            ),
            sa.Column(
                "reviewed_by",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("missing_path_submissions")
    op.drop_table("hlb_route_traversals")
    op.drop_table("hlb_route_plans")
    op.drop_table("hlb_required_edges")
    op.drop_table("road_edges")
    op.drop_table("road_nodes")
    op.drop_table("road_graphs")

