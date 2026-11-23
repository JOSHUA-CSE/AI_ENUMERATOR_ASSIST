import enum
import uuid
from datetime import UTC, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class HlbStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    ASSIGNED = "ASSIGNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class HlbValidationStatus(enum.StrEnum):
    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"


class HouselistingBlock(Base):
    __tablename__ = "houselisting_blocks"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layout_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("layouts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("layout_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_code = Column(String, nullable=False, index=True)  # e.g. "HLB-001"
    name = Column(String, nullable=True)
    target_building_count = Column(Integer, nullable=False, default=250)
    actual_building_count = Column(Integer, nullable=False, default=0)
    estimated_census_house_count = Column(Integer, nullable=True)
    estimated_population = Column(Integer, nullable=True)

    @property
    def target_house_count(self) -> int:
        return self.target_building_count

    @target_house_count.setter
    def target_house_count(self, val: int) -> None:
        self.target_building_count = val

    @property
    def actual_house_count(self) -> int:
        return self.actual_building_count

    @actual_house_count.setter
    def actual_house_count(self, val: int) -> None:
        self.actual_building_count = val

    # PostGIS MULTIPOLYGON geometry in WGS84 (SRID 4326)
    boundary = Column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )
    boundary_status = Column(String, nullable=False, default="PROVISIONAL")
    status = Column(
        Enum(HlbStatus, name="hlb_status_enum"),
        nullable=False,
        default=HlbStatus.GENERATED,
        index=True,
    )
    quality_score = Column(Float, nullable=True)
    validation_status = Column(
        Enum(HlbValidationStatus, name="hlb_validation_status_enum"),
        nullable=False,
        default=HlbValidationStatus.VALID,
        index=True,
    )
    validation_details = Column(JSON, nullable=True)

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
    layout = relationship("Layout", back_populates="hlbs")
    version = relationship("LayoutVersion", back_populates="hlbs")
    house_assignments = relationship(
        "HlbHouse",
        back_populates="hlb",
        cascade="all, delete-orphan",
    )
    enumerator_assignments = relationship(
        "HlbEnumeratorAssignment",
        back_populates="hlb",
        cascade="all, delete-orphan",
    )


class HlbHouse(Base):
    __tablename__ = "hlb_houses"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    house_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    status = Column(String, nullable=False, default="ASSIGNED")

    # Relationships
    hlb = relationship("HouselistingBlock", back_populates="house_assignments")
    house = relationship("House", back_populates="hlb_assignments")
