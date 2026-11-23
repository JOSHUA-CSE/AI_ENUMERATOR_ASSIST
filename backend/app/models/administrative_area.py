import enum
import uuid
from datetime import UTC, datetime

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


class AreaType(enum.StrEnum):
    VILLAGE = "VILLAGE"
    WARD = "WARD"
    TALUK = "TALUK"
    DISTRICT = "DISTRICT"


class BoundaryStatus(enum.StrEnum):
    OFFICIAL = "OFFICIAL"
    PROVISIONAL = "PROVISIONAL"
    ESTIMATED = "ESTIMATED"
    UNVERIFIED = "UNVERIFIED"


class AdministrativeArea(Base):
    __tablename__ = "administrative_areas"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    type = Column(Enum(AreaType), nullable=False, default=AreaType.VILLAGE)
    code = Column(String, unique=True, nullable=False, index=True)
    parent_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("administrative_areas.id", ondelete="SET NULL"),
        nullable=True,
    )
    # PostGIS MULTIPOLYGON geometry in WGS84 (SRID 4326)
    boundary = Column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )
    boundary_status = Column(String, nullable=False, default=BoundaryStatus.PROVISIONAL.value)
    status = Column(String, nullable=False, default="ACTIVE")

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    parent = relationship(
        "AdministrativeArea",
        remote_side=[id],
        backref="children",
    )
    houses = relationship(
        "House",
        back_populates="area",
        cascade="all, delete-orphan",
    )
