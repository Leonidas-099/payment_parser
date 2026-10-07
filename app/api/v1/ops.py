from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import DeadLetterServiceDep, OutboxAdminDep
from app.api.mappers import to_dead_letter, to_failed_outbox, to_outbox_retry
from app.core.security import require_api_key
from app.schemas.ops import DeadLetterRead, FailedOutboxRead, OutboxRetryRead

router = APIRouter(tags=["operations"], dependencies=[Depends(require_api_key)])


@router.get("/outbox/failed", response_model=list[FailedOutboxRead])
async def list_failed_outbox(service: OutboxAdminDep) -> list[FailedOutboxRead]:
    return [to_failed_outbox(event) for event in await service.list_failed()]


@router.post(
    "/outbox/{event_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=OutboxRetryRead,
)
async def retry_outbox_event(event_id: UUID, service: OutboxAdminDep) -> OutboxRetryRead:
    return to_outbox_retry(await service.retry(event_id))


@router.get("/dead-letters", response_model=list[DeadLetterRead])
async def list_dead_letters(service: DeadLetterServiceDep) -> list[DeadLetterRead]:
    return [to_dead_letter(letter) for letter in await service.list_recent()]
