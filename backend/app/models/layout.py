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


class LayoutStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    ASSIGNED = "ASSIGNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class LayoutVersionStatus(enum.StrEnum):
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class LayoutVersionSource(enum.StrEnum):
    AI_GENERATED = "AI_GENERATED"
    MANUAL_EDIT = "MANUAL_EDIT"
    APPROVED = "APPROVED"


class WorkloadUnit(enum.StrEnum):
    BUILDINGS = "BUILDINGS"
    CENSUS_HOUSES = "CENSUS_HOUSES"
    POPULATION = "POPULATION"


class Layout(Base):
    __tablename__ = "layouts"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    area_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("administrative_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False, index=True)
    target_hlb_building_count = Column(Integer, nullable=False, default=250)
    actual_building_count = Column(Integer, nullable=False, default=0)
    expected_hlb_count = Column(Integer, nullable=False, default=0)

    # Workload unit & estimations
    workload_unit = Column(
        Enum(WorkloadUnit, name="workload_unit_enum"),
        default=WorkloadUnit.BUILDINGS,
        nullable=False,
    )
    target_workload = Column(Integer, nullable=False, default=250)
    estimated_census_house_count = Column(Integer, nullable=True)
    estimated_population = Column(Integer, nullable=True)
    estimation_method = Column(String, nullable=True)
    estimation_provenance = Column(String, nullable=True)

    # PostGIS MULTIPOLYGON geometry in WGS84 (SRID 4326)
    boundary = Column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )
    boundary_status = Column(String, nullable=False, default="PROVISIONAL")
    status = Column(
        Enum(LayoutStatus, name="layout_status_enum"),
        nullable=False,
        default=LayoutStatus.DRAFT,
        index=True,
    )

    active_version_id = Column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    created_by = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at = Column(DateTime, nullable=True)

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

    @property
    def target_hlb_house_count(self) -> int:
        return self.target_hlb_building_count

    @target_hlb_house_count.setter
    def target_hlb_house_count(self, val: int) -> None:
        self.target_hlb_building_count = val

    @property
    def actual_house_count(self) -> int:
        return self.actual_building_count

    @actual_house_count.setter
    def actual_house_count(self, val: int) -> None:
        self.actual_building_count = val

    # Relationships
    area = relationship("AdministrativeArea", backref="layouts")
    associated_areas = relationship(
        "LayoutAdministrativeArea",
        back_populates="layout",
        cascade="all, delete-orphan",
    )
    versions = relationship(
        "LayoutVersion",
        back_populates="layout",
        cascade="all, delete-orphan",
        order_by="LayoutVersion.version_number.desc()",
    )
    hlbs = relationship(
        "HouselistingBlock",
        back_populates="layout",
        cascade="all, delete-orphan",
    )
    supervisor_assignments = relationship(
        "LayoutSupervisorAssignment",
        back_populates="layout",
        cascade="all, delete-orphan",
        order_by="LayoutSupervisorAssignment.assigned_at.desc()",
    )
    enumerator_assignments = relationship(
        "HlbEnumeratorAssignment",
        back_populates="layout",
        cascade="all, delete-orphan",
        order_by="HlbEnumeratorAssignment.assigned_at.desc()",
    )


class LayoutVersion(Base):
    __tablename__ = "layout_versions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layout_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("layouts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False, default=1)
    source = Column(
        Enum(LayoutVersionSource, name="layout_version_source_enum"),
        nullable=False,
        default=LayoutVersionSource.AI_GENERATED,
    )
    status = Column(
        Enum(LayoutVersionStatus, name="layout_version_status_enum"),
        nullable=False,
        default=LayoutVersionStatus.CANDIDATE,
        index=True,
    )
    target_buildings_per_hlb = Column(Integer, nullable=False, default=250)
    workload_unit = Column(
        Enum(WorkloadUnit, name="workload_unit_enum"),
        default=WorkloadUnit.BUILDINGS,
        nullable=False,
    )
    target_workload = Column(Integer, nullable=False, default=250)
    estimated_census_house_count = Column(Integer, nullable=True)
    estimated_population = Column(Integer, nullable=True)
    estimation_method = Column(String, nullable=True)
    estimation_provenance = Column(String, nullable=True)
    total_buildings = Column(Integer, nullable=False, default=0)
    hlb_count = Column(Integer, nullable=False, default=0)
    boundary_status = Column(String, nullable=False, default="PROVISIONAL")
    quality_score = Column(Float, nullable=True)
    validation_status = Column(String, nullable=False, default="VALID")
    validation_summary = Column(JSON, nullable=True)
    generation_metadata = Column(JSON, nullable=True)

    @property
    def target_houses_per_hlb(self) -> int:
        return self.target_buildings_per_hlb

    @target_houses_per_hlb.setter
    def target_houses_per_hlb(self, val: int) -> None:
        self.target_buildings_per_hlb = val

    created_by = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    layout = relationship("Layout", back_populates="versions")
    hlbs = relationship(
        "HouselistingBlock",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="HouselistingBlock.block_code.asc()",
    )


class LayoutAdministrativeArea(Base):
    __tablename__ = "layout_administrative_areas"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layout_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("layouts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    area_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("administrative_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    layout = relationship("Layout", back_populates="associated_areas")
    area = relationship("AdministrativeArea", backref="layout_associations")

