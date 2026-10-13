from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import mongomock
import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core.config import settings
from app.core.database import get_database
from app.core.security import create_access_token, hash_password
from app.main import app
from app.scripts.init_db import init_indexes

# Ensure mongomock uses MongoDB 7.0 compatibility across all platforms
mongomock.SERVER_VERSION = "7.0.0"

# Disable rate limiting for unit and integration test suites
settings.RATE_LIMIT_ENABLED = False


@pytest.fixture
def mock_mongo_client():
    client = AsyncMongoMockClient()
    return client


@pytest.fixture
async def test_db(mock_mongo_client):
    db = mock_mongo_client["fieldops_test"]
    await init_indexes(db)
    yield db
    # Clean up collections between tests
    collections = await db.list_collection_names()
    for col in collections:
        await db[col].drop()


@pytest.fixture
async def async_client(test_db) -> AsyncGenerator[AsyncClient, None]:
    # Override get_database dependency with test_db
    app.dependency_overrides[get_database] = lambda: test_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def admin_user(test_db):
    now = datetime.now(UTC)
    user_doc = {
        "email": "admin@test.com",
        "full_name": "Test Admin",
        "hashed_password": hash_password("AdminPass123!"),
        "role": "ADMIN",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    res = await test_db["users"].insert_one(user_doc)
    user_doc["id"] = str(res.inserted_id)
    return user_doc


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(subject=admin_user["id"], role=admin_user["role"])


@pytest.fixture
async def dispatcher_user(test_db):
    now = datetime.now(UTC)
    user_doc = {
        "email": "dispatcher@test.com",
        "full_name": "Test Dispatcher",
        "hashed_password": hash_password("DispatcherPass123!"),
        "role": "DISPATCHER",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    res = await test_db["users"].insert_one(user_doc)
    user_doc["id"] = str(res.inserted_id)
    return user_doc


@pytest.fixture
def dispatcher_token(dispatcher_user):
    return create_access_token(subject=dispatcher_user["id"], role=dispatcher_user["role"])


@pytest.fixture
async def customer_user(test_db):
    now = datetime.now(UTC)
    user_doc = {
        "email": "customer@test.com",
        "full_name": "Test Customer",
        "hashed_password": hash_password("CustomerPass123!"),
        "role": "CUSTOMER",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    res = await test_db["users"].insert_one(user_doc)
    user_doc["id"] = str(res.inserted_id)
    return user_doc


@pytest.fixture
def customer_token(customer_user):
    return create_access_token(subject=customer_user["id"], role=customer_user["role"])


@pytest.fixture
async def sample_customer(test_db):
    now = datetime.now(UTC)
    cust_doc = {
        "full_name": "Eleanor Vance",
        "phone": "+14045550183",
        "email": "eleanor@test.com",
        "preferred_channel": "VOICE",
        "service_addresses": [
            {
                "street": "1428 Elm Street",
                "city": "Atlanta",
                "state": "GA",
                "postal_code": "30309",
                "is_primary": True,
            }
        ],
        "total_completed_jobs": 0,
        "no_show_history_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    res = await test_db["customers"].insert_one(cust_doc)
    cust_doc["id"] = str(res.inserted_id)
    return cust_doc


@pytest.fixture
async def sample_technician(test_db):
    now = datetime.now(UTC)
    tech_doc = {
        "name": "Marcus Brody",
        "email": "marcus@test.com",
        "phone": "+14045550199",
        "status": "ACTIVE",
        "skills": ["HVAC_EPA_CERTIFIED"],
        "max_travel_radius_km": 40.0,
        "rating": 5.0,
        "completed_jobs_count": 0,
        "home_base": {"type": "Point", "coordinates": [-84.3880, 33.7490]},
        "current_location": {"type": "Point", "coordinates": [-84.3850, 33.7550]},
        "shift_schedule": {
            "timezone": "America/New_York",
            "weekly_hours": [
                {"day_of_week": "MONDAY", "start_time": "08:00", "end_time": "17:00"},
                {"day_of_week": "TUESDAY", "start_time": "08:00", "end_time": "17:00"},
                {"day_of_week": "WEDNESDAY", "start_time": "08:00", "end_time": "17:00"},
                {"day_of_week": "THURSDAY", "start_time": "08:00", "end_time": "17:00"},
                {"day_of_week": "FRIDAY", "start_time": "08:00", "end_time": "17:00"},
                {"day_of_week": "SATURDAY", "start_time": "08:00", "end_time": "17:00"},
                {"day_of_week": "SUNDAY", "start_time": "08:00", "end_time": "17:00"},
            ],
        },
        "created_at": now,
        "updated_at": now,
    }
    res = await test_db["technicians"].insert_one(tech_doc)
    tech_doc["id"] = str(res.inserted_id)
    return tech_doc
