import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.exceptions import IdempotencyConflict, PaymentNotFound
from app.models.enums import PaymentStatus
from app.models.outbox import OutboxEvent
from app.models.payment import Payment
from app.policies.idempotency import IdempotencyDecision, decide, payment_fingerprint
from app.policies.money import normalize_amount
from app.repositories.outbox import OutboxRepository
from app.repositories.payment import PaymentRepository
from app.schemas.events import PAYMENT_CREATED, PaymentCreated
from app.schemas.payment import PaymentCreate


class PaymentService:
    def __init__(
        self,
        session: AsyncSession,
        payments: PaymentRepository,
        outbox: OutboxRepository,
    ) -> None:
        self._session = session
        self._payments = payments
        self._outbox = outbox

    async def create(self, body: PaymentCreate, idempotency_key: str) -> Payment:
        request_hash = self._fingerprint(body)
        existing = await self._payments.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            decision = decide(existing.request_hash, request_hash)
            if decision is IdempotencyDecision.REPLAY:
                return existing
            raise IdempotencyConflict(idempotency_key)

        payment = self._new_payment(body, idempotency_key, request_hash)
        self._payments.add(payment)
        self._outbox.add(self._new_event(payment))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raced = await self._payments.get_by_idempotency_key(idempotency_key)
            if raced is None:
                raise exc
            if decide(raced.request_hash, request_hash) is IdempotencyDecision.CONFLICT:
                raise IdempotencyConflict(idempotency_key) from exc
            return raced
        return payment

    async def get(self, payment_id: uuid.UUID) -> Payment:
        payment = await self._payments.get(payment_id)
        if payment is None:
            raise PaymentNotFound(payment_id)
        return payment

    def _new_payment(self, body: PaymentCreate, idempotency_key: str, request_hash: str) -> Payment:
        return Payment(
            id=uuid.uuid4(),
            amount=normalize_amount(body.amount),
            currency=body.currency,
            description=body.description,
            details=body.metadata,
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            webhook_url=str(body.webhook_url),
            created_at=utcnow(),
        )

    def _new_event(self, payment: Payment) -> OutboxEvent:
        return OutboxEvent(
            aggregate_id=payment.id,
            event_type=PAYMENT_CREATED,
            payload=PaymentCreated(payment_id=payment.id).model_dump(mode="json"),
            created_at=payment.created_at,
        )

    @staticmethod
    def _fingerprint(body: PaymentCreate) -> str:
        return payment_fingerprint(
            amount=body.amount,
            currency=body.currency,
            description=body.description,
            metadata=body.metadata,
            webhook_url=str(body.webhook_url),
        )
