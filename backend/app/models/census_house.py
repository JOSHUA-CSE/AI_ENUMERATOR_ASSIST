import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
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


class CensusHouseListingState(enum.StrEnum):
    NOT_VISITED = "NOT_VISITED"
    LISTED = "LISTED"
    VACANT = "VACANT"
    NON_RESIDENTIAL = "NON_RESIDENTIAL"
    LOCKED = "LOCKED"


class CensusHouseUseCode(enum.StrEnum):
    RESIDENTIAL = "RESIDENTIAL"
    RESIDENTIAL_CUM_COMMERCIAL = "RESIDENTIAL_CUM_COMMERCIAL"
    COMMERCIAL = "COMMERCIAL"
    WORKSHOP_FACTORY = "WORKSHOP_FACTORY"
    PLACE_OF_WORSHIP = "PLACE_OF_WORSHIP"
    INSTITUTIONAL = "INSTITUTIONAL"
    VACANT = "VACANT"
    OTHER = "OTHER"


class CensusHouse(Base):
    """
    Authoritative Census House entity inside a physical Building structure.
    A Building can contain multiple Census Houses (e.g. flats, shops, separate residential units).
    A Census House may contain 0 to N Households.
    """

    __tablename__ = "census_houses"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    building_id = Column(
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
    census_house_number = Column(String, nullable=False, index=True)
    use_code = Column(
        Enum(CensusHouseUseCode, name="census_house_use_code_enum"),
        default=CensusHouseUseCode.RESIDENTIAL,
        nullable=False,
    )
    listing_state = Column(
        Enum(CensusHouseListingState, name="census_house_listing_state_enum"),
        default=CensusHouseListingState.NOT_VISITED,
        nullable=False,
        index=True,
    )
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geotag_accuracy_m = Column(Float, nullable=True)
    visited_at = Column(DateTime, nullable=True)
    locked_attempts = Column(Integer, nullable=False, default=0)
    notes = Column(String, nullable=True)
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
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    building = relationship("House", back_populates="census_houses")
    hlb = relationship("HouselistingBlock", backref="census_houses")
    household_records = relationship(
        "HouseholdRecord",
        back_populates="census_house",
        cascade="all, delete-orphan",
    )
