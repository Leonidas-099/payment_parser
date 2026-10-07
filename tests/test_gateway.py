import asyncio
import random

from app.integrations.gateway import EmulatedGateway
from app.models.enums import PaymentStatus


def test_gateway_success_and_decline_are_statuses() -> None:
    asyncio.run(_run())


async def _run() -> None:
    delays: list[float] = []

    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    success = EmulatedGateway(
        min_delay_seconds=2,
        max_delay_seconds=2,
        success_rate=1,
        sleep=sleep,
        random_source=random.Random(1),
    )
    decline = EmulatedGateway(
        min_delay_seconds=5,
        max_delay_seconds=5,
        success_rate=0,
        sleep=sleep,
        random_source=random.Random(1),
    )

    assert await success.authorize() is PaymentStatus.SUCCEEDED
    assert await decline.authorize() is PaymentStatus.FAILED
    assert delays == [2, 5]
