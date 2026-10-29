from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

SERVER_SELECTION_TIMEOUT_MS = 5000


def create_mongo_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri, serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS)


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.memberships.create_index([("user_id", ASCENDING), ("org_id", ASCENDING)], unique=True)
    await db.chats.create_index([("org_id", ASCENDING), ("user_id", ASCENDING), ("updated_at", DESCENDING)])
    await db.jobs.create_index([("org_id", ASCENDING), ("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db.messages.create_index(
        [("org_id", ASCENDING), ("user_id", ASCENDING), ("chat_id", ASCENDING), ("created_at", ASCENDING)]
    )
