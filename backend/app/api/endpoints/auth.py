from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import (
    InactiveUserException,
    InvalidCredentialsException,
    auth_service,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return access token + user details.
    """
    try:
        user = auth_service.authenticate(
            db, username=login_data.username, password=login_data.password
        )
    except InvalidCredentialsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except InactiveUserException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    access_token = create_access_token(subject=user.username)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current logged in user details.
    """
    return current_user


@router.post("/logout")
def logout(_current_user: User = Depends(get_current_user)):
    """
    Stateless logout endpoint. Return confirmation.
    """
    return {"status": "ok", "message": "Successfully logged out"}


# --- RBAC Test Endpoints ---
# Renamed from test_xxx to rbac_test_xxx to prevent pytest warning PT028


@router.get("/test-deputy")
def rbac_test_deputy(
    current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Endpoint accessible only by Deputy Tahsildar.
    """
    return {
        "status": "ok",
        "message": f"Hello Deputy {current_user.name}",
    }


@router.get("/test-supervisor")
def rbac_test_supervisor(
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    """
    Endpoint accessible only by Supervisor.
    """
    return {
        "status": "ok",
        "message": f"Hello Supervisor {current_user.name}",
    }


@router.get("/test-enumerator")
def rbac_test_enumerator(
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    """
    Endpoint accessible only by Enumerator.
    """
    return {
        "status": "ok",
        "message": f"Hello Enumerator {current_user.name}",
    }
