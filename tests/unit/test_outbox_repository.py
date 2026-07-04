from app.core.time import utc_now
from app.models.outbox import OutboxEvent, OutboxStatus
from app.repositories.outbox import MAX_OUTBOX_ATTEMPTS, OutboxRepository


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
    event = make_event(attempts=MAX_OUTBOX_ATTEMPTS - 1)
    repository = OutboxRepository(session=None)

    repository.mark_publish_failed(event, "unsupported event")

    assert event.attempts == MAX_OUTBOX_ATTEMPTS
    assert event.status == OutboxStatus.FAILED
    assert event.last_error == "unsupported event"
