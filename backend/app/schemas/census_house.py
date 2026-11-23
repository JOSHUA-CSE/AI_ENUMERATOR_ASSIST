from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.census_house import CensusHouseListingState, CensusHouseUseCode


class CensusHouseBase(BaseModel):
    census_house_number: str = Field(
        ..., description="Local census house sequence number (e.g. 'CH-1', 'Flat 101')"
    )
    use_code: CensusHouseUseCode = Field(default=CensusHouseUseCode.RESIDENTIAL)
    listing_state: CensusHouseListingState = Field(
        default=CensusHouseListingState.NOT_VISITED
    )
    latitude: float | None = None
    longitude: float | None = None
    geotag_accuracy_m: float | None = None
    notes: str | None = None


class CensusHouseCreate(CensusHouseBase):
    building_id: UUID
    hlb_id: UUID


class CensusHouseUpdate(BaseModel):
    census_house_number: str | None = None
    use_code: CensusHouseUseCode | None = None
    listing_state: CensusHouseListingState | None = None
    latitude: float | None = None
    longitude: float | None = None
    geotag_accuracy_m: float | None = None
    notes: str | None = None
    locked_attempts: int | None = None


class CensusHouseResponse(CensusHouseBase):
    id: UUID
    building_id: UUID
    hlb_id: UUID
    visited_at: datetime | None = None
    locked_attempts: int = 0
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    household_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CensusHouseListResponse(BaseModel):
    items: list[CensusHouseResponse]
    total: int
