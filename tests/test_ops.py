import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.exceptions import OutboxEventNotFound, OutboxNotFailed
from app.models.enums import OutboxStatus
from app.services.ops import OutboxAdminService


def test_only_a_failed_outbox_event_returns_to_pending() -> None:
    asyncio.run(_retry_failed())


def test_pending_outbox_event_is_not_retried() -> None:
    with pytest.raises(OutboxNotFailed):
        asyncio.run(_retry(OutboxStatus.PENDING))


def test_missing_outbox_event_is_not_found() -> None:
    with pytest.raises(OutboxEventNotFound):
        asyncio.run(OutboxAdminService(_Outbox(None)).retry(uuid4()))


async def _retry_failed() -> None:
    event = await _retry(OutboxStatus.FAILED)
    assert event.status == OutboxStatus.PENDING
    assert event.attempts == 0
    assert event.last_error is None
    assert event.locked_at is None


async def _retry(status: OutboxStatus):
    event = _Event(status)
    return await OutboxAdminService(_Outbox(event)).retry(event.id)


class _Event:
    def __init__(self, status: OutboxStatus) -> None:
        self.id = uuid4()
        self.status = status
        self.attempts = 10
        self.last_error = "broker unavailable"
        self.locked_at = datetime(2026, 10, 7, tzinfo=UTC)


class _Outbox:
    def __init__(self, event: _Event | None) -> None:
        self.event = event

    async def get(self, event_id):
        if self.event is not None and self.event.id == event_id:
            return self.event
        return None
