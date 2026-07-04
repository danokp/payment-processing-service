import os
from uuid import uuid4

import pytest

os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

from app.broker.retry import MAX_PROCESSING_ATTEMPTS
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
        self.sessions = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


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
    def __init__(
        self,
        exc: Exception | None = None,
        *,
        needs_webhook: bool = False,
        webhook_exc: Exception | None = None,
    ) -> None:
        self.state_exc = exc
        self.webhook_exc = webhook_exc
        self.needs_webhook = needs_webhook
        self.payment_ids = []
        self.webhook_payment_ids = []

    async def process_payment_state(self, payment_id) -> bool:
        self.payment_ids.append(payment_id)
        if self.state_exc is not None:
            raise self.state_exc
        return self.needs_webhook

    async def send_webhook(self, payment_id) -> None:
        self.webhook_payment_ids.append(payment_id)
        if self.webhook_exc is not None:
            raise self.webhook_exc


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
    assert session_factory.sessions[0].commits == 1
    assert session_factory.sessions[0].rollbacks == 0
    assert publisher.calls == []


@pytest.mark.asyncio
async def test_process_message_sends_invalid_payment_id_to_dlq() -> None:
    session_factory = FakeSessionFactory()
    publisher = FakePublisher()

    await process_message(
        {"payment_id": "not-a-uuid"},
        session_factory,
        publisher,
        retry_scheduler=fake_retry_scheduler,
    )

    assert session_factory.sessions == []
    assert publisher.calls == [
        (
            {
                "payment_id": "not-a-uuid",
                "retry_count": MAX_PROCESSING_ATTEMPTS,
            },
            "badly formed hexadecimal UUID string",
        )
    ]


@pytest.mark.asyncio
async def test_process_message_sends_missing_payment_id_to_dlq() -> None:
    session_factory = FakeSessionFactory()
    publisher = FakePublisher()

    await process_message(
        {"unexpected": "payload"},
        session_factory,
        publisher,
        retry_scheduler=fake_retry_scheduler,
    )

    assert session_factory.sessions == []
    assert publisher.calls == [
        (
            {
                "unexpected": "payload",
                "retry_count": MAX_PROCESSING_ATTEMPTS,
            },
            "'payment_id'",
        )
    ]


@pytest.mark.asyncio
async def test_process_message_commits_terminal_state_before_sending_webhook() -> None:
    payment_id = uuid4()
    session_factory = FakeSessionFactory()
    publisher = FakePublisher()

    class ObservingService(FakeService):
        async def send_webhook(self, observed_payment_id) -> None:
            assert session_factory.sessions[0].commits == 1
            await super().send_webhook(observed_payment_id)

    service = ObservingService(needs_webhook=True)

    await process_message(
        {"payment_id": str(payment_id)},
        session_factory,
        publisher,
        service_builder=lambda session: service,
        retry_scheduler=fake_retry_scheduler,
    )

    assert service.payment_ids == [payment_id]
    assert service.webhook_payment_ids == [payment_id]
    assert session_factory.sessions[0].commits == 1
    assert session_factory.sessions[1].commits == 1
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

    assert session_factory.sessions[0].commits == 0
    assert session_factory.sessions[0].rollbacks == 1
    assert publisher.calls == [
        (
            {
                "payment_id": str(payment_id),
                "retry_count": MAX_PROCESSING_ATTEMPTS,
            },
            str(payment_id),
        )
    ]


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

    assert session_factory.sessions[0].commits == 1
    assert session_factory.sessions[0].rollbacks == 0
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

    assert session_factory.sessions[0].commits == 0
    assert session_factory.sessions[0].rollbacks == 1
    assert publisher.calls == [({"payment_id": str(payment_id)}, "db unavailable")]
