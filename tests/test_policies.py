from decimal import Decimal

from app.policies.idempotency import IdempotencyDecision, decide, payment_fingerprint
from app.policies.retry import MAX_ATTEMPTS, RetryAction, next_attempt, reported_attempt, should_process
from app.policies.retry import decide as decide_retry
from app.policies.routing import failure_target


def test_amount_normalization_does_not_change_fingerprint() -> None:
    first = _fingerprint(amount=Decimal("10.1"), metadata={"b": 1, "a": {"d": 1, "c": 2}})
    second = _fingerprint(amount=Decimal("10.10"), metadata={"a": {"c": 2, "d": 1}, "b": 1})
    assert first == second


def test_different_payload_changes_fingerprint() -> None:
    assert _fingerprint(amount=Decimal("10.00")) != _fingerprint(amount=Decimal("11.00"))


def test_idempotency_decision() -> None:
    assert decide(None, "hash") is IdempotencyDecision.CREATE
    assert decide("hash", "hash") is IdempotencyDecision.REPLAY
    assert decide("old", "new") is IdempotencyDecision.CONFLICT


def test_broker_retry_stops_after_three_attempts() -> None:
    first = decide_retry(1)
    second = decide_retry(2)
    third = decide_retry(3)

    assert MAX_ATTEMPTS == 3
    assert first.action is RetryAction.RETRY and first.delay_seconds == 2
    assert second.action is RetryAction.RETRY and second.delay_seconds == 4
    assert third.action is RetryAction.DEAD and third.delay_seconds is None
    assert should_process(1) and should_process(3)
    assert not should_process(4)


def test_failure_is_routed_from_the_attempt_header() -> None:
    assert next_attempt({}) == 1
    assert next_attempt({"x-retry-count": "1"}) == 2
    assert next_attempt({"x-retry-count": b"2"}) == 3

    assert failure_target(1).routing_key == "payments.retry.1"
    assert failure_target(1).headers == {"x-retry-count": "1"}
    assert failure_target(3).exchange == "payments.dlx"
    assert failure_target(3).routing_key == "payments.dlq"
    assert reported_attempt({"x-retry-count": "3"}) == 3


def _fingerprint(*, amount: Decimal, metadata: dict | None = None) -> str:
    return payment_fingerprint(
        amount=amount,
        currency="RUB",
        description="order",
        metadata={} if metadata is None else metadata,
        webhook_url="https://example.com/hook",
    )
