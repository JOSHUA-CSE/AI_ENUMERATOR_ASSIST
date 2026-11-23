from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_any_role, require_role
from app.models.user import User, UserRole
from app.schemas.enumerator_assignment import (
    EnumeratorAssignedHlbDetailResponse,
    EnumeratorHlbDownloadResponse,
    EnumeratorListResponse,
)
from app.services.enumerator_service import enumerator_service

# Router for /api/v1/enumerators
router = APIRouter()

# Router for /api/v1/enumerator
enumerator_router = APIRouter()


@router.get("", response_model=EnumeratorListResponse)
def list_enumerators(
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    List all enumerators and their real-time availability status.
    Accessible by Deputy Tahsildar and Supervisor.
    """
    return enumerator_service.list_enumerators(db=db)


@enumerator_router.get(
    "/hlbs",
    response_model=list[EnumeratorAssignedHlbDetailResponse],
)
def get_my_assigned_hlbs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    """
    Retrieve all HLBs actively assigned to the authenticated enumerator.
    Authorized for ENUMERATOR only.
    Derived strictly from authenticated JWT identity.
    """
    return enumerator_service.get_enumerator_assigned_hlbs(
        db=db, enumerator_id=current_user.id
    )


@enumerator_router.get(
    "/hlbs/{hlb_id}",
    response_model=EnumeratorAssignedHlbDetailResponse,
)
def get_my_assigned_hlb_detail(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    """
    Retrieve detailed information and boundary for an assigned HLB.
    Enforces 403 Forbidden if HLB is not assigned to this enumerator.
    """
    return enumerator_service.get_enumerator_assigned_hlb_detail(
        db=db, hlb_id=hlb_id, enumerator_id=current_user.id
    )


@enumerator_router.get(
    "/hlbs/{hlb_id}/download",
    response_model=EnumeratorHlbDownloadResponse,
)
def download_assigned_hlb(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    """
    Download complete HLB dataset (boundary, metadata, and all assigned buildings)
    for offline field operations.
    Enforces strict 403 Forbidden if HLB is not actively assigned to this enumerator.
    """
    return enumerator_service.get_enumerator_hlb_download(
        db=db, hlb_id=hlb_id, enumerator_id=current_user.id
    )
