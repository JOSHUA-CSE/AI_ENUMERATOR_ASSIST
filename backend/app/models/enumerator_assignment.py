import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


class EnumeratorAssignmentStatus(enum.StrEnum):
    ASSIGNED = "ASSIGNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class HlbEnumeratorAssignment(Base):
    """
    Mapping between an approved Houselisting Block (HLB) and its primary
    responsible Enumerator. Rule: 1 HLB -> 1 Primary Enumerator.
    """

    __tablename__ = "hlb_enumerator_assignments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    layout_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("layouts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enumerator_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supervisor_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    status = Column(
        Enum(EnumeratorAssignmentStatus, name="enumerator_assignment_status_enum"),
        nullable=False,
        default=EnumeratorAssignmentStatus.ACTIVE,
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
    hlb = relationship("HouselistingBlock", back_populates="enumerator_assignments")
    layout = relationship("Layout", back_populates="enumerator_assignments")
    enumerator = relationship(
        "User",
        foreign_keys=[enumerator_id],
        backref="hlb_assignments",
    )
    supervisor = relationship(
        "User",
        foreign_keys=[supervisor_id],
    )
