from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# Pauses before the second and third broker delivery. The third failure is final.
RETRY_DELAYS_SECONDS = (2, 4)
MAX_ATTEMPTS = len(RETRY_DELAYS_SECONDS) + 1

# The first webhook call is immediate. Each value is the pause before the next call.
WEBHOOK_RETRY_PAUSES_SECONDS = (1, 2, 4)


class RetryAction(StrEnum):
    RETRY = "retry"
    DEAD = "dead"


@dataclass(frozen=True)
class RetryDecision:
    action: RetryAction
    attempt: int
    delay_seconds: int | None


def should_process(attempt: int) -> bool:
    """A persisted attempt above the limit is a redelivery after a crash, not a new try."""
    return 1 <= attempt <= MAX_ATTEMPTS


def decide(attempt: int) -> RetryDecision:
    if attempt < 1:
        raise ValueError("attempt must be positive")
    if attempt > len(RETRY_DELAYS_SECONDS):
        return RetryDecision(RetryAction.DEAD, attempt, None)
    return RetryDecision(RetryAction.RETRY, attempt, RETRY_DELAYS_SECONDS[attempt - 1])


def next_attempt(headers: Mapping[str, Any]) -> int:
    return _retry_count(headers) + 1


def reported_attempt(headers: Mapping[str, Any]) -> int:
    """Attempt number already stored on a message, including one parked in the DLQ."""
    return _retry_count(headers)


def _retry_count(headers: Mapping[str, Any]) -> int:
    raw = headers.get("x-retry-count", 0)
    if isinstance(raw, bytes):
        raw = raw.decode()
    if raw is None or raw == "":
        return 0
    return int(raw)
