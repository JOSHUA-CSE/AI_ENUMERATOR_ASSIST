"""create_administrative_areas_and_houses

Revision ID: e1a2b3c4d5e6
Revises: d0e9e8162e1a
Create Date: 2026-09-12 10:20:00.000000

"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "d0e9e8162e1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create administrative_areas table
    op.create_table(
        "administrative_areas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("VILLAGE", "WARD", "TALUK", "DISTRICT", name="areatype"),
            nullable=False,
        ),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column(
            "boundary",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                spatial_index=True,
            ),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["administrative_areas.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_administrative_areas_code"),
        "administrative_areas",
        ["code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_administrative_areas_name"),
        "administrative_areas",
        ["name"],
        unique=False,
    )

    # 2. Create houses table
    op.create_table(
        "houses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.Column("building_reference", sa.String(), nullable=True),
        sa.Column("house_number", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                spatial_index=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["administrative_areas.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_houses_area_id"), "houses", ["area_id"], unique=False)
    op.create_index(
        op.f("ix_houses_building_reference"),
        "houses",
        ["building_reference"],
        unique=False,
    )
    op.create_index(
        op.f("ix_houses_house_number"), "houses", ["house_number"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_houses_house_number"), table_name="houses")
    op.drop_index(op.f("ix_houses_building_reference"), table_name="houses")
    op.drop_index(op.f("ix_houses_area_id"), table_name="houses")
    op.drop_table("houses")

    op.drop_index(
        op.f("ix_administrative_areas_name"), table_name="administrative_areas"
    )
    op.drop_index(
        op.f("ix_administrative_areas_code"), table_name="administrative_areas"
    )
    op.drop_table("administrative_areas")
