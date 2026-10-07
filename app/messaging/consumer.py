import asyncio
import logging

import httpx
from faststream import AckPolicy, FastStream
from faststream.rabbit import Channel, RabbitMessage

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionFactory
from app.integrations.gateway import EmulatedGateway
from app.integrations.webhook import HttpxWebhookSender
from app.messaging.broker import create_broker
from app.messaging.publisher import RabbitEventPublisher
from app.messaging.topology import (
    dead_letter_exchange,
    dead_letter_queue,
    declare_topology,
    payments_exchange,
    payments_new_queue,
)
from app.policies.retry import next_attempt, reported_attempt, should_process
from app.repositories.dead_letter import DeadLetterRepository
from app.repositories.payment import PaymentRepository
from app.schemas.events import PaymentCreated
from app.services.ops import DeadLetterService
from app.services.processing import ProcessingService

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()
broker = create_broker(settings.rabbitmq_url)
publisher = RabbitEventPublisher(broker)
gateway = EmulatedGateway(
    min_delay_seconds=settings.gateway_min_delay_seconds,
    max_delay_seconds=settings.gateway_max_delay_seconds,
    success_rate=settings.gateway_success_rate,
)
webhooks = HttpxWebhookSender(
    httpx.AsyncClient(
        timeout=httpx.Timeout(
            settings.webhook_timeout_seconds,
            connect=settings.webhook_connect_timeout_seconds,
        )
    )
)
app = FastStream(broker)


@app.on_startup
async def prepare_topology() -> None:
    await broker.connect()
    await declare_topology(broker)


@app.after_shutdown
async def close_webhook_client() -> None:
    await webhooks.aclose()


@broker.subscriber(
    payments_new_queue,
    payments_exchange,
    channel=Channel(prefetch_count=1, publisher_confirms=True, on_return_raises=True),
    ack_policy=AckPolicy.MANUAL,
)
async def handle_payment_created(event: PaymentCreated, message: RabbitMessage) -> None:
    attempt = await _reserve_attempt(event.payment_id, message)
    if attempt is None:
        await message.ack()
        return
    if not should_process(attempt):
        logger.warning("payment %s exceeded %s attempts after redelivery", event.payment_id, attempt)
        await _park(event, message, attempt)
        return
    try:
        async with SessionFactory() as session:
            service = ProcessingService(session, PaymentRepository(session), gateway, webhooks)
            await service.handle(event.payment_id)
    except Exception:
        logger.exception("payment %s failed on attempt %s", event.payment_id, attempt)
        await _park(event, message, attempt)
        return
    await message.ack()


async def _reserve_attempt(payment_id, message: RabbitMessage) -> int | None:
    """Commit the attempt before the slow gateway and webhook calls.

    A killed process leaves this number in the database, so the redelivery counts it.
    None means the webhook was already sent and the message can be acknowledged.
    """
    async with SessionFactory() as session:
        repository = PaymentRepository(session)
        payment = await repository.get(payment_id)
        if payment is not None and payment.webhook_sent_at is not None:
            return None
        if payment is None:
            return next_attempt(message.headers)
        attempt = await repository.increment_processing_attempts(payment_id)
        await session.commit()
    if attempt is None:
        return next_attempt(message.headers)
    return attempt


async def _park(event: PaymentCreated, message: RabbitMessage, attempt: int) -> None:
    try:
        target = await publisher.publish_failure(event.model_dump(mode="json"), attempt)
    except Exception:
        logger.exception("payment %s could not be rerouted", event.payment_id)
        await asyncio.sleep(1)
        await message.nack(requeue=True)
        return
    logger.warning(
        "payment %s attempt %s routed to %s",
        event.payment_id,
        attempt,
        target.routing_key,
    )
    await message.ack()


@broker.subscriber(
    dead_letter_queue,
    dead_letter_exchange,
    channel=Channel(prefetch_count=1, publisher_confirms=True, on_return_raises=True),
    ack_policy=AckPolicy.MANUAL,
)
async def handle_dead_letter(event: PaymentCreated, message: RabbitMessage) -> None:
    attempt = reported_attempt(message.headers)
    payload = event.model_dump(mode="json")
    try:
        async with SessionFactory() as session:
            await DeadLetterService(DeadLetterRepository(session)).record(
                payment_id=event.payment_id,
                payload=payload,
                attempt=attempt,
            )
            await session.commit()
    except Exception:
        logger.exception("payment %s dead letter was not stored", event.payment_id)
        await message.nack(requeue=True)
        return
    logger.warning("payment %s stored from the DLQ after attempt %s", event.payment_id, attempt)
    await message.ack()
