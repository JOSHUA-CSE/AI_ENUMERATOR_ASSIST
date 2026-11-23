import enum
import uuid
from datetime import UTC, datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


class BuildingSourceType(enum.StrEnum):
    SATELLITE_DETECTED = "SATELLITE_DETECTED"
    DEVELOPMENT_DATA = "DEVELOPMENT_DATA"
    MANUAL = "MANUAL"
    GOVERNMENT_IMPORT = "GOVERNMENT_IMPORT"
    FIELD_VERIFIED = "FIELD_VERIFIED"
    FIELD_DISCOVERED = "FIELD_DISCOVERED"


class BuildingFieldStatus(enum.StrEnum):
    UNVERIFIED = "UNVERIFIED"
    CONFIRMED = "CONFIRMED"
    FALSE_DETECTION = "FALSE_DETECTION"
    FIELD_ADDED = "FIELD_ADDED"


class House(Base):
    """
    Physical structure / building footprint master entity.
    Serves as the root structure containing 1..N Census Houses.
    """

    __tablename__ = "houses"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    area_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("administrative_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    building_reference = Column(String, nullable=True, index=True)
    house_number = Column(String, nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # PostGIS POINT centroid geometry in WGS84 (SRID 4326)
    location = Column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )

    # Optional PostGIS MULTIPOLYGON building footprint geometry
    footprint = Column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326),
        nullable=True,
    )

    # Satellite & building detection metadata
    source_type = Column(
        Enum(BuildingSourceType, name="building_source_type_enum"),
        default=BuildingSourceType.SATELLITE_DETECTED,
        nullable=False,
        index=True,
    )
    detection_confidence = Column(Float, nullable=True)
    detected_at = Column(DateTime, nullable=True)
    imagery_source = Column(String, nullable=True)
    imagery_date = Column(DateTime, nullable=True)

    # Field operations & listing closure
    field_status = Column(
        Enum(BuildingFieldStatus, name="building_field_status_enum"),
        default=BuildingFieldStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )
    listing_closed = Column(Boolean, default=False, nullable=False)
    listing_closed_at = Column(DateTime, nullable=True)

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
    area = relationship("AdministrativeArea", back_populates="houses")
    hlb_assignments = relationship(
        "HlbHouse",
        back_populates="house",
        cascade="all, delete-orphan",
    )
    census_houses = relationship(
        "CensusHouse",
        back_populates="building",
        cascade="all, delete-orphan",
    )
    edits = relationship(
        "BuildingEdit",
        back_populates="building",
        cascade="all, delete-orphan",
    )
