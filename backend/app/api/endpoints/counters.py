from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.counter_service import counter_service

router = APIRouter()


class CounterAllocateRequest(BaseModel):
    hlb_id: UUID
    building_count: int = Field(default=0, ge=0)
    census_house_count: int = Field(default=0, ge=0)


class CounterAllocateResponse(BaseModel):
    hlb_id: UUID
    building_number_start: int | None = None
    building_number_end: int | None = None
    census_house_number_start: int | None = None
    census_house_number_end: int | None = None
    allocated_building_numbers: list[int]
    allocated_census_house_numbers: list[int]
    next_building_no: int
    next_census_house_no: int
    version: int


@router.post("/allocate", response_model=CounterAllocateResponse, summary="Atomically allocate sequence numbers for an HLB")
def allocate_counters(
    body: CounterAllocateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Requirement C1: Synchronized numbering sequence allocation.
    Atomically allocates contiguous building and census house numbers within an HLB.
    """
    res = counter_service.allocate_numbers(
        db=db,
        hlb_id=body.hlb_id,
        building_count=body.building_count,
        census_house_count=body.census_house_count,
    )
    b_nums = res["allocated_building_numbers"]
    ch_nums = res["allocated_census_house_numbers"]

    return {
        "hlb_id": res["hlb_id"],
        "building_number_start": b_nums[0] if b_nums else None,
        "building_number_end": b_nums[-1] if b_nums else None,
        "census_house_number_start": ch_nums[0] if ch_nums else None,
        "census_house_number_end": ch_nums[-1] if ch_nums else None,
        "allocated_building_numbers": b_nums,
        "allocated_census_house_numbers": ch_nums,
        "next_building_no": res["next_building_no"],
        "next_census_house_no": res["next_census_house_no"],
        "version": res["version"],
    }

