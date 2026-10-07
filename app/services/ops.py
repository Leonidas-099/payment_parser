from uuid import UUID

from app.core.exceptions import OutboxEventNotFound, OutboxNotFailed
from app.models.dead_letter import DeadLetter
from app.models.enums import OutboxStatus
from app.models.outbox import OutboxEvent
from app.repositories.dead_letter import DeadLetterRepository
from app.repositories.outbox import OutboxRepository


class OutboxAdminService:
    def __init__(self, outbox: OutboxRepository) -> None:
        self._outbox = outbox

    async def list_failed(self) -> list[OutboxEvent]:
        return await self._outbox.list_failed()

    async def retry(self, event_id: UUID) -> OutboxEvent:
        event = await self._outbox.get(event_id)
        if event is None:
            raise OutboxEventNotFound(event_id)
        if event.status != OutboxStatus.FAILED:
            raise OutboxNotFailed(event_id)
        event.status = OutboxStatus.PENDING
        event.attempts = 0
        event.last_error = None
        event.locked_at = None
        return event


class DeadLetterService:
    def __init__(self, letters: DeadLetterRepository) -> None:
        self._letters = letters

    async def record(self, *, payment_id: UUID, payload: dict, attempt: int) -> None:
        await self._letters.record(payment_id=payment_id, payload=payload, attempt=attempt)

    async def list_recent(self) -> list[DeadLetter]:
        return await self._letters.list_recent()
