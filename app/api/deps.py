from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.dead_letter import DeadLetterRepository
from app.repositories.outbox import OutboxRepository
from app.repositories.payment import PaymentRepository
from app.services.ops import DeadLetterService, OutboxAdminService
from app.services.payment import PaymentService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_payment_service(session: SessionDep) -> PaymentService:
    return PaymentService(session, PaymentRepository(session), OutboxRepository(session))


def parse_idempotency_key(
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> str:
    key = idempotency_key.strip()
    if not key or len(key) > 255:
        raise HTTPException(
            status_code=422,
            detail="Idempotency-Key must contain 1 to 255 characters",
        )
    return key


def get_outbox_admin(session: SessionDep) -> OutboxAdminService:
    return OutboxAdminService(OutboxRepository(session))


def get_dead_letter_service(session: SessionDep) -> DeadLetterService:
    return DeadLetterService(DeadLetterRepository(session))


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]
IdempotencyKeyDep = Annotated[str, Depends(parse_idempotency_key)]
OutboxAdminDep = Annotated[OutboxAdminService, Depends(get_outbox_admin)]
DeadLetterServiceDep = Annotated[DeadLetterService, Depends(get_dead_letter_service)]
