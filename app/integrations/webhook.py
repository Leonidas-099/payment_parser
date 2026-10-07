import asyncio
from collections.abc import Awaitable, Callable

import httpx

from app.core.exceptions import WebhookDeliveryError
from app.policies.retry import WEBHOOK_RETRY_PAUSES_SECONDS
from app.schemas.webhook import WebhookNotification


class HttpxWebhookSender:
    def __init__(
        self,
        client: httpx.AsyncClient,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._sleep = sleep

    async def aclose(self) -> None:
        await self._client.aclose()

    async def send(self, notification: WebhookNotification) -> None:
        attempts = len(WEBHOOK_RETRY_PAUSES_SECONDS) + 1
        reason = "webhook delivery failed"
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                await self._sleep(WEBHOOK_RETRY_PAUSES_SECONDS[attempt - 2])
            try:
                response = await self._client.post(
                    notification.url,
                    json=notification.body(),
                    follow_redirects=False,
                )
            except httpx.HTTPError as exc:
                reason = str(exc)
            else:
                if response.is_success:
                    return
                reason = f"HTTP {response.status_code}"
        raise WebhookDeliveryError(notification.payment_id, attempts, reason)
