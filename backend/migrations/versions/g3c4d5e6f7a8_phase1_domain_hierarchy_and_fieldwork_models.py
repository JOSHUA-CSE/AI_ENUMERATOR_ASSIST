"""phase1_domain_hierarchy_and_fieldwork_models

Revision ID: g3c4d5e6f7a8
Revises: f2b3c4d5e6f7
Create Date: 2026-11-10 20:30:00.000000

"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "f2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. Enums
    building_field_status_enum = sa.Enum(
        "UNVERIFIED",
        "CONFIRMED",
        "FALSE_DETECTION",
        "FIELD_ADDED",
        name="building_field_status_enum",
    )
    census_house_use_code_enum = sa.Enum(
        "RESIDENTIAL",
        "RESIDENTIAL_CUM_COMMERCIAL",
        "COMMERCIAL",
        "WORKSHOP_FACTORY",
        "PLACE_OF_WORSHIP",
        "INSTITUTIONAL",
        "VACANT",
        "OTHER",
        name="census_house_use_code_enum",
    )
    census_house_listing_state_enum = sa.Enum(
        "NOT_VISITED",
        "LISTED",
        "VACANT",
        "NON_RESIDENTIAL",
        "LOCKED",
        name="census_house_listing_state_enum",
    )
    household_review_state_enum = sa.Enum(
        "DRAFT",
        "SUBMITTED",
        "SUPERVISOR_VERIFIED",
        "ACCEPTED",
        "RETURNED_FOR_CORRECTION",
        name="household_review_state_enum",
    )
    person_review_state_enum = sa.Enum(
        "DRAFT",
        "SUBMITTED",
        "SUPERVISOR_VERIFIED",
        "ACCEPTED",
        name="person_review_state_enum",
    )
    building_edit_type_enum = sa.Enum(
        "ADD",
        "DELETE",
        "MERGE",
        "MOVE",
        "RENUMBER",
        name="building_edit_type_enum",
    )
    building_edit_review_status_enum = sa.Enum(
        "PENDING",
        "APPROVED",
        "REJECTED",
        name="building_edit_review_status_enum",
    )
    change_request_type_enum = sa.Enum(
        "ADDITIONAL_ENUMERATOR",
        "HLB_SPLIT",
        "HLB_MERGE",
        "BOUNDARY_DISPUTE",
        "ENUMERATOR_REASSIGNMENT",
        "TECHNICAL_ISSUE",
        "FIELDWORK_CLARIFICATION",
        name="change_request_type_enum",
    )
    change_request_status_enum = sa.Enum(
        "OPEN",
        "IN_REVIEW",
        "RESOLVED",
        "REJECTED",
        name="change_request_status_enum",
    )
    change_request_priority_enum = sa.Enum(
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        name="change_request_priority_enum",
    )

    is_sqlite = bind.dialect.name == "sqlite"

    # 2. Add columns to houses table if not present
    if "houses" in existing_tables:
        existing_cols = {c["name"] for c in insp.get_columns("houses")}
        if "field_status" not in existing_cols:
            op.add_column(
                "houses",
                sa.Column(
                    "field_status",
                    building_field_status_enum,
                    nullable=False,
                    server_default="UNVERIFIED",
                ),
            )
        if "listing_closed" not in existing_cols:
            op.add_column(
                "houses",
                sa.Column(
                    "listing_closed",
                    sa.Boolean(),
                    nullable=False,
                    server_default="0",
                ),
            )
        if "listing_closed_at" not in existing_cols:
            op.add_column(
                "houses",
                sa.Column("listing_closed_at", sa.DateTime(), nullable=True),
            )

    # 3. Create census_houses table
    if "census_houses" not in existing_tables:
        op.create_table(
            "census_houses",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "building_id",
                sa.Uuid(),
                sa.ForeignKey("houses.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "hlb_id",
                sa.Uuid(),
                sa.ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("census_house_number", sa.String(), nullable=False),
            sa.Column("use_code", census_house_use_code_enum, nullable=False),
            sa.Column("listing_state", census_house_listing_state_enum, nullable=False),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("geotag_accuracy_m", sa.Float(), nullable=True),
            sa.Column("visited_at", sa.DateTime(), nullable=True),
            sa.Column("locked_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column(
                "created_by",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            op.f("ix_census_houses_building_id"),
            "census_houses",
            ["building_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_census_houses_hlb_id"),
            "census_houses",
            ["hlb_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_census_houses_census_house_number"),
            "census_houses",
            ["census_house_number"],
            unique=False,
        )
        op.create_index(
            op.f("ix_census_houses_listing_state"),
            "census_houses",
            ["listing_state"],
            unique=False,
        )

    # 4. Update household_records with census_house_id and review_state
    if "household_records" in existing_tables:
        existing_hh_cols = {c["name"] for c in insp.get_columns("household_records")}
        if "census_house_id" not in existing_hh_cols:
            census_house_fk = [] if is_sqlite else [sa.ForeignKey("census_houses.id", ondelete="SET NULL")]
            op.add_column(
                "household_records",
                sa.Column(
                    "census_house_id",
                    sa.Uuid(),
                    *census_house_fk,
                    nullable=True,
                ),
            )
            op.create_index(
                op.f("ix_household_records_census_house_id"),
                "household_records",
                ["census_house_id"],
                unique=False,
            )
        if "questionnaire_version" not in existing_hh_cols:
            op.add_column(
                "household_records",
                sa.Column(
                    "questionnaire_version",
                    sa.String(),
                    nullable=False,
                    server_default="1.0",
                ),
            )
        if "review_state" not in existing_hh_cols:
            op.add_column(
                "household_records",
                sa.Column(
                    "review_state",
                    household_review_state_enum,
                    nullable=False,
                    server_default="DRAFT",
                ),
            )
        if "rejection_reason" not in existing_hh_cols:
            op.add_column(
                "household_records",
                sa.Column("rejection_reason", sa.String(), nullable=True),
            )
        if "supervisor_comment" not in existing_hh_cols:
            op.add_column(
                "household_records",
                sa.Column("supervisor_comment", sa.String(), nullable=True),
            )
        if "verified_by" not in existing_hh_cols:
            verified_by_fk = [] if is_sqlite else [sa.ForeignKey("users.id", ondelete="SET NULL")]
            op.add_column(
                "household_records",
                sa.Column(
                    "verified_by",
                    sa.Uuid(),
                    *verified_by_fk,
                    nullable=True,
                ),
            )
        if "verified_at" not in existing_hh_cols:
            op.add_column(
                "household_records",
                sa.Column("verified_at", sa.DateTime(), nullable=True),
            )

    # 5. Create persons table
    if "persons" not in existing_tables:
        op.create_table(
            "persons",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "household_id",
                sa.Uuid(),
                sa.ForeignKey("household_records.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("person_number", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("relationship_to_head", sa.String(), nullable=False, server_default="HEAD"),
            sa.Column("sex", sa.String(), nullable=False),
            sa.Column("age", sa.Integer(), nullable=True),
            sa.Column("date_of_birth", sa.DateTime(), nullable=True),
            sa.Column("marital_status", sa.String(), nullable=True),
            sa.Column("answers", sa.JSON(), nullable=True),
            sa.Column("questionnaire_version", sa.String(), nullable=False, server_default="2.0"),
            sa.Column("review_state", person_review_state_enum, nullable=False, server_default="DRAFT"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            op.f("ix_persons_household_id"),
            "persons",
            ["household_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_persons_name"),
            "persons",
            ["name"],
            unique=False,
        )
        op.create_index(
            op.f("ix_persons_review_state"),
            "persons",
            ["review_state"],
            unique=False,
        )

    # 6. Create building_edits table
    if "building_edits" not in existing_tables:
        op.create_table(
            "building_edits",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "hlb_id",
                sa.Uuid(),
                sa.ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "building_id",
                sa.Uuid(),
                sa.ForeignKey("houses.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("edit_type", building_edit_type_enum, nullable=False),
            sa.Column("proposed_changes", sa.JSON(), nullable=False),
            sa.Column("reason", sa.String(), nullable=False),
            sa.Column(
                "requesting_user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("review_status", building_edit_review_status_enum, nullable=False, server_default="PENDING"),
            sa.Column(
                "reviewer_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("review_comment", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            op.f("ix_building_edits_hlb_id"),
            "building_edits",
            ["hlb_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_building_edits_building_id"),
            "building_edits",
            ["building_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_building_edits_review_status"),
            "building_edits",
            ["review_status"],
            unique=False,
        )

    # 7. Create change_requests table
    if "change_requests" not in existing_tables:
        op.create_table(
            "change_requests",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("request_type", change_request_type_enum, nullable=False),
            sa.Column(
                "hlb_id",
                sa.Uuid(),
                sa.ForeignKey("houselisting_blocks.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "layout_id",
                sa.Uuid(),
                sa.ForeignKey("layouts.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "requesting_user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "assigned_reviewer_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("priority", change_request_priority_enum, nullable=False, server_default="MEDIUM"),
            sa.Column("status", change_request_status_enum, nullable=False, server_default="OPEN"),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("resolution_notes", sa.String(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            op.f("ix_change_requests_request_type"),
            "change_requests",
            ["request_type"],
            unique=False,
        )
        op.create_index(
            op.f("ix_change_requests_status"),
            "change_requests",
            ["status"],
            unique=False,
        )
        op.create_index(
            op.f("ix_change_requests_requesting_user_id"),
            "change_requests",
            ["requesting_user_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())
    is_sqlite = bind.dialect.name == "sqlite"

    for t in ["change_requests", "building_edits", "persons", "census_houses"]:
        if t in existing_tables:
            op.drop_table(t)

    if not is_sqlite:
        if "household_records" in existing_tables:
            op.drop_column("household_records", "verified_at")
            op.drop_column("household_records", "verified_by")
            op.drop_column("household_records", "supervisor_comment")
            op.drop_column("household_records", "rejection_reason")
            op.drop_column("household_records", "review_state")
            op.drop_column("household_records", "questionnaire_version")
            op.drop_column("household_records", "census_house_id")

        if "houses" in existing_tables:
            op.drop_column("houses", "listing_closed_at")
            op.drop_column("houses", "listing_closed")
            op.drop_column("houses", "field_status")

