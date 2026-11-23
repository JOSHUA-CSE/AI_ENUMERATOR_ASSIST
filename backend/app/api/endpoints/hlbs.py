from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_any_role, require_role
from app.gis.hlb.editing_service import hlb_editing_service
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import House
from app.models.user import User, UserRole
from app.schemas.enumerator_assignment import (
    EnumeratorAssignmentRequest,
    EnumeratorAssignmentResponse,
)
from app.schemas.hlb import (
    HlbBoundaryUpdateRequest,
    HlbDetailResponse,
    HlbMergePreviewResponse,
    HlbMergeRequest,
    HlbMergeResponse,
    HlbResponse,
    HlbSplitPreviewResponse,
    HlbSplitRequest,
    HlbSplitResponse,
)
from app.services.enumerator_service import enumerator_service

router = APIRouter()


@router.get("/{id}", response_model=HlbDetailResponse)
def get_hlb(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role(
            [UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR, UserRole.ENUMERATOR]
        )
    ),
):
    """
    Retrieve single HLB detail with boundary, metrics, and assigned building IDs.
    - Deputy Tahsildar: Allowed.
    - Supervisor: Only allowed if assigned to the HLB's layout; returns 403 otherwise.
    - Enumerator: Only allowed if assigned to this specific HLB; returns 403 otherwise.
    """
    from fastapi import HTTPException

    hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == id).first()
    if not hlb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Houselisting Block with ID {id} not found",
        )

    if current_user.role == UserRole.SUPERVISOR:
        from app.services.supervisor_service import supervisor_service

        if not supervisor_service.check_supervisor_layout_access(
            db, layout_id=hlb.layout_id, supervisor_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this HLB",
            )

    if current_user.role == UserRole.ENUMERATOR:
        if not enumerator_service.check_enumerator_hlb_access(
            db, hlb_id=id, enumerator_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this HLB",
            )

    formatted = hlb_editing_service._format_hlb_response(hlb)

    # Load assigned buildings
    houses = (
        db.query(House.id, House.building_reference, House.latitude, House.longitude)
        .join(HlbHouse, HlbHouse.house_id == House.id)
        .filter(HlbHouse.hlb_id == id)
        .all()
    )
    formatted["houses"] = [
        {
            "id": h.id,
            "building_reference": h.building_reference,
            "latitude": h.latitude,
            "longitude": h.longitude,
        }
        for h in houses
    ]

    return formatted


@router.post(
    "/{id}/assign-enumerator",
    response_model=EnumeratorAssignmentResponse,
    status_code=status.HTTP_200_OK,
)
def assign_enumerator_to_hlb(
    id: UUID,
    request: EnumeratorAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Assign a Primary Enumerator to an HLB.
    Authorized for the responsible SUPERVISOR only.
    """
    return enumerator_service.assign_enumerator(
        db=db,
        hlb_id=id,
        enumerator_id=request.enumerator_id,
        supervisor_id=current_user.id,
    )


@router.get(
    "/{id}/enumerator",
    response_model=EnumeratorAssignmentResponse | None,
)
def get_hlb_enumerator(
    id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_any_role(
            [UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR, UserRole.ENUMERATOR]
        )
    ),
):
    """
    Get the active Primary Enumerator assignment for an HLB.
    """
    return enumerator_service.get_hlb_assignment(db=db, hlb_id=id)


@router.get(
    "/{id}/enumerator-assignment",
    response_model=EnumeratorAssignmentResponse | None,
)
def get_hlb_enumerator_assignment_alias(
    id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_any_role(
            [UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR, UserRole.ENUMERATOR]
        )
    ),
):
    """
    Alias for getting active Primary Enumerator assignment for an HLB.
    """
    return enumerator_service.get_hlb_assignment(db=db, hlb_id=id)


@router.patch("/{id}/boundary", response_model=HlbResponse)
def edit_hlb_boundary(
    id: UUID,
    request: HlbBoundaryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Update an HLB's boundary geometry and recalculate spatial building memberships.
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return hlb_editing_service.edit_hlb_boundary(
        db=db,
        hlb_id=id,
        new_boundary_geojson=request.boundary,
        user_id=current_user.id,
    )


@router.post("/{id}/split/preview", response_model=HlbSplitPreviewResponse)
def preview_split_hlb(
    id: UUID,
    request: HlbSplitRequest = HlbSplitRequest(),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Generate preview of an HLB split without committing changes.
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return hlb_editing_service.preview_split_hlb(
        db=db,
        hlb_id=id,
        split_method=request.split_method,
        split_ratio=request.split_ratio,
        target_building_count=request.target_building_count,
        split_line_coordinates=request.split_line_coordinates,
    )


@router.post("/{id}/split", response_model=HlbSplitResponse)
def split_hlb(
    id: UUID,
    request: HlbSplitRequest = HlbSplitRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Spatially split one HLB into two candidate HLBs using Auto, Target,
    or Draw-Line methods. Authorized for DEPUTY_TAHSILDAR only.
    """
    return hlb_editing_service.split_hlb(
        db=db,
        hlb_id=id,
        user_id=current_user.id,
        split_ratio=request.split_ratio,
        split_method=request.split_method,
        target_building_count=request.target_building_count,
        split_line_coordinates=request.split_line_coordinates,
    )


@router.post("/merge/preview", response_model=HlbMergePreviewResponse)
def preview_merge_hlbs(
    request: HlbMergeRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Preview the combination of two candidate HLBs and validate geographic adjacency.
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return hlb_editing_service.preview_merge_hlbs(
        db=db,
        hlb_id_1=request.hlb_id_1,
        hlb_id_2=request.hlb_id_2,
    )


@router.post("/merge", response_model=HlbMergeResponse)
def merge_hlbs(
    request: HlbMergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Merge two adjacent candidate HLBs within the same layout into one combined HLB.
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return hlb_editing_service.merge_hlbs(
        db=db,
        hlb_id_1=request.hlb_id_1,
        hlb_id_2=request.hlb_id_2,
        user_id=current_user.id,
    )


class CounterAllocationRequest(BaseModel):
    building_count: int = 0
    census_house_count: int = 0


class CounterAllocationResponse(BaseModel):
    hlb_id: UUID
    allocated_building_numbers: list[int]
    allocated_census_house_numbers: list[int]
    next_building_no: int
    next_census_house_no: int
    version: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("/{hlb_id}/counters/allocate", response_model=CounterAllocationResponse)
def allocate_hlb_counters(
    hlb_id: UUID,
    body: CounterAllocationRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_any_role([UserRole.ENUMERATOR, UserRole.SUPERVISOR, UserRole.DEPUTY_TAHSILDAR])),
):
    """
    Requirement C2: Synchronized HLB sequence counters.
    Allocates collision-free numbers for buildings and census houses within HLB scope.
    """
    from app.services.counter_service import counter_service
    return counter_service.allocate_numbers(
        db=db,
        hlb_id=hlb_id,
        building_count=body.building_count,
        census_house_count=body.census_house_count,
    )
