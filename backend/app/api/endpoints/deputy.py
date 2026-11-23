from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.change_request import ChangeRequestStatus
from app.models.user import User, UserRole
from app.schemas.change_request import (
    ChangeRequestListResponse,
    ChangeRequestMessageCreate,
    ChangeRequestMessageListResponse,
    ChangeRequestMessageResponse,
    ChangeRequestResolutionRequest,
    ChangeRequestResponse,
)
from app.schemas.deputy_progress import (
    DeputyLayoutDetailProgressResponse,
    DeputyOverallProgressResponse,
)
from app.services.deputy_service import deputy_service

# Router for /api/v1/deputy
deputy_router = APIRouter()


@deputy_router.get(
    "/progress",
    response_model=DeputyOverallProgressResponse,
    summary="Retrieve overall fieldwork progress across all layouts under jurisdiction",
)
def get_deputy_overall_progress(
    area_id: UUID | None = Query(
        default=None, description="Optional administrative area filter"
    ),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Level 1: Overall administrative progress across layouts in Deputy's jurisdiction.
    Authorized for DEPUTY_TAHSILDAR only.
    Returns aggregated metrics, active/completed HLBs, and per-layout progress cards.
    """
    return deputy_service.get_overall_progress(db=db, area_id=area_id)


@deputy_router.get(
    "/layouts/{layout_id}/progress",
    response_model=DeputyLayoutDetailProgressResponse,
    summary="Retrieve detailed fieldwork progress and HLB summaries for a layout",
)
def get_deputy_layout_progress(
    layout_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Level 2 & Level 3: Layout detail and HLB summary within the selected layout.
    Authorized for DEPUTY_TAHSILDAR only.
    Returns layout status, supervisor assignment, house completion, and HLB breakdown.
    """
    return deputy_service.get_layout_progress_detail(db=db, layout_id=layout_id)


@deputy_router.get("/change-requests", response_model=ChangeRequestListResponse)
def list_change_requests(
    status: ChangeRequestStatus | None = Query(default=None),
    area_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    List change requests submitted by Supervisors across Deputy's jurisdiction.
    """
    return deputy_service.list_change_requests(
        db=db, status_filter=status, area_id=area_id
    )


@deputy_router.post(
    "/change-requests/{request_id}/resolve", response_model=ChangeRequestResponse
)
def resolve_change_request(
    request_id: UUID,
    body: ChangeRequestResolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Deputy Tahsildar reviews and resolves (APPROVES / REJECTS) a supervisor change request.
    """
    return deputy_service.resolve_change_request(
        db=db,
        deputy_id=current_user.id,
        request_id=request_id,
        new_status=body.status,
        resolution_notes=body.resolution_notes,
    )


@deputy_router.get(
    "/accepted-totals",
    summary="Retrieve final accepted census figures strictly isolated from draft progress",
)
@deputy_router.get(
    "/accepted-census-totals",
    summary="Retrieve final accepted census figures strictly isolated from draft progress",
)
def get_accepted_census_totals(
    area_id: UUID | None = Query(default=None),
    layout_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Requirement D2: Data Visibility.
    Deputy dashboards read ONLY ACCEPTED data for final accepted census figures.
    Does not mix draft, submitted, returned or supervisor-verified records.
    """
    return deputy_service.get_accepted_census_totals(
        db=db, area_id=area_id, layout_id=layout_id
    )


@deputy_router.post(
    "/records/{record_id}/accept",
    summary="Deputy Tahsildar accepts a household record into the final census figures",
)
def accept_household_record(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Requirement D1 & D2: Final acceptance into authoritative census counts.
    """
    return deputy_service.accept_record(
        db=db, deputy_id=current_user.id, record_id=record_id
    )


@deputy_router.get(
    "/change-requests/{request_id}/messages",
    response_model=ChangeRequestMessageListResponse,
    summary="Retrieve discussion message thread for a change request",
)
def list_change_request_messages(
    request_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Requirement D5: Message threads for change requests and issues.
    """
    messages = deputy_service.list_request_messages(db=db, request_id=request_id)
    return {"items": messages, "total": len(messages)}


@deputy_router.post(
    "/change-requests/{request_id}/messages",
    response_model=ChangeRequestMessageResponse,
    summary="Post a message to a change request discussion thread",
)
def post_change_request_message(
    request_id: UUID,
    body: ChangeRequestMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Requirement D5: Post message to thread with author role and timestamp.
    """
    return deputy_service.add_request_message(
        db=db,
        request_id=request_id,
        author_id=current_user.id,
        author_role=str(current_user.role),
        message=body.message,
        attachments=body.attachments,
    )
