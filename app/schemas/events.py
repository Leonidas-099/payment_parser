from typing import Literal
from uuid import UUID

from pydantic import BaseModel

PAYMENT_CREATED = "payment.created"


class PaymentCreated(BaseModel):
    payment_id: UUID
    event_type: Literal["payment.created"] = PAYMENT_CREATED
