from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

SERVER_SELECTION_TIMEOUT_MS = 5000
CHECKPOINT_COLLECTION = "agent_checkpoints"
WRITES_COLLECTION = "agent_checkpoint_writes"


def create_mongo_checkpointer(uri: str, db_name: str) -> tuple[MongoClient, MongoDBSaver]:
    client = MongoClient(uri, serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS)
    saver = MongoDBSaver(
        client,
        db_name=db_name,
        checkpoint_collection_name=CHECKPOINT_COLLECTION,
        writes_collection_name=WRITES_COLLECTION,
    )
    return client, saver
