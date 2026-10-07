from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Error raised by an application service."""


class IdempotencyConflict(AppError):
    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__("Idempotency key was already used with a different payload")


class PaymentNotFound(AppError):
    def __init__(self, payment_id: UUID) -> None:
        self.payment_id = payment_id
        super().__init__("Payment not found")


class WebhookDeliveryError(AppError):
    def __init__(self, payment_id: UUID, attempts: int, reason: str) -> None:
        self.payment_id = payment_id
        self.attempts = attempts
        self.reason = reason
        super().__init__(reason)


class PublicationError(AppError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class OutboxEventNotFound(AppError):
    def __init__(self, event_id: UUID) -> None:
        self.event_id = event_id
        super().__init__("Outbox event not found")


class OutboxNotFailed(AppError):
    def __init__(self, event_id: UUID) -> None:
        self.event_id = event_id
        super().__init__("Only a failed outbox event can be retried")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IdempotencyConflict)
    async def handle_conflict(_request: Request, exc: IdempotencyConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(PaymentNotFound)
    async def handle_not_found(_request: Request, exc: PaymentNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(OutboxEventNotFound)
    async def handle_outbox_not_found(_request: Request, exc: OutboxEventNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(OutboxNotFailed)
    async def handle_outbox_not_failed(_request: Request, exc: OutboxNotFailed) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})
