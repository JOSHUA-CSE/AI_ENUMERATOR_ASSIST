from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_any_role, require_role
from app.models.hlb import HouselistingBlock
from app.models.user import User, UserRole
from app.schemas.building_edit import (
    BuildingEditListResponse,
    BuildingEditResponse,
    BuildingEditReviewRequest,
)
from app.schemas.gps import SupervisorEnumeratorMonitoringResponse
from app.schemas.change_request import (
    ChangeRequestCreate,
    ChangeRequestListResponse,
    ChangeRequestMessageCreate,
    ChangeRequestMessageListResponse,
    ChangeRequestMessageResponse,
    ChangeRequestResponse,
)
from app.schemas.submission import (
    HouseholdReturnRequest,
    HouseholdSubmissionListResponse,
    HouseholdSubmissionResponse,
    HouseholdVerificationRequest,
    QuarantinedOperationReviewRequest,
    SupervisorCorrectionCreate,
    SupervisorCorrectionResponse,
)
from app.schemas.supervisor_assignment import (
    SupervisorLayoutListResponse,
    SupervisorLayoutResponse,
    SupervisorListResponse,
)
from app.schemas.supervisor_progress import (
    SupervisorHlbProgressResponse,
    SupervisorLayoutProgressResponse,
    SupervisorOverallProgressResponse,
)
from app.services.supervisor_service import supervisor_service

# Router for /api/v1/supervisors
router = APIRouter()

# Router for /api/v1/supervisor
supervisor_router = APIRouter()


