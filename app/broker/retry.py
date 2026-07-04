from typing import Any

from app.broker.publisher import PaymentEventPublisher

MAX_PROCESSING_ATTEMPTS = 3


async def publish_retry_or_dlq(
    publisher: PaymentEventPublisher,
    payload: dict[str, Any],
    error: str,
) -> None:
    retry_count = _current_retry_count(payload)
    next_retry_count = retry_count + 1

    if next_retry_count <= MAX_PROCESSING_ATTEMPTS:
        await publisher.publish_processing_retry(
            {**payload, "retry_count": next_retry_count},
            next_retry_count,
        )
        return

    await publisher.publish_processing_dlq(payload, error)


def _current_retry_count(payload: dict[str, Any]) -> int:
    retry_count = payload.get("retry_count", 0)
    if not isinstance(retry_count, int) or retry_count < 0:
        return 0
    return retry_count
