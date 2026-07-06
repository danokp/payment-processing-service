from app.core.config import Settings
from app.core.time import utc_now
from app.db.models.outbox import OutboxEvent, OutboxStatus
from app.repositories.outbox import OutboxRepository


def make_event(attempts: int = 0) -> OutboxEvent:
    now = utc_now()
    return OutboxEvent(
        event_type="unsupported",
        payload={},
        status=OutboxStatus.PENDING,
        attempts=attempts,
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )


def test_publish_failure_marks_event_failed_after_max_attempts() -> None:
    settings = Settings(
        API_KEY="secret",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        RABBITMQ_URL="amqp://guest:guest@localhost:5672/",
    )
    event = make_event(attempts=settings.DEFAULT_OUTBOX_MAX_ATTEMPTS - 1)
    repository = OutboxRepository(session=None, settings=settings)

    repository.mark_publish_failed(event, "unsupported event")

    assert event.attempts == settings.DEFAULT_OUTBOX_MAX_ATTEMPTS
    assert event.status == OutboxStatus.FAILED
    assert event.last_error == "unsupported event"
