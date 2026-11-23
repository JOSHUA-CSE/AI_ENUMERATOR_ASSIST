import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import relationship, synonym

from app.core.database import Base


class HouseholdRecordStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"


class HouseholdReviewState(enum.StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    SUPERVISOR_VERIFIED = "SUPERVISOR_VERIFIED"
    ACCEPTED = "ACCEPTED"
    RETURNED_FOR_CORRECTION = "RETURNED_FOR_CORRECTION"


class HouseholdSyncStatus(enum.StrEnum):
    LOCAL = "LOCAL"
    SYNCED = "SYNCED"
    CONFLICT = "CONFLICT"


class RevisitRecordStatus(enum.StrEnum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class FieldworkBuildingStatus(enum.StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    LOCKED = "LOCKED"
    REVISIT_REQUIRED = "REVISIT_REQUIRED"


class SyncOperationType(enum.StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    STATUS_UPDATE = "STATUS_UPDATE"
    DELETE = "DELETE"


class SyncEntityType(enum.StrEnum):
    BUILDING = "BUILDING"
    CENSUS_HOUSE = "CENSUS_HOUSE"
    HOUSEHOLD = "HOUSEHOLD"
    PERSON = "PERSON"
    BUILDING_EDIT = "BUILDING_EDIT"
    GPS_LOG = "GPS_LOG"
    GPS_TRACK = "GPS_TRACK"
    GPS_BATCH = "GPS_BATCH"
    BOUNDARY_EVENT = "BOUNDARY_EVENT"
    BUILDING_STATUS = "BUILDING_STATUS"
    STATUS = "STATUS"
    REVISIT = "REVISIT"
    CHANGE_REQUEST = "CHANGE_REQUEST"
    REVIEW_UPDATE = "REVIEW_UPDATE"


class SyncOperationStatus(enum.StrEnum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    CONFLICT = "CONFLICT"
    QUARANTINE = "QUARANTINE"


class HouseholdRecord(Base):
    """
    Socio-demographic census questionnaire data for households enumerated on the ground.
    One building may contain multiple household records.
    """

    __tablename__ = "household_records"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    census_house_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("census_houses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    house_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enumerator_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    household_number = Column(String, nullable=False, index=True)
    head_name = Column(String, nullable=False, index=True)
    total_members = Column(Integer, nullable=False, default=1)
    male_count = Column(Integer, nullable=False, default=0)
    female_count = Column(Integer, nullable=False, default=0)
    transgender_count = Column(Integer, nullable=False, default=0)
    ownership_status = Column(String, nullable=False, default="OWNED")
    drinking_water_source = Column(String, nullable=True)
    lighting_source = Column(String, nullable=True)
    latrine_facility = Column(String, nullable=True)
    data = Column(JSON, nullable=True)
    answers = synonym("data")
    source = Column(String, nullable=False, default="FORM")
    questionnaire_version = Column(String, nullable=False, default="1.0")
    status = Column(
        Enum(HouseholdRecordStatus, name="household_record_status_enum"),
        nullable=False,
        default=HouseholdRecordStatus.DRAFT,
        index=True,
    )
    review_state = Column(
        Enum(HouseholdReviewState, name="household_review_state_enum"),
        nullable=False,
        default=HouseholdReviewState.DRAFT,
        index=True,
    )
    rejection_reason = Column(String, nullable=True)
    supervisor_comment = Column(String, nullable=True)
    verified_by = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at = Column(DateTime, nullable=True)
    sync_status = Column(
        Enum(HouseholdSyncStatus, name="household_sync_status_enum"),
        nullable=False,
        default=HouseholdSyncStatus.SYNCED,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    captured_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
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
    house = relationship("House", backref="household_records")
    census_house = relationship("CensusHouse", back_populates="household_records")
    hlb = relationship("HouselistingBlock", backref="household_records")
    enumerator = relationship(
        "User", foreign_keys=[enumerator_id], backref="household_records"
    )
    verifier = relationship("User", foreign_keys=[verified_by])
    persons = relationship(
        "Person",
        back_populates="household",
        cascade="all, delete-orphan",
    )


class HouseFieldworkStatus(Base):
    """
    Tracks ground fieldwork status per house/building and HLB assignment.
    """

    __tablename__ = "house_fieldwork_status"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    house_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enumerator_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(FieldworkBuildingStatus, name="fieldwork_building_status_enum"),
        nullable=False,
        default=FieldworkBuildingStatus.PENDING,
        index=True,
    )
    household_count = Column(Integer, nullable=False, default=0)
    last_updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_by = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    house = relationship("House", backref="fieldwork_statuses")
    hlb = relationship("HouselistingBlock", backref="house_fieldwork_statuses")
    enumerator = relationship("User", foreign_keys=[enumerator_id])


class RevisitRecord(Base):
    """
    Records revisits recommended or required during fieldwork.
    """

    __tablename__ = "revisits"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    house_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enumerator_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason = Column(String, nullable=False)
    notes = Column(String, nullable=True)
    status = Column(
        Enum(RevisitRecordStatus, name="revisit_record_status_enum"),
        nullable=False,
        default=RevisitRecordStatus.PENDING,
        index=True,
    )
    recommended_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    house = relationship("House", backref="revisits")
    hlb = relationship("HouselistingBlock", backref="revisits")
    enumerator = relationship("User", backref="revisits")


class GpsTrack(Base):
    """
    GPS observation tracks captured during fieldwork.
    """

    __tablename__ = "gps_tracks"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enumerator_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    house_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy_meters = Column(Float, nullable=True)
    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    source = Column(String, nullable=False, default="OFFLINE")

    # Relationships
    enumerator = relationship("User", backref="gps_tracks")
    hlb = relationship("HouselistingBlock", backref="gps_tracks")
    house = relationship("House", backref="gps_tracks")


class SyncOperation(Base):
    """
    Server-side record of synchronized operations enforcing strict idempotency.
    """

    __tablename__ = "sync_operations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    device_id = Column(String, nullable=True, index=True)
    local_entity_id = Column(String, nullable=True, index=True)
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_type = Column(
        Enum(SyncOperationType, name="sync_operation_type_enum"),
        nullable=False,
    )
    entity_type = Column(
        Enum(SyncEntityType, name="sync_entity_type_enum"),
        nullable=False,
    )
    entity_id = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=True)
    client_timestamp = Column(DateTime, nullable=False)
    server_timestamp = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    status = Column(
        Enum(SyncOperationStatus, name="sync_operation_status_enum"),
        nullable=False,
        default=SyncOperationStatus.SYNCED,
        index=True,
    )
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(String, nullable=True)
    response_data = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "entity_type",
            "local_entity_id",
            name="uq_sync_device_entity_local",
        ),
    )

    # Relationships
    user = relationship("User", backref="sync_operations")


class SupervisorCorrection(Base):
    """
    Versioned, non-destructive supervisor fieldwork corrections.
    Preserves original enumerator provenance while storing field modifications.
    """

    __tablename__ = "supervisor_corrections"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(Uuid(as_uuid=True), nullable=False, index=True)
    original_version = Column(Integer, nullable=False)
    corrected_version = Column(Integer, nullable=False)
    author_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    author_role = Column(String, nullable=False, default="SUPERVISOR")
    changed_fields = Column(JSON, nullable=False)  # List of modified field names (NO PII)
    previous_data = Column(JSON, nullable=True)
    corrected_data = Column(JSON, nullable=False)
    correction_reason = Column(String, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    author = relationship("User", foreign_keys=[author_id])
