import pytest

from app.broker.retry import publish_retry_or_dlq


class FakePublisher:
    def __init__(self) -> None:
        self.retries: list[tuple[dict, int]] = []
        self.dlqs: list[tuple[dict, str]] = []

    async def publish_processing_retry(self, payload: dict, retry_count: int) -> None:
        self.retries.append((payload, retry_count))

    async def publish_processing_dlq(self, payload: dict, error: str) -> None:
        self.dlqs.append((payload, error))


@pytest.mark.asyncio
async def test_missing_retry_count_publishes_first_retry() -> None:
    publisher = FakePublisher()
    payload = {"payment_id": "payment-1"}

    await publish_retry_or_dlq(publisher, payload, "failed")

    assert publisher.retries == [({"payment_id": "payment-1", "retry_count": 1}, 1)]
    assert publisher.dlqs == []


@pytest.mark.asyncio
async def test_existing_retry_count_publishes_next_retry() -> None:
    publisher = FakePublisher()
    payload = {"payment_id": "payment-1", "retry_count": 2}

    await publish_retry_or_dlq(publisher, payload, "failed")

    assert publisher.retries == [({"payment_id": "payment-1", "retry_count": 3}, 3)]
    assert publisher.dlqs == []


@pytest.mark.asyncio
async def test_max_retry_count_publishes_dlq() -> None:
    publisher = FakePublisher()
    payload = {"payment_id": "payment-1", "retry_count": 3}

    await publish_retry_or_dlq(publisher, payload, "failed")

    assert publisher.retries == []
    assert publisher.dlqs == [(payload, "failed")]


@pytest.mark.parametrize("retry_count", [-1, "not-an-int"])
@pytest.mark.asyncio
async def test_invalid_retry_count_is_normalized_before_increment(
    retry_count: object,
) -> None:
    publisher = FakePublisher()
    payload = {"payment_id": "payment-1", "retry_count": retry_count}

    await publish_retry_or_dlq(publisher, payload, "failed")

    assert publisher.retries == [({"payment_id": "payment-1", "retry_count": 1}, 1)]
    assert publisher.dlqs == []
