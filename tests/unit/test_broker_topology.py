import pytest

from app.broker.topology import (
    DLQ_ROUTING_KEY,
    PAYMENT_CREATED_ROUTING_KEY,
    PAYMENTS_DLX,
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    PAYMENTS_RETRY_1_QUEUE,
    PAYMENTS_RETRY_2_QUEUE,
    PAYMENTS_RETRY_3_QUEUE,
    PAYMENTS_RETRY_EXCHANGE,
    RETRY_ROUTING_KEYS,
    declare_topology,
)


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
    assert PAYMENTS_NEW_QUEUE.routing_key == PAYMENT_CREATED_ROUTING_KEY
    assert PAYMENTS_RETRY_1_QUEUE.routing_key == RETRY_ROUTING_KEYS[0]
    assert PAYMENTS_RETRY_2_QUEUE.routing_key == RETRY_ROUTING_KEYS[1]
    assert PAYMENTS_RETRY_3_QUEUE.routing_key == RETRY_ROUTING_KEYS[2]
    assert DLQ_ROUTING_KEY == "payments.new.dlq"


@pytest.mark.asyncio
async def test_declare_topology_binds_queues_to_published_exchanges() -> None:
    broker = FakeBroker()

    await declare_topology(broker)

    assert set(broker.exchanges) == {
        PAYMENTS_EXCHANGE.name,
        PAYMENTS_RETRY_EXCHANGE.name,
        PAYMENTS_DLX.name,
    }
    assert broker.queues[PAYMENTS_NEW_QUEUE.name].bindings == [
        (PAYMENTS_EXCHANGE.name, PAYMENT_CREATED_ROUTING_KEY)
    ]
    assert broker.queues[PAYMENTS_RETRY_1_QUEUE.name].bindings == [
        (PAYMENTS_RETRY_EXCHANGE.name, RETRY_ROUTING_KEYS[0])
    ]
    assert broker.queues[PAYMENTS_RETRY_2_QUEUE.name].bindings == [
        (PAYMENTS_RETRY_EXCHANGE.name, RETRY_ROUTING_KEYS[1])
    ]
    assert broker.queues[PAYMENTS_RETRY_3_QUEUE.name].bindings == [
        (PAYMENTS_RETRY_EXCHANGE.name, RETRY_ROUTING_KEYS[2])
    ]
    assert broker.queues["payments.dlq"].bindings == [
        (PAYMENTS_DLX.name, DLQ_ROUTING_KEY)
    ]
