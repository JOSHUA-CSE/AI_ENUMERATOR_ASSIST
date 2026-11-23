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


class BuildingEditType(enum.StrEnum):
    ADD = "ADD"
    DELETE = "DELETE"
    MERGE = "MERGE"
    MOVE = "MOVE"
    RENUMBER = "RENUMBER"


class BuildingEditReviewStatus(enum.StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BuildingEdit(Base):
    """
    Audit and verification record for building-level modifications proposed in the field.
    Never silently destroys historical GIS or footprint data.
    """

    __tablename__ = "building_edits"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    building_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    edit_type = Column(
        Enum(BuildingEditType, name="building_edit_type_enum"),
        nullable=False,
        index=True,
    )
    proposed_changes = Column(JSON, nullable=False)
    reason = Column(String, nullable=False)
    requesting_user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_status = Column(
        Enum(BuildingEditReviewStatus, name="building_edit_review_status_enum"),
        default=BuildingEditReviewStatus.PENDING,
        nullable=False,
        index=True,
    )
    reviewer_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(String, nullable=True)
    version = Column(Integer, default=1, nullable=False)
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
    building = relationship("House", back_populates="edits")
    hlb = relationship("HouselistingBlock", backref="building_edits")
    requesting_user = relationship("User", foreign_keys=[requesting_user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
