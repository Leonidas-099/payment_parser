from dataclasses import dataclass

from app.policies.retry import RetryAction, decide

PAYMENTS_EXCHANGE = "payments.events"
RETRY_EXCHANGE = "payments.retry"
DEAD_LETTER_EXCHANGE = "payments.dlx"
NEW_ROUTING_KEY = "payments.new"
DEAD_LETTER_ROUTING_KEY = "payments.dlq"
RETRY_COUNT_HEADER = "x-retry-count"


@dataclass(frozen=True)
class PublicationTarget:
    exchange: str
    routing_key: str
    headers: dict[str, str]


def new_payment_target() -> PublicationTarget:
    return PublicationTarget(PAYMENTS_EXCHANGE, NEW_ROUTING_KEY, {})


def retry_routing_key(attempt: int) -> str:
    return f"payments.retry.{attempt}"


def failure_target(attempt: int) -> PublicationTarget:
    decision = decide(attempt)
    headers = {RETRY_COUNT_HEADER: str(decision.attempt)}
    if decision.action is RetryAction.DEAD:
        return PublicationTarget(DEAD_LETTER_EXCHANGE, DEAD_LETTER_ROUTING_KEY, headers)
    return PublicationTarget(RETRY_EXCHANGE, retry_routing_key(decision.attempt), headers)
