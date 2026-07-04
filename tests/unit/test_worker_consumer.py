import os
from uuid import uuid4

import pytest

os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

from app.services.consumer import PaymentNotFoundError, WebhookDeliveryError
from app.workers.consumer import process_message, register_topology_hook


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeSessionFactory:
    def __init__(self) -> None:
        self.session = FakeSession()

    def __call__(self) -> FakeSession:
        return self.session


class FakePublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, str]] = []

    async def publish_retry_or_dlq(self, payload: dict, error: str) -> None:
        self.calls.append((payload, error))


async def fake_retry_scheduler(
    retry_publisher: FakePublisher, payload: dict, error: str
) -> None:
    await retry_publisher.publish_retry_or_dlq(payload, error)


class FakeService:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.payment_ids = []

    async def process_payment(self, payment_id) -> None:
        self.payment_ids.append(payment_id)
        if self.exc is not None:
            raise self.exc


class FakeApp:
    def __init__(self) -> None:
        self.after_startup_callbacks = []
        self.on_startup_callbacks = []

    def after_startup(self, callback):
        self.after_startup_callbacks.append(callback)
        return callback

    def on_startup(self, callback):
        self.on_startup_callbacks.append(callback)
        return callback


class FakeBroker:
    def __init__(self) -> None:
        self.topology_declared = False


@pytest.mark.asyncio
async def test_register_topology_hook_prefers_after_startup(monkeypatch) -> None:
    app = FakeApp()
    broker = FakeBroker()

    async def fake_declare_topology(callback_broker) -> None:
        assert callback_broker is broker
        callback_broker.topology_declared = True

    monkeypatch.setattr(
        "app.workers.consumer.declare_topology", fake_declare_topology
    )

    register_topology_hook(app, broker)

    assert len(app.after_startup_callbacks) == 1
    assert app.on_startup_callbacks == []

    await app.after_startup_callbacks[0]()

    assert broker.topology_declared is True


@pytest.mark.asyncio
async def test_process_message_commits_successful_payment() -> None:
    payment_id = uuid4()
    session_factory = FakeSessionFactory()
    publisher = FakePublisher()
    service = FakeService()

    await process_message(
        {"payment_id": str(payment_id)},
        session_factory,
        publisher,
        service_builder=lambda session: service,
        retry_scheduler=fake_retry_scheduler,
    )

    assert service.payment_ids == [payment_id]
    assert session_factory.session.commits == 1
    assert session_factory.session.rollbacks == 0
    assert publisher.calls == []


@pytest.mark.asyncio
async def test_process_message_rolls_back_and_acks_non_retryable_consumer_error() -> None:
    payment_id = uuid4()
    session_factory = FakeSessionFactory()
    publisher = FakePublisher()
    service = FakeService(PaymentNotFoundError(str(payment_id)))

    await process_message(
        {"payment_id": str(payment_id)},
        session_factory,
        publisher,
        service_builder=lambda session: service,
        retry_scheduler=fake_retry_scheduler,
    )

    assert session_factory.session.commits == 0
    assert session_factory.session.rollbacks == 1
    assert publisher.calls == []


@pytest.mark.asyncio
async def test_process_message_commits_retryable_state_before_scheduling_retry() -> None:
    payment_id = uuid4()
    session_factory = FakeSessionFactory()
    publisher = FakePublisher()
    service = FakeService(WebhookDeliveryError("webhook down"))

    await process_message(
        {"payment_id": str(payment_id), "retry_count": 1},
        session_factory,
        publisher,
        service_builder=lambda session: service,
        retry_scheduler=fake_retry_scheduler,
    )

    assert session_factory.session.commits == 1
    assert session_factory.session.rollbacks == 0
    assert publisher.calls == [
        ({"payment_id": str(payment_id), "retry_count": 1}, "webhook down")
    ]


@pytest.mark.asyncio
async def test_process_message_rolls_back_unexpected_error_before_scheduling_retry() -> None:
    payment_id = uuid4()
    session_factory = FakeSessionFactory()
    publisher = FakePublisher()
    service = FakeService(RuntimeError("db unavailable"))

    await process_message(
        {"payment_id": str(payment_id)},
        session_factory,
        publisher,
        service_builder=lambda session: service,
        retry_scheduler=fake_retry_scheduler,
    )

    assert session_factory.session.commits == 0
    assert session_factory.session.rollbacks == 1
    assert publisher.calls == [({"payment_id": str(payment_id)}, "db unavailable")]
