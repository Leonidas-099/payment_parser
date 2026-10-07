import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import SessionFactory
from app.messaging.broker import create_broker
from app.messaging.publisher import RabbitEventPublisher
from app.messaging.topology import declare_topology
from app.services.outbox import OutboxRelay


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    broker = create_broker(settings.rabbitmq_url)
    await broker.start()
    stop = asyncio.Event()
    relay_task: asyncio.Task[None] | None = None
    try:
        await declare_topology(broker)
        relay = OutboxRelay(SessionFactory, RabbitEventPublisher(broker), settings)
        relay_task = asyncio.create_task(relay.run(stop))
        yield
    finally:
        stop.set()
        if relay_task is not None:
            await relay_task
        await broker.stop()


def create_app(lifespan_handler=lifespan) -> FastAPI:
    configure_logging()
    application = FastAPI(title="Payment processing", version="1.0.0", lifespan=lifespan_handler)
    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
