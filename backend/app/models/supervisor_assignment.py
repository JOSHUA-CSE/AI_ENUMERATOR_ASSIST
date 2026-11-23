import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


class SupervisorAssignmentStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class LayoutSupervisorAssignment(Base):
    """
    Mapping between an approved layout and its primary responsible Supervisor.
    A Supervisor is assigned to the complete approved layout.
    """

    __tablename__ = "layout_supervisor_assignments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layout_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("layouts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supervisor_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    status = Column(
        Enum(SupervisorAssignmentStatus, name="supervisor_assignment_status_enum"),
        nullable=False,
        default=SupervisorAssignmentStatus.ACTIVE,
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
    layout = relationship("Layout", back_populates="supervisor_assignments")
    supervisor = relationship(
        "User",
        foreign_keys=[supervisor_id],
        backref="supervisor_layout_assignments",
    )
    assigner = relationship(
        "User",
        foreign_keys=[assigned_by],
    )
