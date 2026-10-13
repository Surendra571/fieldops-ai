import asyncio
import logging
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.core.security import hash_password
from app.scripts.init_db import init_indexes

logger = logging.getLogger(__name__)

# Sample Metro Atlanta technician definitions
TECHNICIANS_DATA = [
    {
        "name": "Marcus Brody",
        "email": "marcus.brody@fieldops.ai",
        "phone": "+14045550101",
        "skills": ["HVAC_EPA_CERTIFIED", "HEAT_PUMP_REPAIR", "HIGH_VOLTAGE"],
        "home_base": {"type": "Point", "coordinates": [-84.3880, 33.7490]},
        "current_location": {"type": "Point", "coordinates": [-84.3850, 33.7550]},
        "rating": 4.9,
        "completed_jobs_count": 142,
    },
    {
        "name": "Samantha Cruz",
        "email": "samantha.cruz@fieldops.ai",
        "phone": "+14045550102",
        "skills": ["MASTER_PLUMBER", "WATER_HEATER_EXPERT", "DRAIN_SPECIALIST"],
        "home_base": {"type": "Point", "coordinates": [-84.3500, 33.7700]},
        "current_location": {"type": "Point", "coordinates": [-84.3550, 33.7650]},
        "rating": 4.95,
        "completed_jobs_count": 189,
    },
    {
        "name": "David Kim",
        "email": "david.kim@fieldops.ai",
        "phone": "+14045550103",
        "skills": ["LICENSED_ELECTRICIAN", "PANEL_UPGRADE", "EV_CHARGER_INSTALL"],
        "home_base": {"type": "Point", "coordinates": [-84.4200, 33.7900]},
        "current_location": {"type": "Point", "coordinates": [-84.4150, 33.7850]},
        "rating": 4.88,
        "completed_jobs_count": 97,
    },
    {
        "name": "Carlos Gomez",
        "email": "carlos.gomez@fieldops.ai",
        "phone": "+14045550104",
        "skills": ["APPLIANCE_MASTER", "REFRIGERATION", "WASHER_DRYER_REPAIR"],
        "home_base": {"type": "Point", "coordinates": [-84.3600, 33.7300]},
        "current_location": {"type": "Point", "coordinates": [-84.3620, 33.7350]},
        "rating": 4.82,
        "completed_jobs_count": 115,
    },
    {
        "name": "Rachel Adams",
        "email": "rachel.adams@fieldops.ai",
        "phone": "+14045550105",
        "skills": ["HVAC_EPA_CERTIFIED", "COMMERCIAL_HVAC", "CHILLER_REPAIR"],
        "home_base": {"type": "Point", "coordinates": [-84.3900, 33.8200]},
        "current_location": {"type": "Point", "coordinates": [-84.3850, 33.8150]},
        "rating": 4.97,
        "completed_jobs_count": 210,
    },
]

CUSTOMERS_DATA = [
    {
        "full_name": "Eleanor Vance",
        "phone": "+14045550201",
        "email": "eleanor.vance@example.com",
        "street": "1428 Elm Street",
        "city": "Atlanta",
        "state": "GA",
        "postal_code": "30309",
        "coordinates": [-84.3840, 33.7890],
        "access_instructions": "Gate code #4012, beware of golden retriever",
    },
    {
        "full_name": "Arthur Pendelton",
        "phone": "+14045550202",
        "email": "arthur.pendelton@example.com",
        "street": "742 Evergreen Terrace",
        "city": "Atlanta",
        "state": "GA",
        "postal_code": "30306",
        "coordinates": [-84.3500, 33.7800],
        "access_instructions": "Side door key is in lockbox code 1234",
    },
    {
        "full_name": "Beatrice Thorne",
        "phone": "+14045550203",
        "email": "beatrice.thorne@example.com",
        "street": "221B Baker Street NW",
        "city": "Atlanta",
        "state": "GA",
        "postal_code": "30318",
        "coordinates": [-84.4100, 33.7750],
        "access_instructions": "Please call 10 minutes prior to arrival",
    },
    {
        "full_name": "Julian Sterling",
        "phone": "+14045550204",
        "email": "julian.sterling@example.com",
        "street": "100 Peachtree St NE",
        "city": "Atlanta",
        "state": "GA",
        "postal_code": "30303",
        "coordinates": [-84.3880, 33.7560],
        "access_instructions": "High-rise condo, check in with security concierge",
    },
]

