from typing import Any

from faststream.rabbit import RabbitBroker, RabbitExchange

from app.core.exceptions import PublicationError
from app.messaging.topology import dead_letter_exchange, payments_exchange, retry_exchange
from app.policies.routing import (
    DEAD_LETTER_EXCHANGE,
    PAYMENTS_EXCHANGE,
    RETRY_EXCHANGE,
    PublicationTarget,
    failure_target,
    new_payment_target,
)

_EXCHANGES: dict[str, RabbitExchange] = {
    PAYMENTS_EXCHANGE: payments_exchange,
    RETRY_EXCHANGE: retry_exchange,
    DEAD_LETTER_EXCHANGE: dead_letter_exchange,
}


class RabbitEventPublisher:
    def __init__(self, broker: RabbitBroker) -> None:
        self._broker = broker

    async def publish_new(self, payload: dict[str, Any]) -> None:
        await self._publish(new_payment_target(), payload)

    async def publish_failure(self, payload: dict[str, Any], attempt: int) -> PublicationTarget:
        target = failure_target(attempt)
        await self._publish(target, payload)
        return target

    async def _publish(self, target: PublicationTarget, payload: dict[str, Any]) -> None:
        confirmation = await self._broker.publish(
            payload,
            exchange=_EXCHANGES[target.exchange],
            routing_key=target.routing_key,
            headers=target.headers or None,
            persist=True,
            mandatory=True,
        )
        if confirmation is None:
            raise PublicationError(f"RabbitMQ did not confirm publication to {target.routing_key}")
