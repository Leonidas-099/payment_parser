from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentStatus
from app.models.payment import Payment


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, payment_id: UUID) -> Payment | None:
        return await self._session.get(Payment, payment_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        statement = select(Payment).where(Payment.idempotency_key == idempotency_key)
        return await self._session.scalar(statement)

    def add(self, payment: Payment) -> None:
        self._session.add(payment)

    async def mark_processed(
        self,
        payment_id: UUID,
        status: PaymentStatus,
        processed_at: datetime,
    ) -> bool:
        statement = (
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING)
            .values(status=status, processed_at=processed_at)
        )
        result = await self._session.execute(statement)
        return result.rowcount == 1

    async def increment_processing_attempts(self, payment_id: UUID) -> int | None:
        statement = (
            update(Payment)
            .where(Payment.id == payment_id)
            .values(processing_attempts=Payment.processing_attempts + 1)
            .returning(Payment.processing_attempts)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def mark_webhook_sent(self, payment_id: UUID, sent_at: datetime) -> None:
        statement = (
            update(Payment)
            .where(Payment.id == payment_id, Payment.webhook_sent_at.is_(None))
            .values(webhook_sent_at=sent_at)
        )
        await self._session.execute(statement)
