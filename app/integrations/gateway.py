import asyncio
import random
from collections.abc import Awaitable, Callable

from app.models.enums import PaymentStatus


class EmulatedGateway:
    """Sleeps for a few seconds, then succeeds or declines according to a fixed rate."""

    def __init__(
        self,
        *,
        min_delay_seconds: float,
        max_delay_seconds: float,
        success_rate: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_source: random.Random | None = None,
    ) -> None:
        if min_delay_seconds > max_delay_seconds:
            raise ValueError("min_delay_seconds must not exceed max_delay_seconds")
        if not 0 <= success_rate <= 1:
            raise ValueError("success_rate must be between 0 and 1")
        self._min_delay_seconds = min_delay_seconds
        self._max_delay_seconds = max_delay_seconds
        self._success_rate = success_rate
        self._sleep = sleep
        self._random = random_source or random.Random()

    async def authorize(self) -> PaymentStatus:
        delay = self._random.uniform(self._min_delay_seconds, self._max_delay_seconds)
        await self._sleep(delay)
        if self._random.random() < self._success_rate:
            return PaymentStatus.SUCCEEDED
        return PaymentStatus.FAILED
