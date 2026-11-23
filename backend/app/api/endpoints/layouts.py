from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_any_role, require_role
from app.gis.hlb.editing_service import hlb_editing_service
from app.models.layout import LayoutStatus
from app.models.user import User, UserRole
from app.schemas.enumerator_assignment import (
    LayoutEnumeratorAssignmentsResponse,
)
from app.schemas.hlb import HlbListResponse
from app.schemas.layout import (
    GenerateHlbsRequest,
    HlbGenerationResultResponse,
    LayoutApprovalResponse,
    LayoutCreate,
    LayoutListResponse,
    LayoutResponse,
    LayoutUpdate,
    LayoutValidationResponse,
    LayoutVersionListResponse,
)
from app.schemas.supervisor_assignment import (
    SupervisorAssignmentRequest,
    SupervisorAssignmentResponse,
)
from app.services.layout_service import layout_service
from app.services.supervisor_service import supervisor_service

router = APIRouter()


@router.get("", response_model=LayoutListResponse)
def list_layouts(
    area_id: UUID | None = Query(
        default=None, description="Filter by administrative area ID"
    ),
    administrative_area_id: UUID | None = Query(
        default=None, description="Filter by administrative area ID alias"
    ),
    status: LayoutStatus | None = Query(
        default=None, description="Filter by layout status"
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    List layouts with area details, building count, and HLB count.
    - Deputy Tahsildar: Views layouts within administrative scope.
    - Supervisor: Strictly isolated to layouts assigned to them.
    """
    if current_user.role == UserRole.SUPERVISOR:
        res = supervisor_service.get_supervisor_layouts(
            db=db, supervisor_id=current_user.id
        )
        return {"items": res["items"], "total": res["total"]}

    filter_area_id = administrative_area_id or area_id
    return layout_service.list_layouts(
        db=db,
        area_id=filter_area_id,
        status_filter=status,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=LayoutResponse, status_code=status.HTTP_201_CREATED)
def create_layout(
    data: LayoutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Create a new layout for an administrative area.
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return layout_service.create_layout(db=db, data=data, user_id=current_user.id)


@router.put("/{id}", response_model=LayoutResponse)
@router.patch("/{id}", response_model=LayoutResponse)
def update_layout(
    id: UUID,
    data: LayoutUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Update layout details (name, target buildings, associated administrative areas).
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return layout_service.update_layout(db=db, layout_id=id, data=data)


@router.get("/{id}", response_model=LayoutResponse)
def get_layout(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Retrieve full layout details including active candidate version.
    - Deputy Tahsildar: Allowed.
    - Supervisor: Only if assigned to this layout; returns 403 otherwise.
    """
    if current_user.role == UserRole.SUPERVISOR:
        if not supervisor_service.check_supervisor_layout_access(
            db, layout_id=id, supervisor_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this layout",
            )
    return layout_service.get_layout_by_id(db=db, layout_id=id)


@router.get("/{id}/versions", response_model=LayoutVersionListResponse)
def get_layout_versions(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Retrieve all historical and candidate versions for a layout.
    - Deputy Tahsildar: Allowed.
    - Supervisor: Only if assigned to this layout; returns 403 otherwise.
    """
    if current_user.role == UserRole.SUPERVISOR:
        if not supervisor_service.check_supervisor_layout_access(
            db, layout_id=id, supervisor_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this layout",
            )
    return layout_service.get_layout_versions(db=db, layout_id=id)


@router.post("/{id}/generate-hlbs", response_model=HlbGenerationResultResponse)
def generate_hlbs(
    id: UUID,
    request: GenerateHlbsRequest = GenerateHlbsRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Generate candidate Houselisting Blocks (HLBs) using AI/GIS spatial
    optimization. Consumes real building footprints and Deputy's
    target_buildings_per_hlb.
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return layout_service.generate_hlbs(
        db=db,
        layout_id=id,
        user_id=current_user.id,
        target_buildings_per_hlb=request.target_buildings_per_hlb,
    )


@router.get("/{id}/hlbs", response_model=HlbListResponse)
def get_layout_hlbs(
    id: UUID,
    version_id: UUID | None = Query(
        default=None, description="Optional version ID to inspect"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Retrieve candidate HLBs and their boundaries for a layout.
    - Deputy Tahsildar: Allowed.
    - Supervisor: Only if assigned to this layout; returns 403 otherwise.
    """
    if current_user.role == UserRole.SUPERVISOR:
        if not supervisor_service.check_supervisor_layout_access(
            db, layout_id=id, supervisor_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this layout",
            )
    return layout_service.get_layout_hlbs(db=db, layout_id=id, version_id=version_id)


@router.post("/{id}/validate", response_model=LayoutValidationResponse)
def validate_layout(
    id: UUID,
    version_id: UUID | None = Query(
        default=None, description="Optional version ID to validate"
    ),
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Perform comprehensive validation checks on a layout's candidate HLB partition.
    Accessible by Deputy Tahsildar and Supervisor.
    """
    return hlb_editing_service.validate_layout(
        db=db, layout_id=id, version_id=version_id
    )


@router.post("/{id}/approve", response_model=LayoutApprovalResponse)
def approve_layout(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Approve candidate layout after successful validation, locking it into
    an immutable approved version.
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return hlb_editing_service.approve_layout(
        db=db, layout_id=id, user_id=current_user.id
    )


@router.post(
    "/{id}/assign-supervisor",
    response_model=SupervisorAssignmentResponse,
    status_code=status.HTTP_200_OK,
)
def assign_supervisor_to_layout(
    id: UUID,
    request: SupervisorAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Assign an approved layout to a primary Supervisor.
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return supervisor_service.assign_supervisor(
        db=db,
        layout_id=id,
        supervisor_id=request.supervisor_id,
        assigned_by_user_id=current_user.id,
    )


@router.get(
    "/{id}/supervisor",
    response_model=SupervisorAssignmentResponse | None,
)
def get_layout_supervisor(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Get the active Supervisor assignment for a layout.
    - Deputy Tahsildar: Allowed.
    - Supervisor: Allowed if assigned to this layout; returns 403 otherwise.
    """
    if current_user.role == UserRole.SUPERVISOR:
        if not supervisor_service.check_supervisor_layout_access(
            db, layout_id=id, supervisor_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this layout",
            )
    return supervisor_service.get_layout_supervisor_assignment(db=db, layout_id=id)


@router.get(
    "/{id}/supervisor-assignment",
    response_model=SupervisorAssignmentResponse | None,
)
def get_layout_supervisor_assignment_alias(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Alias for GET /{id}/supervisor.
    """
    return get_layout_supervisor(id=id, db=db, current_user=current_user)


@router.get(
    "/{id}/enumerator-assignments",
    response_model=LayoutEnumeratorAssignmentsResponse,
)
def get_layout_enumerator_assignments(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Get layout-level enumerator assignment summary and list of HLBs with their
    assigned enumerators. Accessible by Deputy Tahsildar and responsible Supervisor.
    """
    from app.services.enumerator_service import enumerator_service

    supervisor_id = (
        current_user.id if current_user.role == UserRole.SUPERVISOR else None
    )
    return enumerator_service.get_layout_assignment_summary(
        db=db, layout_id=id, supervisor_id=supervisor_id
    )
