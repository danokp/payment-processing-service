import pytest

from app.broker.topology import (
    DLQ_ROUTING_KEY,
    PAYMENT_CREATED_ROUTING_KEY,
    PAYMENTS_DLX,
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    PAYMENTS_RETRY_EXCHANGE,
    build_retry_queues,
    build_retry_routing_keys,
    declare_topology,
)
from app.core.config import Settings


class FakeDeclaredQueue:
    def __init__(self, name: str) -> None:
        self.name = name
        self.bindings: list[tuple[str, str]] = []

    async def bind(self, exchange: object, routing_key: str) -> None:
        self.bindings.append((exchange.name, routing_key))


class FakeBroker:
    def __init__(self) -> None:
        self.exchanges: dict[str, object] = {}
        self.queues: dict[str, FakeDeclaredQueue] = {}

    async def declare_exchange(self, exchange: object) -> object:
        self.exchanges[exchange.name] = exchange
        return exchange

    async def declare_queue(self, queue: object) -> FakeDeclaredQueue:
        declared_queue = FakeDeclaredQueue(queue.name)
        self.queues[queue.name] = declared_queue
        return declared_queue


def test_topology_queue_routing_keys_match_bindings() -> None:
    settings = Settings(
        API_KEY="secret",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        RABBITMQ_URL="amqp://guest:guest@localhost:5672/",
    )
    retry_queues = build_retry_queues(settings)
    retry_routing_keys = build_retry_routing_keys(settings)

    assert PAYMENTS_NEW_QUEUE.routing_key == PAYMENT_CREATED_ROUTING_KEY
    assert tuple(queue.routing_key for queue in retry_queues) == retry_routing_keys
    assert DLQ_ROUTING_KEY == "payments.new.dlq"


def test_retry_queues_match_processing_retry_delays() -> None:
    settings = Settings(
        API_KEY="secret",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        RABBITMQ_URL="amqp://guest:guest@localhost:5672/",
    )

    retry_queues = build_retry_queues(settings)

    assert len(retry_queues) == len(settings.DEFAULT_PAYMENT_PROCESSING_RETRY_DELAYS_SECONDS)
    assert tuple(
        queue.arguments["x-message-ttl"] for queue in retry_queues
    ) == tuple(delay * 1000 for delay in settings.DEFAULT_PAYMENT_PROCESSING_RETRY_DELAYS_SECONDS)


@pytest.mark.asyncio
async def test_declare_topology_binds_queues_to_published_exchanges() -> None:
    broker = FakeBroker()
    settings = Settings(
        API_KEY="secret",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        RABBITMQ_URL="amqp://guest:guest@localhost:5672/",
    )
    retry_queues = build_retry_queues(settings)
    retry_routing_keys = build_retry_routing_keys(settings)

    await declare_topology(broker, settings)

    assert set(broker.exchanges) == {
        PAYMENTS_EXCHANGE.name,
        PAYMENTS_RETRY_EXCHANGE.name,
        PAYMENTS_DLX.name,
    }
    assert broker.queues[PAYMENTS_NEW_QUEUE.name].bindings == [
        (PAYMENTS_EXCHANGE.name, PAYMENT_CREATED_ROUTING_KEY)
    ]
    for queue, routing_key in zip(retry_queues, retry_routing_keys, strict=True):
        assert broker.queues[queue.name].bindings == [
            (PAYMENTS_RETRY_EXCHANGE.name, routing_key)
        ]
    assert broker.queues["payments.dlq"].bindings == [
        (PAYMENTS_DLX.name, DLQ_ROUTING_KEY)
    ]
