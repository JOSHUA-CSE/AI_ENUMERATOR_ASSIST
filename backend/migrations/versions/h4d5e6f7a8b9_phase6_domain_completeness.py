"""phase6_domain_completeness

Revision ID: h4d5e6f7a8b9
Revises: g3c4d5e6f7a8
Create Date: 2026-11-11 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "g3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())
    is_sqlite = bind.dialect.name == "sqlite"

    workload_unit_enum = sa.Enum(
        "BUILDINGS",
        "CENSUS_HOUSES",
        "POPULATION",
        name="workload_unit_enum",
    )

    # 1. Update layouts
    if "layouts" in existing_tables:
        cols = {c["name"] for c in insp.get_columns("layouts")}
        if is_sqlite:
            with op.batch_alter_table("layouts") as batch_op:
                if "workload_unit" not in cols:
                    batch_op.add_column(
                        sa.Column("workload_unit", sa.String(), server_default="BUILDINGS", nullable=False)
                    )
                if "target_workload" not in cols:
                    batch_op.add_column(
                        sa.Column("target_workload", sa.Integer(), server_default="250", nullable=False)
                    )
                if "estimated_census_house_count" not in cols:
                    batch_op.add_column(sa.Column("estimated_census_house_count", sa.Integer(), nullable=True))
                if "estimated_population" not in cols:
                    batch_op.add_column(sa.Column("estimated_population", sa.Integer(), nullable=True))
                if "estimation_method" not in cols:
                    batch_op.add_column(sa.Column("estimation_method", sa.String(), nullable=True))
                if "estimation_provenance" not in cols:
                    batch_op.add_column(sa.Column("estimation_provenance", sa.String(), nullable=True))
        else:
            if "workload_unit" not in cols:
                op.add_column(
                    "layouts",
                    sa.Column("workload_unit", workload_unit_enum, server_default="BUILDINGS", nullable=False),
                )
            if "target_workload" not in cols:
                op.add_column(
                    "layouts",
                    sa.Column("target_workload", sa.Integer(), server_default="250", nullable=False),
                )
            if "estimated_census_house_count" not in cols:
                op.add_column("layouts", sa.Column("estimated_census_house_count", sa.Integer(), nullable=True))
            if "estimated_population" not in cols:
                op.add_column("layouts", sa.Column("estimated_population", sa.Integer(), nullable=True))
            if "estimation_method" not in cols:
                op.add_column("layouts", sa.Column("estimation_method", sa.String(), nullable=True))
            if "estimation_provenance" not in cols:
                op.add_column("layouts", sa.Column("estimation_provenance", sa.String(), nullable=True))

    # 2. Update layout_versions
    if "layout_versions" in existing_tables:
        cols = {c["name"] for c in insp.get_columns("layout_versions")}
        if is_sqlite:
            with op.batch_alter_table("layout_versions") as batch_op:
                if "workload_unit" not in cols:
                    batch_op.add_column(
                        sa.Column("workload_unit", sa.String(), server_default="BUILDINGS", nullable=False)
                    )
                if "target_workload" not in cols:
                    batch_op.add_column(
                        sa.Column("target_workload", sa.Integer(), server_default="250", nullable=False)
                    )
                if "estimated_census_house_count" not in cols:
                    batch_op.add_column(sa.Column("estimated_census_house_count", sa.Integer(), nullable=True))
                if "estimated_population" not in cols:
                    batch_op.add_column(sa.Column("estimated_population", sa.Integer(), nullable=True))
                if "estimation_method" not in cols:
                    batch_op.add_column(sa.Column("estimation_method", sa.String(), nullable=True))
                if "estimation_provenance" not in cols:
                    batch_op.add_column(sa.Column("estimation_provenance", sa.String(), nullable=True))
        else:
            if "workload_unit" not in cols:
                op.add_column(
                    "layout_versions",
                    sa.Column("workload_unit", workload_unit_enum, server_default="BUILDINGS", nullable=False),
                )
            if "target_workload" not in cols:
                op.add_column(
                    "layout_versions",
                    sa.Column("target_workload", sa.Integer(), server_default="250", nullable=False),
                )
            if "estimated_census_house_count" not in cols:
                op.add_column("layout_versions", sa.Column("estimated_census_house_count", sa.Integer(), nullable=True))
            if "estimated_population" not in cols:
                op.add_column("layout_versions", sa.Column("estimated_population", sa.Integer(), nullable=True))
            if "estimation_method" not in cols:
                op.add_column("layout_versions", sa.Column("estimation_method", sa.String(), nullable=True))
            if "estimation_provenance" not in cols:
                op.add_column("layout_versions", sa.Column("estimation_provenance", sa.String(), nullable=True))

    # 3. Update houselisting_blocks
    if "houselisting_blocks" in existing_tables:
        cols = {c["name"] for c in insp.get_columns("houselisting_blocks")}
        if is_sqlite:
            with op.batch_alter_table("houselisting_blocks") as batch_op:
                if "estimated_census_house_count" not in cols:
                    batch_op.add_column(sa.Column("estimated_census_house_count", sa.Integer(), nullable=True))
                if "estimated_population" not in cols:
                    batch_op.add_column(sa.Column("estimated_population", sa.Integer(), nullable=True))
        else:
            if "estimated_census_house_count" not in cols:
                op.add_column("houselisting_blocks", sa.Column("estimated_census_house_count", sa.Integer(), nullable=True))
            if "estimated_population" not in cols:
                op.add_column("houselisting_blocks", sa.Column("estimated_population", sa.Integer(), nullable=True))

    # 4. Update building_edits
    if "building_edits" in existing_tables:
        cols = {c["name"] for c in insp.get_columns("building_edits")}
        if "version" not in cols:
            if is_sqlite:
                with op.batch_alter_table("building_edits") as batch_op:
                    batch_op.add_column(sa.Column("version", sa.Integer(), server_default="1", nullable=False))
            else:
                op.add_column("building_edits", sa.Column("version", sa.Integer(), server_default="1", nullable=False))

    # 5. Create hlb_counters table
    if "hlb_counters" not in existing_tables:
        op.create_table(
            "hlb_counters",
            sa.Column("hlb_id", sa.Uuid(), sa.ForeignKey("houselisting_blocks.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("next_building_no", sa.Integer(), server_default="1", nullable=False),
            sa.Column("next_census_house_no", sa.Integer(), server_default="1", nullable=False),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    # 6. Create change_request_messages table
    if "change_request_messages" not in existing_tables:
        op.create_table(
            "change_request_messages",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("change_request_id", sa.Uuid(), sa.ForeignKey("change_requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("author_role", sa.String(), nullable=False),
            sa.Column("message", sa.String(), nullable=False),
            sa.Column("attachments", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            op.f("ix_change_request_messages_change_request_id"),
            "change_request_messages",
            ["change_request_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_change_request_messages_author_id"),
            "change_request_messages",
            ["author_id"],
            unique=False,
        )

    # 7. Update sync_operations with local_entity_id and unique constraint
    if "sync_operations" in existing_tables:
        cols = {c["name"] for c in insp.get_columns("sync_operations")}
        if "local_entity_id" not in cols:
            if is_sqlite:
                with op.batch_alter_table("sync_operations") as batch_op:
                    batch_op.add_column(sa.Column("local_entity_id", sa.String(), nullable=True))
                    batch_op.create_index(op.f("ix_sync_operations_local_entity_id"), ["local_entity_id"], unique=False)
                    batch_op.create_unique_constraint("uq_sync_device_entity_local", ["device_id", "entity_type", "local_entity_id"])
            else:
                op.add_column("sync_operations", sa.Column("local_entity_id", sa.String(), nullable=True))
                op.create_index(op.f("ix_sync_operations_local_entity_id"), "sync_operations", ["local_entity_id"], unique=False)
                op.create_unique_constraint("uq_sync_device_entity_local", "sync_operations", ["device_id", "entity_type", "local_entity_id"])

    # 8. Create supervisor_corrections table
    if "supervisor_corrections" not in existing_tables:
        op.create_table(
            "supervisor_corrections",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("entity_id", sa.Uuid(), nullable=False),
            sa.Column("original_version", sa.Integer(), nullable=False),
            sa.Column("corrected_version", sa.Integer(), nullable=False),
            sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("author_role", sa.String(), server_default="SUPERVISOR", nullable=False),
            sa.Column("changed_fields", sa.JSON(), nullable=False),
            sa.Column("previous_data", sa.JSON(), nullable=True),
            sa.Column("corrected_data", sa.JSON(), nullable=False),
            sa.Column("correction_reason", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(op.f("ix_supervisor_corrections_entity_type"), "supervisor_corrections", ["entity_type"], unique=False)
        op.create_index(op.f("ix_supervisor_corrections_entity_id"), "supervisor_corrections", ["entity_id"], unique=False)
        op.create_index(op.f("ix_supervisor_corrections_author_id"), "supervisor_corrections", ["author_id"], unique=False)


def downgrade() -> None:
    pass

