from typing import Any, Protocol

from app.models.enums import PaymentStatus
from app.schemas.webhook import WebhookNotification


class PaymentGateway(Protocol):
    async def authorize(self) -> PaymentStatus:
        """Return the business outcome of a charge. A decline is a status, not an exception."""


class WebhookSender(Protocol):
    async def send(self, notification: WebhookNotification) -> None:
        """Deliver a notification or raise WebhookDeliveryError when every attempt fails."""


class EventPublisher(Protocol):
    async def publish_new(self, payload: dict[str, Any]) -> None:
        """Publish a payment.created event and wait for broker confirmation."""
