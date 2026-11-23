from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User, UserStatus
from app.repositories.user_repository import user_repository


class InactiveUserException(Exception):
    """Exception raised when an authenticated user is inactive."""

    pass


class InvalidCredentialsException(Exception):
    """Exception raised when credentials are invalid."""

    pass


class AuthService:
    def authenticate(self, db: Session, username: str, password: str) -> User:
        """
        Authenticate a user by username and password.
        Raises InactiveUserException if the user is inactive.
        Raises InvalidCredentialsException if credentials are invalid.
        """
        user = user_repository.get_by_username(db, username=username)
        if not user:
            raise InvalidCredentialsException("Invalid username or password")

        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsException("Invalid username or password")

        if user.status != UserStatus.ACTIVE:
            raise InactiveUserException("User account is inactive")

        return user


auth_service = AuthService()
