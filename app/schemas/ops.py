from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import OutboxStatus


class FailedOutboxRead(BaseModel):
    id: UUID
    aggregate_id: UUID
    event_type: str
    payload: dict[str, Any]
    status: OutboxStatus
    attempts: int
    last_error: str | None
    created_at: datetime


class OutboxRetryRead(BaseModel):
    id: UUID
    status: OutboxStatus


class DeadLetterRead(BaseModel):
    id: UUID
    payment_id: UUID
    attempt: int
    payload: dict[str, Any]
    created_at: datetime
