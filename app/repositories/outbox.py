from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.outbox import OutboxEvent, OutboxStatus
from app.services.backoff import retry_delay_seconds


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_payment_created(self, payment_id: UUID) -> OutboxEvent:
        now = utc_now()
        event = OutboxEvent(
            event_type="payment.created",
            payload={"payment_id": str(payment_id)},
            status=OutboxStatus.PENDING,
            attempts=0,
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_publishable_batch(self, limit: int) -> list[OutboxEvent]:
        result = await self.session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.PENDING,
                OutboxEvent.next_attempt_at <= utc_now(),
            )
            .order_by(OutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars())

    def mark_published(self, event: OutboxEvent) -> None:
        now = utc_now()
        event.status = OutboxStatus.PUBLISHED
        event.published_at = now
        event.updated_at = now

    def mark_publish_failed(self, event: OutboxEvent, error: str) -> None:
        now = utc_now()
        event.attempts += 1
        event.last_error = error[:2000]
        event.next_attempt_at = now + timedelta(seconds=retry_delay_seconds(event.attempts))
        event.updated_at = now
