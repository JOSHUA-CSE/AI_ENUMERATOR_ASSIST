"""
DEVELOPMENT ONLY SEED SCRIPT
This script generates sample accounts for local development and testing purposes only.
DO NOT use this script in production environments.
"""

import logging

from app.core.database import SessionLocal
from app.models.user import UserRole, UserStatus
from app.repositories.user_repository import user_repository
from app.schemas.user import UserCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_users():
    """
    Seed local database with development users for the three roles:
    - DEPUTY_TAHSILDAR (username: deputy, password: password123)
    - SUPERVISOR       (username: supervisor, password: password123)
    - ENUMERATOR       (username: enumerator, password: password123)
    - INACTIVE         (username: inactive, password: password123) (for inactive checks)
    """
    db = SessionLocal()
    try:
        dev_users = [
            UserCreate(
                name="Dev Deputy Tahsildar",
                username="deputy",
                password="password123",
                role=UserRole.DEPUTY_TAHSILDAR,
                status=UserStatus.ACTIVE,
                phone="9999999991",
            ),
            UserCreate(
                name="Dev Supervisor",
                username="supervisor",
                password="password123",
                role=UserRole.SUPERVISOR,
                status=UserStatus.ACTIVE,
                phone="9999999992",
            ),
            UserCreate(
                name="Dev Enumerator",
                username="enumerator",
                password="password123",
                role=UserRole.ENUMERATOR,
                status=UserStatus.ACTIVE,
                phone="9999999993",
            ),
            UserCreate(
                name="Dev Inactive Enumerator",
                username="inactive",
                password="password123",
                role=UserRole.ENUMERATOR,
                status=UserStatus.INACTIVE,
                phone="9999999994",
            ),
        ]

        for dev_user in dev_users:
            existing = user_repository.get_by_username(db, dev_user.username)
            if existing:
                logger.info(f"User '{dev_user.username}' already exists. Skipping.")
                continue
            user_repository.create(db, dev_user)
            logger.info(
                f"Created dev user: {dev_user.username} ({dev_user.role.value})"
            )

        logger.info("Database seeding completed successfully.")
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
