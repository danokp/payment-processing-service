from typing import Any

from app.broker.publisher import PaymentEventPublisher
from app.core.config import Settings, get_settings


def max_processing_attempts(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    return len(settings.DEFAULT_PAYMENT_PROCESSING_RETRY_DELAYS_SECONDS)


async def publish_retry_or_dlq(
    publisher: PaymentEventPublisher,
    payload: dict[str, Any],
    error: str,
    *,
    settings: Settings | None = None,
    max_attempts: int | None = None,
) -> None:
    retry_count = _current_retry_count(payload)
    next_retry_count = retry_count + 1
    max_attempts = max_attempts or max_processing_attempts(settings)

    if next_retry_count <= max_attempts:
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
