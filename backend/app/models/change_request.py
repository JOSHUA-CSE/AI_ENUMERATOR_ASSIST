import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ChangeRequestType(enum.StrEnum):
    ADDITIONAL_ENUMERATOR = "ADDITIONAL_ENUMERATOR"
    EXTRA_ENUMERATOR = "EXTRA_ENUMERATOR"
    HLB_SPLIT = "HLB_SPLIT"
    SPLIT_HLB = "SPLIT_HLB"
    HLB_MERGE = "HLB_MERGE"
    BOUNDARY_DISPUTE = "BOUNDARY_DISPUTE"
    ENUMERATOR_REASSIGNMENT = "ENUMERATOR_REASSIGNMENT"
    REASSIGN = "REASSIGN"
    TECHNICAL_ISSUE = "TECHNICAL_ISSUE"
    FIELDWORK_CLARIFICATION = "FIELDWORK_CLARIFICATION"


class ChangeRequestStatus(enum.StrEnum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class ChangeRequestPriority(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeRequest(Base):
    """
    Supervisor and Deputy administrative change request and issue thread mechanism.
    """

    __tablename__ = "change_requests"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_type = Column(
        Enum(ChangeRequestType, name="change_request_type_enum"),
        nullable=False,
        index=True,
    )
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    layout_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("layouts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requesting_user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_reviewer_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    priority = Column(
        Enum(ChangeRequestPriority, name="change_request_priority_enum"),
        default=ChangeRequestPriority.MEDIUM,
        nullable=False,
    )
    status = Column(
        Enum(ChangeRequestStatus, name="change_request_status_enum"),
        default=ChangeRequestStatus.OPEN,
        nullable=False,
        index=True,
    )
    description = Column(String, nullable=False)
    resolution_notes = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    resolved_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    requesting_user = relationship("User", foreign_keys=[requesting_user_id])
    assigned_reviewer = relationship("User", foreign_keys=[assigned_reviewer_id])
    hlb = relationship("HouselistingBlock", backref="change_requests")
    layout = relationship("Layout", backref="change_requests")
    messages = relationship(
        "ChangeRequestMessage",
        back_populates="change_request",
        cascade="all, delete-orphan",
        order_by="ChangeRequestMessage.created_at.asc()",
    )


class ChangeRequestMessage(Base):
    """
    Message thread entries for administrative change requests and issue discussions.
    """

    __tablename__ = "change_request_messages"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_request_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("change_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_role = Column(String, nullable=False)
    message = Column(String, nullable=False)
    attachments = Column(JSON, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    author = relationship("User", foreign_keys=[author_id])
    change_request = relationship("ChangeRequest", back_populates="messages")
