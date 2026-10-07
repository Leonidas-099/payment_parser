from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import IdempotencyKeyDep, PaymentServiceDep
from app.api.mappers import to_accepted, to_read
from app.core.security import require_api_key
from app.schemas.payment import PaymentAccepted, PaymentCreate, PaymentRead

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAccepted)
async def create_payment(
    body: PaymentCreate,
    idempotency_key: IdempotencyKeyDep,
    service: PaymentServiceDep,
) -> PaymentAccepted:
    payment = await service.create(body, idempotency_key)
    return to_accepted(payment)


@router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment(payment_id: UUID, service: PaymentServiceDep) -> PaymentRead:
    return to_read(await service.get(payment_id))
