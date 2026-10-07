import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.exceptions import PaymentNotFound
from app.models.enums import PaymentStatus
from app.models.payment import Payment
from app.policies.money import format_amount
from app.repositories.payment import PaymentRepository
from app.schemas.webhook import WebhookNotification
from app.services.contracts import PaymentGateway, WebhookSender

logger = logging.getLogger(__name__)


class ProcessingService:
    """Apply the gateway outcome once, then deliver the webhook.

    The database transaction is closed before the gateway sleep and the HTTP call.
    """

    def __init__(
        self,
        session: AsyncSession,
        payments: PaymentRepository,
        gateway: PaymentGateway,
        webhooks: WebhookSender,
    ) -> None:
        self._session = session
        self._payments = payments
        self._gateway = gateway
        self._webhooks = webhooks

    async def handle(self, payment_id: UUID) -> None:
        payment = await self._require(payment_id)
        if payment.webhook_sent_at is not None:
            return

        needs_processing = payment.status == PaymentStatus.PENDING
        await self._session.commit()

        if needs_processing:
            outcome = await self._gateway.authorize()
            await self._payments.mark_processed(payment_id, outcome, utcnow())
            await self._session.commit()
            logger.info("payment %s gateway outcome %s", payment_id, outcome)

        payment = await self._require(payment_id)
        if payment.webhook_sent_at is not None:
            return
        if payment.status == PaymentStatus.PENDING or payment.processed_at is None:
            raise RuntimeError(f"Payment {payment_id} is not ready for notification")

        await self._webhooks.send(
            WebhookNotification(
                url=payment.webhook_url,
                payment_id=payment.id,
                status=payment.status,
                amount=format_amount(payment.amount),
                currency=payment.currency,
                processed_at=payment.processed_at,
            )
        )
        await self._payments.mark_webhook_sent(payment.id, utcnow())
        await self._session.commit()
        logger.info("payment %s webhook delivered", payment.id)

    async def _require(self, payment_id: UUID) -> Payment:
        payment = await self._payments.get(payment_id)
        if payment is None:
            raise PaymentNotFound(payment_id)
        return payment
