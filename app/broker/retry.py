from typing import Any

from app.broker.publisher import PaymentEventPublisher

MAX_PROCESSING_ATTEMPTS = 3


async def publish_retry_or_dlq(
    publisher: PaymentEventPublisher,
    payload: dict[str, Any],
    retry_count: int,
    error: str,
) -> None:
    if retry_count <= MAX_PROCESSING_ATTEMPTS:
        await publisher.publish_processing_retry(payload, retry_count)
        return

    await publisher.publish_processing_dlq(payload, error)
