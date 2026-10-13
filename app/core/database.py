import logging
import re

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        """Initialize Async MongoDB client and connect."""
        await connect_to_mongo()

    async def disconnect(self) -> None:
        """Close Async MongoDB client connections gracefully."""
        await close_mongo_connection()

    def get_database(self) -> AsyncIOMotorDatabase:
        """Retrieve the active MongoDB database."""
        return get_database()

    @property
    def _client(self) -> AsyncIOMotorClient | None:
        return self.client


db_manager = DatabaseManager()


async def connect_to_mongo() -> None:
    """Initialize Async MongoDB client and connect."""
    sanitized_url = re.sub(r"://([^:]+):([^@]+)@", r"://\1:[REDACTED]@", settings.MONGODB_URL)
    logger.info("Connecting to MongoDB at %s...", sanitized_url)
    try:
        client_kwargs: dict = {
            "minPoolSize": settings.MONGODB_MIN_POOL_SIZE,
            "maxPoolSize": settings.MONGODB_MAX_POOL_SIZE,
            "serverSelectionTimeoutMS": settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            "socketTimeoutMS": 10000,
            "maxIdleTimeMS": 60000,
        }
        if "mongodb+srv://" in settings.MONGODB_URL or "tls=true" in settings.MONGODB_URL.lower():
            try:
                import certifi

                client_kwargs["tlsCAFile"] = certifi.where()
            except ImportError:
                pass

        db_manager.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            **client_kwargs,
        )
        # Verify connection with an admin ping
        await db_manager.client.admin.command("ping")
        db_manager.db = db_manager.client[settings.MONGODB_DB_NAME]
        logger.info("Successfully connected to MongoDB database '%s'.", settings.MONGODB_DB_NAME)
    except Exception as e:
        logger.error("Failed to connect to MongoDB: %s", str(e))
        raise


async def close_mongo_connection() -> None:
    """Close Async MongoDB client connections gracefully."""
    if db_manager.client:
        logger.info("Closing MongoDB connection pool...")
        db_manager.client.close()
        db_manager.client = None
        db_manager.db = None
        logger.info("MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency to retrieve the active MongoDB database."""
    if db_manager.db is None:
        raise RuntimeError("Database connection has not been initialized.")
    return db_manager.db
