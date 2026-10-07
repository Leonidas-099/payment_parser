from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.models.dead_letter import DeadLetter


class DeadLetterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, *, payment_id: UUID, payload: dict, attempt: int) -> None:
        statement = (
            insert(DeadLetter)
            .values(
                payment_id=payment_id,
                payload=payload,
                attempt=attempt,
                created_at=utcnow(),
            )
            .on_conflict_do_nothing(constraint="uq_dead_letters_payment_attempt")
        )
        await self._session.execute(statement)

    async def list_recent(self) -> list[DeadLetter]:
        statement = select(DeadLetter).order_by(DeadLetter.created_at, DeadLetter.id)
        return list(await self._session.scalars(statement))
