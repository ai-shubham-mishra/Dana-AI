import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import MemorySaver

from agent.runtime import build_default_agent
from api.routes import chats, health, jobs, me
from config.settings import Settings, get_settings
from integrations.mongo.client import create_mongo_client, ensure_indexes
from integrations.storage.blob import create_blob_service, ensure_container


def create_app(settings: Settings | None = None, agent_factory=None) -> FastAPI:
    settings = settings or get_settings()
    agent_factory = agent_factory or build_default_agent

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mongo = create_mongo_client(settings.mongo_uri)
        db = mongo[settings.mongo_db]
        await ensure_indexes(db)

        blob = create_blob_service(settings.blob_connection_string)
        await ensure_container(blob, settings.blob_container)

        app.state.settings = settings
        app.state.mongo = mongo
        app.state.db = db
        app.state.blob = blob
        app.state.checkpointer = MemorySaver()
        app.state.agent_factory = agent_factory
        app.state.agent = None
        app.state.agent_lock = asyncio.Lock()
        app.state.active_chats = set()
        try:
            yield
        finally:
            await blob.close()
            mongo.close()

    app = FastAPI(title="Dana AI API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(chats.router)
    app.include_router(jobs.router)
    return app


app = create_app()
