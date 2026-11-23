from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole, UserStatus
from app.repositories.user_repository import user_repository

reusable_oauth2 = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    token_credentials: HTTPAuthorizationCredentials | None = Depends(reusable_oauth2),
) -> User:
    """
    Dependency to fetch the authenticated user based on the JWT bearer token.
    Raises HTTP 401 if missing, expired, or invalid.
    Raises HTTP 401 if the user is inactive.
    """
    if not token_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = token_credentials.credentials
    username = decode_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_repository.get_by_username(db, username=username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(required_role: UserRole):
    """
    Dependency to restrict access to a specific user role.
    Raises HTTP 403 if role does not match.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: operation not permitted for this role",
            )
        return current_user

    return dependency


def require_any_role(required_roles: list[UserRole]):
    """
    Dependency to restrict access to any of the specified user roles.
    Raises HTTP 403 if role is not in the list.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: operation not permitted for this role",
            )
        return current_user

    return dependency
