from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.sync import SyncBatchRequest, SyncBatchResponse
from app.services.sync_service import sync_service

router = APIRouter()


@router.post(
    "",
    response_model=SyncBatchResponse,
    summary="Synchronize batch fieldwork operations",
)
def sync_batch(
    request: SyncBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncBatchResponse:
    """
    Synchronizes offline fieldwork data (households, revisits, GPS logs)
    from an authenticated Primary Enumerator.

    Enforces:
    - JWT authentication & Enumerator role.
    - Strict per-operation idempotency via idempotency_key.
    - Server-side authorization verifying HLB assignment ownership.
    - Conflict awareness and version checking.
    """
    return sync_service.process_sync_batch(
        db=db,
        request=request,
        current_user=current_user,
    )
