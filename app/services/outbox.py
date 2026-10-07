import asyncio
import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.clock import utcnow
from app.core.config import Settings
from app.repositories.outbox import OutboxRepository
from app.services.contracts import EventPublisher

logger = logging.getLogger(__name__)


class OutboxRelay:
    """Claim outbox rows, commit, then publish. A row lock is never held across the broker call."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: EventPublisher,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._settings = settings

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                published = await self.publish_once()
            except Exception:
                logger.exception("outbox relay iteration failed")
                published = False
            if stop.is_set():
                return
            if published:
                continue
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._settings.outbox_poll_interval_seconds)
            except TimeoutError:
                continue

    async def publish_once(self) -> bool:
        now = utcnow()
        stale_before = now - timedelta(seconds=self._settings.outbox_lock_timeout_seconds)
        async with self._session_factory() as session:
            events = await OutboxRepository(session).claim(
                batch_size=self._settings.outbox_batch_size,
                now=now,
                stale_before=stale_before,
            )
            await session.commit()

        if not events:
            return False

        for event in events:
            await self._publish(event.id, event.payload)
        return True

    async def _publish(self, event_id, payload) -> None:
        try:
            await self._publisher.publish_new(payload)
        except Exception as exc:
            logger.exception("failed to publish outbox event %s", event_id)
            await self._record_failure(event_id, str(exc))
            return
        async with self._session_factory() as session:
            await OutboxRepository(session).mark_published(event_id, utcnow())
            await session.commit()

    async def _record_failure(self, event_id, error: str) -> None:
        async with self._session_factory() as session:
            await OutboxRepository(session).release_after_failure(
                event_id,
                error,
                self._settings.outbox_max_attempts,
            )
            await session.commit()
