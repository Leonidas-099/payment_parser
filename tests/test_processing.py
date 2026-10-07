import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.core.exceptions import PaymentNotFound
from app.models.enums import Currency, PaymentStatus
from app.models.payment import Payment
from app.services.processing import ProcessingService


def test_pending_payment_is_charged_once_and_notified() -> None:
    asyncio.run(_pending())


def test_terminal_payment_is_not_charged_again() -> None:
    asyncio.run(_already_processed())


def test_delivered_webhook_is_not_repeated() -> None:
    asyncio.run(_already_delivered())


def test_missing_payment_is_a_technical_error() -> None:
    try:
        asyncio.run(_missing())
    except PaymentNotFound:
        return
    raise AssertionError("expected PaymentNotFound")


async def _pending() -> None:
    payment = _payment(PaymentStatus.PENDING)
    session = _Session()
    gateway = _Gateway(PaymentStatus.FAILED)
    webhooks = _Webhooks()
    service = ProcessingService(session, _Repository(payment), gateway, webhooks)

    await service.handle(payment.id)

    assert gateway.calls == 1
    assert payment.status == PaymentStatus.FAILED
    assert payment.processed_at is not None
    assert payment.webhook_sent_at is not None
    assert [item.status for item in webhooks.sent] == [PaymentStatus.FAILED]
    assert session.commits == 3


async def _already_processed() -> None:
    payment = _payment(PaymentStatus.SUCCEEDED)
    payment.processed_at = datetime(2026, 10, 7, tzinfo=UTC)
    gateway = _Gateway(PaymentStatus.FAILED)
    webhooks = _Webhooks()
    service = ProcessingService(_Session(), _Repository(payment), gateway, webhooks)

    await service.handle(payment.id)

    assert gateway.calls == 0
    assert payment.status == PaymentStatus.SUCCEEDED
    assert len(webhooks.sent) == 1


async def _already_delivered() -> None:
    payment = _payment(PaymentStatus.SUCCEEDED)
    payment.processed_at = datetime(2026, 10, 7, tzinfo=UTC)
    payment.webhook_sent_at = payment.processed_at
    gateway = _Gateway(PaymentStatus.FAILED)
    webhooks = _Webhooks()
    service = ProcessingService(_Session(), _Repository(payment), gateway, webhooks)

    await service.handle(payment.id)

    assert gateway.calls == 0
    assert webhooks.sent == []


async def _missing() -> None:
    await ProcessingService(_Session(), _Repository(None), _Gateway(PaymentStatus.SUCCEEDED), _Webhooks()).handle(
        uuid4()
    )


def _payment(status: PaymentStatus) -> Payment:
    return Payment(
        id=uuid4(),
        amount=Decimal("15.50"),
        currency=Currency.RUB,
        description="order",
        details={"order_id": "1001"},
        status=status,
        idempotency_key="order-1001",
        request_hash="hash",
        webhook_url="https://example.com/hook",
        created_at=datetime(2026, 10, 7, tzinfo=UTC),
    )


class _Session:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class _Repository:
    def __init__(self, payment: Payment | None) -> None:
        self.payment = payment

    async def get(self, payment_id):
        if self.payment is not None and self.payment.id == payment_id:
            return self.payment
        return None

    async def mark_processed(self, payment_id, status, processed_at) -> bool:
        if self.payment is None or self.payment.status != PaymentStatus.PENDING:
            return False
        self.payment.status = status
        self.payment.processed_at = processed_at
        return True

    async def mark_webhook_sent(self, payment_id, sent_at) -> None:
        assert self.payment is not None
        self.payment.webhook_sent_at = sent_at


class _Gateway:
    def __init__(self, outcome: PaymentStatus) -> None:
        self.outcome = outcome
        self.calls = 0

    async def authorize(self) -> PaymentStatus:
        self.calls += 1
        return self.outcome


class _Webhooks:
    def __init__(self) -> None:
        self.sent = []

    async def send(self, notification) -> None:
        self.sent.append(notification)