@router.get("", response_model=SupervisorListResponse)
def list_supervisors(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    List all active supervisors available for layout assignment.
    Authorized for DEPUTY_TAHSILDAR only.
    """
    return supervisor_service.list_supervisors(db=db)


@supervisor_router.get("/layouts", response_model=SupervisorLayoutListResponse)
def get_my_assigned_layouts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Retrieve all layouts actively assigned to the authenticated supervisor.
    Authorized for SUPERVISOR only.
    Derived strictly from authenticated JWT identity.
    """
    return supervisor_service.get_supervisor_layouts(
        db=db, supervisor_id=current_user.id
    )


@supervisor_router.get(
    "/layouts/progress",
    response_model=SupervisorOverallProgressResponse,
    summary="Retrieve fieldwork progress across all layouts assigned to the supervisor",
)
@supervisor_router.get(
    "/progress",
    response_model=SupervisorOverallProgressResponse,
    summary="Alias: Retrieve fieldwork progress across all assigned layouts",
)
def get_supervisor_overall_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Retrieve progress metrics aggregated across all layouts
    actively assigned to this supervisor.
    Authorized for SUPERVISOR only.
    """
    return supervisor_service.get_supervisor_overall_progress(
        db=db, supervisor_id=current_user.id
    )


@supervisor_router.get(
    "/layouts/{layout_id}/progress",
    response_model=SupervisorLayoutProgressResponse,
    summary="Retrieve aggregated fieldwork progress for an assigned layout",
)
def get_layout_progress(
    layout_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role([UserRole.SUPERVISOR, UserRole.DEPUTY_TAHSILDAR])
    ),
):
    """
    Retrieve fieldwork progress metrics for a layout and all its HLBs.
    - Authorized for the assigned SUPERVISOR or DEPUTY_TAHSILDAR.
    - Enforces 403 Forbidden if a supervisor attempts to access another
      supervisor's layout.
    """
    if current_user.role == UserRole.SUPERVISOR:
        if not supervisor_service.check_supervisor_layout_access(
            db, layout_id, current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this layout's progress.",
            )
    return supervisor_service.get_layout_progress(db=db, layout_id=layout_id)


@supervisor_router.get(
    "/hlbs/{hlb_id}/progress",
    response_model=SupervisorHlbProgressResponse,
    summary="Retrieve detailed fieldwork progress for an assigned HLB",
)
def get_hlb_progress(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_role([UserRole.SUPERVISOR, UserRole.DEPUTY_TAHSILDAR])
    ),
):
    """
    Retrieve authoritative fieldwork progress for an individual HLB.
    - Authorized for the assigned SUPERVISOR or DEPUTY_TAHSILDAR.
    - Enforces 403 Forbidden if a supervisor attempts to access an HLB not in
      their layout.
    """
    hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
    if not hlb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Houselisting Block '{hlb_id}' not found.",
        )

    if current_user.role == UserRole.SUPERVISOR:
        if not supervisor_service.check_supervisor_layout_access(
            db, hlb.layout_id, current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this HLB's progress.",
            )

    return supervisor_service.get_hlb_progress(db=db, hlb_id=hlb_id)


@supervisor_router.get("/layouts/{layout_id}", response_model=SupervisorLayoutResponse)
def get_my_assigned_layout_detail(
    layout_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Retrieve detailed layout information for an assigned layout.
    Enforces 403 Forbidden if layout is not assigned to this supervisor.
    """
    return supervisor_service.get_supervisor_layout_detail(
        db=db, layout_id=layout_id, supervisor_id=current_user.id
    )


@supervisor_router.get("/submissions", response_model=HouseholdSubmissionListResponse)
def list_submissions(
    hlb_id: UUID | None = Query(default=None),
    review_state: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    List household submissions across assigned layouts.
    Filtered by optional hlb_id and review_state.
    """
    return supervisor_service.list_submissions(
        db=db,
        supervisor_id=current_user.id,
        hlb_id=hlb_id,
        review_state=review_state,
    )


@supervisor_router.post(
    "/submissions/{household_id}/verify", response_model=HouseholdSubmissionResponse
)
def verify_submission(
    household_id: UUID,
    body: HouseholdVerificationRequest = HouseholdVerificationRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Supervisor verifies an enumerator's household submission.
    """
    return supervisor_service.verify_submission(
        db=db,
        supervisor_id=current_user.id,
        household_id=household_id,
        comment=body.comment,
    )


@supervisor_router.post(
    "/submissions/{household_id}/return", response_model=HouseholdSubmissionResponse
)
def return_submission(
    household_id: UUID,
    body: HouseholdReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Supervisor returns a household submission for enumerator correction.
    """
    return supervisor_service.return_submission(
        db=db,
        supervisor_id=current_user.id,
        household_id=household_id,
        rejection_reason=body.rejection_reason,
        supervisor_comment=body.supervisor_comment,
    )


@supervisor_router.get("/building-edits", response_model=BuildingEditListResponse)
def list_building_edits(
    hlb_id: UUID | None = Query(default=None),
    review_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    List building edits pending or reviewed for the supervisor's assigned layouts.
    """
    return supervisor_service.list_building_edits(
        db=db,
        supervisor_id=current_user.id,
        hlb_id=hlb_id,
        review_status=review_status,
    )


@supervisor_router.post(
    "/building-edits/{edit_id}/review", response_model=BuildingEditResponse
)
def review_building_edit(
    edit_id: UUID,
    body: BuildingEditReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Supervisor approves or rejects a proposed building edit.
    If approved, mutates the underlying building accordingly.
    """
    return supervisor_service.review_building_edit(
        db=db,
        supervisor_id=current_user.id,
        edit_id=edit_id,
        new_status=body.status,
        comment=body.comment,
    )


@supervisor_router.post("/change-requests", response_model=ChangeRequestResponse)
def create_change_request(
    body: ChangeRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Supervisor requests administrative adjustments (e.g. split HLB, merge HLB,
    boundary correction, extra enumerator, or reassignment).
    """
    return supervisor_service.create_change_request(
        db=db,
        supervisor_id=current_user.id,
        request_type=body.request_type,
        description=body.description,
        hlb_id=body.hlb_id,
        layout_id=body.layout_id,
        priority=body.priority,
        metadata_json=body.metadata_json,
    )


@supervisor_router.get("/change-requests", response_model=ChangeRequestListResponse)
def list_change_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    List all change requests submitted by this supervisor.
    """
    return supervisor_service.list_change_requests(db=db, supervisor_id=current_user.id)


@supervisor_router.post(
    "/submissions/{household_id}/accept",
    response_model=HouseholdSubmissionResponse,
    summary="Accept verified household submission for final enumeration",
)
def accept_household_submission(
    household_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Requirement D1: Submission states transition to ACCEPTED.
    """
    return supervisor_service.accept_submission(
        db=db, actor_id=current_user.id, household_id=household_id
    )


@supervisor_router.get(
    "/quarantined-operations",
    summary="List operations quarantined due to post-unassignment timestamps",
)
def list_quarantined_operations(
    hlb_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Requirement B3: Supervisor workflow to review quarantined offline operations.
    """
    return supervisor_service.list_quarantined_operations(
        db=db, supervisor_id=current_user.id, hlb_id=hlb_id
    )


@supervisor_router.post(
    "/quarantined-operations/{operation_id}/review",
    summary="Supervisor accepts or rejects a quarantined offline operation",
)
def review_quarantined_operation(
    operation_id: UUID,
    body: QuarantinedOperationReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Requirement B3: Accept or reject quarantined operation with decision reason.
    """
    return supervisor_service.review_quarantined_operation(
        db=db,
        supervisor_id=current_user.id,
        operation_id=operation_id,
        approved=body.approved,
        reason=body.reason,
    )


@supervisor_router.post(
    "/corrections",
    response_model=SupervisorCorrectionResponse,
    summary="Apply non-destructive versioned supervisor correction to fieldwork record",
)
def create_fieldwork_correction(
    body: SupervisorCorrectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Requirement B4: Versioned supervisor corrections preserving enumerator provenance.
    """
    return supervisor_service.create_fieldwork_correction(
        db=db,
        supervisor_id=current_user.id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        corrected_data=body.corrected_data,
        reason=body.reason,
    )


@supervisor_router.get(
    "/change-requests/{request_id}/messages",
    response_model=ChangeRequestMessageListResponse,
    summary="Retrieve message thread for a change request",
)
def list_supervisor_change_request_messages(
    request_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Requirement D5: Supervisor access to change request message threads.
    """
    from app.services.deputy_service import deputy_service
    messages = deputy_service.list_request_messages(db=db, request_id=request_id)
    return {"items": messages, "total": len(messages)}


@supervisor_router.post(
    "/change-requests/{request_id}/messages",
    response_model=ChangeRequestMessageResponse,
    summary="Post message to change request discussion thread",
)
def post_supervisor_change_request_message(
    request_id: UUID,
    body: ChangeRequestMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Requirement D5: Post supervisor message to thread.
    """
    from app.services.deputy_service import deputy_service
    return deputy_service.add_request_message(
        db=db,
        request_id=request_id,
        author_id=current_user.id,
        author_role=str(current_user.role),
        message=body.message,
        attachments=body.attachments,
    )


@supervisor_router.get(
    "/enumerator-locations",
    response_model=SupervisorEnumeratorMonitoringResponse,
    summary="Real-time monitoring of enumerator locations and boundary statuses",
)
def get_supervisor_enumerator_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Supervisor live monitoring view: displays latest reported location,
    INSIDE/OUTSIDE boundary status, staleness indicator, road coverage %,
    and unvisited road segment count for all assigned enumerators.
    """
    from app.services.gps_service import gps_service
    return gps_service.get_supervisor_enumerator_locations(
        db=db, supervisor_id=current_user.id
    )

