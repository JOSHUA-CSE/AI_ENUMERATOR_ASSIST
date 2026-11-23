"""add_satellite_building_estimation_fields

Revision ID: f2b3c4d5e6f7
Revises: e1a2b3c4d5e6
Create Date: 2026-09-12 12:30:00.000000

"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "e1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create building_source_type_enum enum
    building_source_enum = sa.Enum(
        "SATELLITE_DETECTED",
        "DEVELOPMENT_DATA",
        "MANUAL",
        "GOVERNMENT_IMPORT",
        "FIELD_VERIFIED",
        name="building_source_type_enum",
    )
    building_source_enum.create(op.get_bind(), checkfirst=True)

    # 2. Add columns to houses table
    op.add_column(
        "houses",
        sa.Column(
            "footprint",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "houses",
        sa.Column(
            "source_type",
            building_source_enum,
            nullable=False,
            server_default="SATELLITE_DETECTED",
        ),
    )
    op.add_column(
        "houses",
        sa.Column("detection_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "houses",
        sa.Column("detected_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "houses",
        sa.Column("imagery_source", sa.String(), nullable=True),
    )
    op.add_column(
        "houses",
        sa.Column("imagery_date", sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f("ix_houses_source_type"), "houses", ["source_type"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_houses_source_type"), table_name="houses")
    op.drop_column("houses", "imagery_date")
    op.drop_column("houses", "imagery_source")
    op.drop_column("houses", "detected_at")
    op.drop_column("houses", "detection_confidence")
    op.drop_column("houses", "source_type")
    op.drop_column("houses", "footprint")

    building_source_enum = sa.Enum(name="building_source_type_enum")
    building_source_enum.drop(op.get_bind(), checkfirst=True)
