from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.policies.retry import RETRY_DELAYS_SECONDS
from app.policies.routing import (
    DEAD_LETTER_EXCHANGE,
    DEAD_LETTER_ROUTING_KEY,
    NEW_ROUTING_KEY,
    PAYMENTS_EXCHANGE,
    RETRY_EXCHANGE,
    retry_routing_key,
)

payments_exchange = RabbitExchange(PAYMENTS_EXCHANGE, type=ExchangeType.TOPIC, durable=True)
retry_exchange = RabbitExchange(RETRY_EXCHANGE, type=ExchangeType.DIRECT, durable=True)
dead_letter_exchange = RabbitExchange(DEAD_LETTER_EXCHANGE, type=ExchangeType.DIRECT, durable=True)

payments_new_queue = RabbitQueue(
    "payments.new",
    durable=True,
    routing_key=NEW_ROUTING_KEY,
    arguments={
        "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
        "x-dead-letter-routing-key": DEAD_LETTER_ROUTING_KEY,
    },
)

retry_queues = tuple(
    RabbitQueue(
        retry_routing_key(attempt),
        durable=True,
        routing_key=retry_routing_key(attempt),
        arguments={
            "x-message-ttl": delay_seconds * 1000,
            "x-dead-letter-exchange": PAYMENTS_EXCHANGE,
            "x-dead-letter-routing-key": NEW_ROUTING_KEY,
        },
    )
    for attempt, delay_seconds in enumerate(RETRY_DELAYS_SECONDS, start=1)
)

dead_letter_queue = RabbitQueue(
    "payments.dlq",
    durable=True,
    routing_key=DEAD_LETTER_ROUTING_KEY,
)

_BINDINGS = (
    (payments_new_queue, payments_exchange),
    *((queue, retry_exchange) for queue in retry_queues),
    (dead_letter_queue, dead_letter_exchange),
)


async def declare_topology(broker: RabbitBroker) -> None:
    for exchange in (payments_exchange, retry_exchange, dead_letter_exchange):
        await broker.declare_exchange(exchange)
    for queue, exchange in _BINDINGS:
        declared = await broker.declare_queue(queue)
        await declared.bind(exchange.name, routing_key=queue.routing_key)
