import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.core.exceptions import WebhookDeliveryError
from app.integrations.webhook import HttpxWebhookSender
from app.schemas.webhook import WebhookNotification


def test_webhook_retries_then_succeeds() -> None:
    pauses = asyncio.run(_send(failures_before_success=2))
    assert pauses == [1, 2]


def test_webhook_gives_up_after_the_backoff_schedule() -> None:
    with pytest.raises(WebhookDeliveryError) as error:
        asyncio.run(_send(failures_before_success=None))
    assert error.value.attempts == 4
    assert error.value.reason == "HTTP 503"


async def _send(failures_before_success: int | None) -> list[float]:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failures_before_success is None or calls <= failures_before_success:
            return httpx.Response(503)
        return httpx.Response(204)

    pauses: list[float] = []

    async def sleep(seconds: float) -> None:
        pauses.append(seconds)

    sender = HttpxWebhookSender(httpx.AsyncClient(transport=httpx.MockTransport(handler)), sleep=sleep)
    notification = WebhookNotification(
        url="https://example.com/hook",
        payment_id=uuid4(),
        status="succeeded",
        amount="10.00",
        currency="RUB",
        processed_at=datetime(2026, 10, 7, tzinfo=UTC),
    )
    try:
        await sender.send(notification)
    finally:
        await sender.aclose()
    return pauses
