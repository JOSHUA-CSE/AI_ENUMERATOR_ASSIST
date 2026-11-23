import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, String, Uuid

from app.core.database import Base


class UserRole(enum.StrEnum):
    DEPUTY_TAHSILDAR = "DEPUTY_TAHSILDAR"
    SUPERVISOR = "SUPERVISOR"
    ENUMERATOR = "ENUMERATOR"


class UserStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
