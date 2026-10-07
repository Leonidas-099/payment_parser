import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import HttpUrl

from app.core.exceptions import IdempotencyConflict
from app.models.enums import PaymentStatus
from app.models.payment import Payment
from app.policies.idempotency import payment_fingerprint
from app.schemas.events import PAYMENT_CREATED
from app.schemas.payment import PaymentCreate
from app.services.payment import PaymentService


def test_create_writes_payment_and_outbox_together() -> None:
    asyncio.run(_create())


def test_same_key_and_body_returns_existing_payment() -> None:
    asyncio.run(_replay())


def test_same_key_and_different_body_conflicts() -> None:
    with pytest.raises(IdempotencyConflict):
        asyncio.run(_conflict())


async def _create() -> None:
    payments = _Payments()
    outbox = _Outbox()
    service = PaymentService(_Session(), payments, outbox)

    payment = await service.create(_body(Decimal("10.50")), "order-1")

    assert payment.status == PaymentStatus.PENDING
    assert payment.amount == Decimal("10.50")
    assert payments.added == [payment]
    assert outbox.added[0].aggregate_id == payment.id
    assert outbox.added[0].event_type == PAYMENT_CREATED
    assert outbox.added[0].payload["payment_id"] == str(payment.id)


async def _replay() -> None:
    body = _body(Decimal("10.00"))
    existing = _stored(body, "order-1")
    payments = _Payments(existing)
    outbox = _Outbox()
    service = PaymentService(_Session(), payments, outbox)

    found = await service.create(body, "order-1")

    assert found is existing
    assert payments.added == []
    assert outbox.added == []


async def _conflict() -> None:
    existing = _stored(_body(Decimal("10.00")), "order-1")
    service = PaymentService(_Session(), _Payments(existing), _Outbox())
    await service.create(_body(Decimal("99.00")), "order-1")


def _body(amount: Decimal) -> PaymentCreate:
    return PaymentCreate(
        amount=amount,
        currency="RUB",
        description="order",
        metadata={"order_id": "1"},
        webhook_url=HttpUrl("https://example.com/hook"),
    )


def _stored(body: PaymentCreate, key: str) -> Payment:
    return Payment(
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        details=body.metadata,
        status=PaymentStatus.PENDING,
        idempotency_key=key,
        request_hash=payment_fingerprint(
            amount=body.amount,
            currency=body.currency,
            description=body.description,
            metadata=body.metadata,
            webhook_url=str(body.webhook_url),
        ),
        webhook_url=str(body.webhook_url),
        created_at=datetime(2026, 10, 7, tzinfo=UTC),
    )


class _Session:
    async def flush(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _Payments:
    def __init__(self, existing: Payment | None = None) -> None:
        self.existing = existing
        self.added: list[Payment] = []

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        if self.existing is not None and self.existing.idempotency_key == key:
            return self.existing
        return None

    def add(self, payment: Payment) -> None:
        self.added.append(payment)


class _Outbox:
    def __init__(self) -> None:
        self.added = []

    def add(self, event) -> None:
        self.added.append(event)
