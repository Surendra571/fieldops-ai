from httpx import AsyncClient


async def test_health_and_readiness_endpoints(async_client: AsyncClient):
    # Liveness probe
    health_resp = await async_client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    # Readiness probe
    ready_resp = await async_client.get("/api/v1/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"
    assert ready_resp.json()["database"] == "connected"


async def test_user_registration_and_authentication(async_client: AsyncClient):
    # 1. Register new user
    register_payload = {
        "email": "newuser@example.com",
        "full_name": "New User",
        "password": "Password123!",
        "role": "CUSTOMER",
    }
    reg_resp = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == "newuser@example.com"
    assert "password" not in user_data
    assert "hashed_password" not in user_data

    # 2. Duplicate registration conflict
    dup_resp = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "CONFLICT"

    # 3. Login with valid credentials
    login_payload = {
        "email": "newuser@example.com",
        "password": "Password123!",
    }
    login_resp = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    access_token = token_data["access_token"]

    # 4. Access /auth/me with Bearer token
    me_resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "newuser@example.com"

    # 5. Invalid credentials rejection
    bad_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "newuser@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "AUTHENTICATION_FAILED"
