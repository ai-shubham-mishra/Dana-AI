import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agent.runtime import build_default_agent
from api.routes import chats, connectors, health, jobs, me
from config.settings import Settings, get_settings
from integrations.auth.jwt_secret import load_jwt_secret
from integrations.checkpoint.mongo import create_mongo_checkpointer
from integrations.mongo.client import create_mongo_client, ensure_indexes
from integrations.postgres.client import create_readonly_pool
from integrations.storage.blob import create_blob_service, ensure_container
from integrations.training.service import CommandFactory, TrainingService

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    agent_factory=None,
    jwt_secret_loader: Callable[[Settings], str] | None = None,
    training_command_factory: CommandFactory | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    agent_factory = agent_factory or build_default_agent
    jwt_secret_loader = jwt_secret_loader or load_jwt_secret

    async def fetch_jwt_secret() -> str | None:
        try:
            return await asyncio.to_thread(jwt_secret_loader, settings)
        except Exception as exc:
            logger.warning("JWT secret unavailable from Key Vault (%s); auth will fail closed", type(exc).__name__)
            return None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mongo = create_mongo_client(settings.mongo_uri)
        db = mongo[settings.mongo_db]
        await ensure_indexes(db)

        blob = create_blob_service(settings.blob_connection_string)
        await ensure_container(blob, settings.blob_container)

        app.state.settings = settings
        app.state.jwt_secret = await fetch_jwt_secret()
        app.state.mongo = mongo
        app.state.db = db
        app.state.blob = blob
        app.state.checkpoint_client, app.state.checkpointer = await asyncio.to_thread(
            create_mongo_checkpointer, settings.mongo_uri, settings.mongo_db
        )
        app.state.agent_factory = agent_factory
        app.state.agent = None
        app.state.agent_lock = asyncio.Lock()
        app.state.active_chats = set()
        app.state.connector_pool = None
        if settings.database_url_test:
            app.state.connector_pool = create_readonly_pool(settings.database_url_test.get_secret_value())
            await app.state.connector_pool.open(wait=False)
        app.state.training = TrainingService(
            db=db, blob=blob, settings=settings, command_factory=training_command_factory
        )
        try:
            yield
        finally:
            await app.state.training.close()
            if app.state.connector_pool is not None:
                await app.state.connector_pool.close()
            await blob.close()
            app.state.checkpoint_client.close()
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
    app.include_router(connectors.router)
    return app


app = create_app()
