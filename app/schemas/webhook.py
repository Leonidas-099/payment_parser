from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class WebhookNotification:
    url: str
    payment_id: UUID
    status: str
    amount: str
    currency: str
    processed_at: datetime

    def body(self) -> dict[str, str]:
        return {
            "payment_id": str(self.payment_id),
            "status": self.status,
            "amount": self.amount,
            "currency": self.currency,
            "processed_at": self.processed_at.isoformat(),
        }
