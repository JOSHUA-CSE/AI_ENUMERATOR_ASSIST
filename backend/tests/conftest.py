import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.user import User, UserRole, UserStatus

# Use a file-based SQLite database for testing to share connection tables.
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_temp.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    """Create all database tables in a temp file database for testing."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    try:
        if os.path.exists("./test_temp.db"):
            os.remove("./test_temp.db")
    except Exception as e:
        print(f"Error removing temporary test database: {e}")


@pytest.fixture(name="db")
def db_fixture():
    """Fixture to yield a database session and clean up afterwards."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(name="client")
def client_fixture(db):
    """Fixture to yield a test client with get_db overridden."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def seed_test_users(db):
    """Seed base users before each test run to ensure a clean slate."""
    db.query(User).delete()
    db.commit()

    users = [
        User(
            name="Test Deputy",
            username="deputy",
            password_hash=get_password_hash("password123"),
            role=UserRole.DEPUTY_TAHSILDAR,
            status=UserStatus.ACTIVE,
        ),
        User(
            name="Test Supervisor",
            username="supervisor",
            password_hash=get_password_hash("password123"),
            role=UserRole.SUPERVISOR,
            status=UserStatus.ACTIVE,
        ),
        User(
            name="Test Enumerator",
            username="enumerator",
            password_hash=get_password_hash("password123"),
            role=UserRole.ENUMERATOR,
            status=UserStatus.ACTIVE,
        ),
        User(
            name="Test Inactive User",
            username="inactive",
            password_hash=get_password_hash("password123"),
            role=UserRole.ENUMERATOR,
            status=UserStatus.INACTIVE,
        ),
    ]

    for user in users:
        db.add(user)
    db.commit()


export_fixtures = [create_test_db, db_fixture, client_fixture, seed_test_users]
