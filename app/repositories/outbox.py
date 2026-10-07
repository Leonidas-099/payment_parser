from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OutboxStatus
from app.models.outbox import OutboxEvent


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, event: OutboxEvent) -> None:
        self._session.add(event)

    async def get(self, event_id: UUID) -> OutboxEvent | None:
        return await self._session.get(OutboxEvent, event_id)

    async def list_failed(self) -> list[OutboxEvent]:
        statement = (
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatus.FAILED)
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
        )
        return list(await self._session.scalars(statement))

    async def claim(self, *, batch_size: int, now: datetime, stale_before: datetime) -> list[OutboxEvent]:
        await self._release_stale(stale_before)
        ids = list(await self._session.scalars(self._pending_ids(batch_size)))
        if not ids:
            return []
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id.in_(ids))
            .values(
                status=OutboxStatus.PUBLISHING,
                locked_at=now,
                attempts=OutboxEvent.attempts + 1,
            )
        )
        events = await self._session.scalars(
            select(OutboxEvent).where(OutboxEvent.id.in_(ids)).order_by(OutboxEvent.created_at, OutboxEvent.id)
        )
        return list(events)

    async def mark_published(self, event_id: UUID, published_at: datetime) -> None:
        await self._session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(status=OutboxStatus.PUBLISHED, published_at=published_at, locked_at=None)
        )

    async def release_after_failure(self, event_id: UUID, error: str, max_attempts: int) -> None:
        event = await self._session.get(OutboxEvent, event_id)
        if event is None:
            return
        event.status = OutboxStatus.FAILED if event.attempts >= max_attempts else OutboxStatus.PENDING
        event.last_error = error[:2000]
        event.locked_at = None

    async def _release_stale(self, stale_before: datetime) -> None:
        await self._session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.PUBLISHING,
                OutboxEvent.locked_at.is_not(None),
                OutboxEvent.locked_at < stale_before,
            )
            .values(status=OutboxStatus.PENDING, locked_at=None)
        )

    def _pending_ids(self, batch_size: int):
        return (
            select(OutboxEvent.id)
            .where(OutboxEvent.status == OutboxStatus.PENDING)
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
