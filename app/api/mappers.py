from app.models.dead_letter import DeadLetter
from app.models.enums import Currency, OutboxStatus, PaymentStatus
from app.models.outbox import OutboxEvent
from app.models.payment import Payment
from app.schemas.ops import DeadLetterRead, FailedOutboxRead, OutboxRetryRead
from app.schemas.payment import PaymentAccepted, PaymentRead


def to_accepted(payment: Payment) -> PaymentAccepted:
    return PaymentAccepted(
        payment_id=payment.id,
        status=PaymentStatus(payment.status),
        created_at=payment.created_at,
    )


def to_read(payment: Payment) -> PaymentRead:
    return PaymentRead(
        payment_id=payment.id,
        amount=payment.amount,
        currency=Currency(payment.currency),
        description=payment.description,
        metadata=payment.details,
        status=PaymentStatus(payment.status),
        idempotency_key=payment.idempotency_key,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
        webhook_sent_at=payment.webhook_sent_at,
    )


def to_failed_outbox(event: OutboxEvent) -> FailedOutboxRead:
    return FailedOutboxRead(
        id=event.id,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        payload=event.payload,
        status=OutboxStatus(event.status),
        attempts=event.attempts,
        last_error=event.last_error,
        created_at=event.created_at,
    )


def to_outbox_retry(event: OutboxEvent) -> OutboxRetryRead:
    return OutboxRetryRead(id=event.id, status=OutboxStatus(event.status))


def to_dead_letter(letter: DeadLetter) -> DeadLetterRead:
    return DeadLetterRead(
        id=letter.id,
        payment_id=letter.payment_id,
        attempt=letter.attempt,
        payload=letter.payload,
        created_at=letter.created_at,
    )
