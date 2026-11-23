import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import relationship

from app.core.database import Base


class HlbCounter(Base):
    """
    Synchronized sequence counters per Houselisting Block (HLB).
    Guarantees unique, collision-free numbering for buildings and census houses.
    Survives device replacement and enumerator reassignment.
    Supports transactional atomic allocations and block-based offline reservations.
    """

    __tablename__ = "hlb_counters"

    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_building_no = Column(Integer, nullable=False, default=1)
    next_census_house_no = Column(Integer, nullable=False, default=1)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    hlb = relationship("HouselistingBlock", backref="counter")

