import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class PersonReviewState(enum.StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    SUPERVISOR_VERIFIED = "SUPERVISOR_VERIFIED"
    ACCEPTED = "ACCEPTED"


class Person(Base):
    """
    Phase II Individual Person Census Entity.
    Belongs to a specific HouseholdRecord.
    """

    __tablename__ = "persons"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("household_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_number = Column(Integer, nullable=False)
    name = Column(String, nullable=False, index=True)
    relationship_to_head = Column(String, nullable=False, default="HEAD")
    sex = Column(String, nullable=False)  # MALE, FEMALE, TRANSGENDER
    age = Column(Integer, nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    marital_status = Column(String, nullable=True)
    answers = Column(JSON, nullable=True)
    questionnaire_version = Column(String, nullable=False, default="2.0")
    review_state = Column(
        Enum(PersonReviewState, name="person_review_state_enum"),
        default=PersonReviewState.DRAFT,
        nullable=False,
        index=True,
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
    household = relationship("HouseholdRecord", back_populates="persons")
