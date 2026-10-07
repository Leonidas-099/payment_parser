from faststream.rabbit import Channel, RabbitBroker

_SHUTDOWN_GRACE_SECONDS = 35.0


def create_broker(url: str) -> RabbitBroker:
    return RabbitBroker(
        url,
        default_channel=Channel(
            prefetch_count=1,
            publisher_confirms=True,
            on_return_raises=True,
        ),
        graceful_timeout=_SHUTDOWN_GRACE_SECONDS,
    )
