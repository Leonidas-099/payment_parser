import hashlib
import json
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.policies.money import format_amount


class IdempotencyDecision(StrEnum):
    CREATE = "create"
    REPLAY = "replay"
    CONFLICT = "conflict"


def payment_fingerprint(
    *,
    amount: Decimal,
    currency: str,
    description: str | None,
    metadata: dict[str, Any],
    webhook_url: str,
) -> str:
    payload = {
        "amount": format_amount(amount),
        "currency": currency,
        "description": description,
        "metadata": metadata,
        "webhook_url": webhook_url,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def decide(existing_hash: str | None, request_hash: str) -> IdempotencyDecision:
    if existing_hash is None:
        return IdempotencyDecision.CREATE
    if existing_hash == request_hash:
        return IdempotencyDecision.REPLAY
    return IdempotencyDecision.CONFLICT
