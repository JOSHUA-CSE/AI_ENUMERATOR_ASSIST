from fastapi.testclient import TestClient


def test_login_success(client: TestClient):
    """1. Successful login returns access token and user info."""
    response = client.post(
        "/api/v1/auth/login", json={"username": "enumerator", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "enumerator"
    assert data["user"]["role"] == "ENUMERATOR"
    # Ensure password hashes are never returned
    assert "password_hash" not in data["user"]
    assert "password" not in data["user"]


def test_login_invalid_username(client: TestClient):
    """2. Login fails with invalid username."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "unknown_user", "password": "password123"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_invalid_password(client: TestClient):
    """3. Login fails with invalid password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "enumerator", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_inactive_user(client: TestClient):
    """4. Login fails when user is inactive."""
    response = client.post(
        "/api/v1/auth/login", json={"username": "inactive", "password": "password123"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "User account is inactive"


def test_me_missing_token(client: TestClient):
    """5. Accessing protected endpoint without token returns HTTP 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_invalid_token(client: TestClient):
    """6. Accessing protected endpoint with invalid token returns HTTP 401."""
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid_token_here"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_get_me_success(client: TestClient):
    """7. Accessing GET /api/auth/me with valid token returns user details."""
    # First, login to get token
    login_response = client.post(
        "/api/v1/auth/login", json={"username": "enumerator", "password": "password123"}
    )
    token = login_response.json()["access_token"]

    # Get profile
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "enumerator"
    assert data["role"] == "ENUMERATOR"
    assert "password_hash" not in data


def test_logout_success(client: TestClient):
    """8. Logout returns a successful status response."""
    # First, login
    login_response = client.post(
        "/api/v1/auth/login", json={"username": "enumerator", "password": "password123"}
    )
    token = login_response.json()["access_token"]

    # Call logout
    response = client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Successfully logged out"}


def test_deputy_authorization(client: TestClient):
    """9. Deputy Tahsildar can access deputy endpoint."""
    login_response = client.post(
        "/api/v1/auth/login", json={"username": "deputy", "password": "password123"}
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/test-deputy", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "Hello Deputy" in response.json()["message"]


def test_supervisor_authorization(client: TestClient):
    """10. Supervisor can access supervisor endpoint."""
    login_response = client.post(
        "/api/v1/auth/login", json={"username": "supervisor", "password": "password123"}
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/test-supervisor", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "Hello Supervisor" in response.json()["message"]


def test_enumerator_authorization(client: TestClient):
    """11. Enumerator can access enumerator endpoint."""
    login_response = client.post(
        "/api/v1/auth/login", json={"username": "enumerator", "password": "password123"}
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/test-enumerator", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "Hello Enumerator" in response.json()["message"]


def test_cross_role_access_denial(client: TestClient):
    """12. Access is denied (HTTP 403) when role is unauthorized."""
    # 12a. Enumerator trying to access Deputy endpoint -> 403
    login_response = client.post(
        "/api/v1/auth/login", json={"username": "enumerator", "password": "password123"}
    )
    enumerator_token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/test-deputy",
        headers={"Authorization": f"Bearer {enumerator_token}"},
    )
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]

    # 12b. Supervisor trying to access Deputy endpoint -> 403
    login_response = client.post(
        "/api/v1/auth/login", json={"username": "supervisor", "password": "password123"}
    )
    supervisor_token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/test-deputy",
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert response.status_code == 403

    # 12c. Enumerator trying to access Supervisor endpoint -> 403
    response = client.get(
        "/api/v1/auth/test-supervisor",
        headers={"Authorization": f"Bearer {enumerator_token}"},
    )
    assert response.status_code == 403