WORK_ORDERS_SEED = [
    {
        "category": "HVAC",
        "priority": "HIGH",
        "description": "Central AC compressor failing to ignite; fan spinning but blowing warm air.",
        "symptoms": ["WARM_AIR", "COMPRESSOR_SILENT", "HUMMING_NOISE"],
        "required_skills": ["HVAC_EPA_CERTIFIED"],
        "estimated_duration_minutes": 90,
    },
    {
        "category": "PLUMBING",
        "priority": "EMERGENCY",
        "description": "Main water shutoff valve leaking rapidly under bathroom subfloor.",
        "symptoms": ["LEAK_ACTIVE", "WATER_PRESSURE_DROP"],
        "required_skills": ["MASTER_PLUMBER"],
        "estimated_duration_minutes": 120,
    },
    {
        "category": "ELECTRICAL",
        "priority": "MEDIUM",
        "description": "Master bedroom breaker continually tripping when space heater is engaged.",
        "symptoms": ["BREAKER_TRIP", "OVERLOAD"],
        "required_skills": ["LICENSED_ELECTRICIAN"],
        "estimated_duration_minutes": 60,
    },
]


async def seed_database(db: AsyncIOMotorDatabase) -> None:
    logger.info("Initializing database indexes...")
    await init_indexes(db)

    now = datetime.now(UTC)

    # 1. Seed Administrator and Dispatcher Users
    logger.info("Seeding administrative users...")
    admin_user = {
        "email": settings.SEED_ADMIN_EMAIL,
        "full_name": "System Administrator",
        "hashed_password": hash_password(settings.SEED_ADMIN_PASSWORD),
        "role": "ADMIN",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db["users"].update_one({"email": admin_user["email"]}, {"$set": admin_user}, upsert=True)

    dispatcher_user = {
        "email": "dispatcher@fieldops.ai",
        "full_name": "Chief Dispatcher Sarah",
        "hashed_password": hash_password("DispatcherSecure123!"),
        "role": "DISPATCHER",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db["users"].update_one(
        {"email": dispatcher_user["email"]}, {"$set": dispatcher_user}, upsert=True
    )

    # 2. Seed Technicians
    logger.info("Seeding technicians...")
    created_tech_ids = []
    for tech in TECHNICIANS_DATA:
        # Create tech user account
        tech_user = {
            "email": tech["email"],
            "full_name": tech["name"],
            "hashed_password": hash_password("TechnicianPass123!"),
            "role": "TECHNICIAN",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        user_res = await db["users"].find_one_and_update(
            {"email": tech["email"]},
            {"$set": tech_user},
            upsert=True,
            return_document=True,
        )

        tech_doc = {
            "user_id": str(user_res["_id"]),
            "name": tech["name"],
            "phone": tech["phone"],
            "email": tech["email"],
            "status": "ACTIVE",
            "skills": tech["skills"],
            "home_base": tech["home_base"],
            "current_location": tech["current_location"],
            "max_travel_radius_km": 40.0,
            "rating": tech["rating"],
            "completed_jobs_count": tech["completed_jobs_count"],
            "created_at": now,
            "updated_at": now,
        }
        res = await db["technicians"].find_one_and_update(
            {"email": tech["email"]},
            {"$set": tech_doc},
            upsert=True,
            return_document=True,
        )
        created_tech_ids.append(str(res["_id"]))

    # 3. Seed Customers
    logger.info("Seeding customers...")
    created_customer_ids = []
    for cust in CUSTOMERS_DATA:
        cust_doc = {
            "full_name": cust["full_name"],
            "phone": cust["phone"],
            "email": cust["email"],
            "preferred_channel": "VOICE",
            "service_addresses": [
                {
                    "street": cust["street"],
                    "city": cust["city"],
                    "state": cust["state"],
                    "postal_code": cust["postal_code"],
                    "location": {"type": "Point", "coordinates": cust["coordinates"]},
                    "access_instructions": cust["access_instructions"],
                    "is_primary": True,
                }
            ],
            "total_completed_jobs": 2,
            "no_show_history_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        res = await db["customers"].find_one_and_update(
            {"phone": cust["phone"]},
            {"$set": cust_doc},
            upsert=True,
            return_document=True,
        )
        created_customer_ids.append(str(res["_id"]))

    # 4. Seed Initial Work Orders and Appointments
    logger.info("Seeding initial work orders and appointments...")
    for idx, wo_seed in enumerate(WORK_ORDERS_SEED):
        cust_id = created_customer_ids[idx % len(created_customer_ids)]
        tech_id = created_tech_ids[idx % len(created_tech_ids)]
        wo_number = f"WO-2026-100{idx + 1}"

        cust = await db["customers"].find_one({"_id": ObjectId(cust_id)})
        service_addr = (
            cust["service_addresses"][0]
            if cust
            else {
                "street": "1428 Elm Street",
                "city": "Atlanta",
                "state": "GA",
                "postal_code": "30309",
            }
        )

        wo_doc = {
            "work_order_number": wo_number,
            "customer_id": cust_id,
            "source": "VOICE",
            "category": wo_seed["category"],
            "priority": wo_seed["priority"],
            "status": "SCHEDULED",
            "description": wo_seed["description"],
            "symptoms": wo_seed["symptoms"],
            "required_skills": wo_seed["required_skills"],
            "service_address": service_addr,
            "estimated_duration_minutes": wo_seed["estimated_duration_minutes"],
            "predicted_by_ml": False,
            "assigned_technician_id": tech_id,
            "audit_trail": [
                {
                    "transition_id": f"tr_{idx}_1",
                    "from_status": "DRAFT",
                    "to_status": "SUBMITTED",
                    "actor": "AI_AGENT",
                    "timestamp": now - timedelta(hours=2),
                    "reason": "Voice intake dialogue completed",
                },
                {
                    "transition_id": f"tr_{idx}_2",
                    "from_status": "SUBMITTED",
                    "to_status": "SCHEDULED",
                    "actor": "DISPATCHER",
                    "timestamp": now - timedelta(hours=1),
                    "reason": "Technician matched and confirmed",
                },
            ],
            "created_at": now - timedelta(hours=2),
            "updated_at": now - timedelta(hours=1),
        }
        wo_res = await db["work_orders"].find_one_and_update(
            {"work_order_number": wo_number},
            {"$set": wo_doc},
            upsert=True,
            return_document=True,
        )

        # Create scheduled appointment
        appt_start = now + timedelta(days=1, hours=idx * 2)
        appt_end = appt_start + timedelta(minutes=wo_seed["estimated_duration_minutes"])
        appt_number = f"APT-2026-500{idx + 1}"

        appt_doc = {
            "appointment_number": appt_number,
            "work_order_id": str(wo_res["_id"]),
            "technician_id": tech_id,
            "customer_id": cust_id,
            "scheduled_start": appt_start,
            "scheduled_end": appt_end,
            "status": "CONFIRMED",
            "lock_version": 1,
            "created_at": now - timedelta(hours=1),
            "updated_at": now - timedelta(hours=1),
        }
        await db["appointments"].find_one_and_update(
            {"appointment_number": appt_number},
            {"$set": appt_doc},
            upsert=True,
        )

    logger.info("Database seeding completed successfully!")


async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]
    await seed_database(db)
    client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
