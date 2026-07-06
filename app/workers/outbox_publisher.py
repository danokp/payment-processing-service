import asyncio
import logging

from faststream.rabbit import RabbitBroker

from app.broker.publisher import PaymentEventPublisher
from app.broker.topology import declare_topology
from app.core.config import get_settings
from app.db.models.outbox import OutboxEvent
from app.db.session import get_sessionmaker
from app.repositories.outbox import OutboxRepository

logger = logging.getLogger(__name__)


async def _publish_event(publisher: PaymentEventPublisher, event: OutboxEvent) -> None:
    if event.event_type == "payment.created":
        await publisher.publish_payment_created(event.payload)
        return

    raise ValueError(f"Unsupported outbox event type: {event.event_type}")


async def publish_once(
    publisher: PaymentEventPublisher,
    batch_size: int,
    *,
    settings=None,
) -> int:
    sessionmaker = get_sessionmaker()
    published_count = 0

    async with sessionmaker() as session:
        async with session.begin():
            repository = OutboxRepository(session, settings=settings)
            events = await repository.get_publishable_batch(batch_size)

            for event in events:
                try:
                    await _publish_event(publisher, event)
                except Exception as exc:
                    repository.mark_publish_failed(event, str(exc))
                    logger.exception("Failed to publish outbox event %s", event.id)
                else:
                    repository.mark_published(event)
                    published_count += 1

    return published_count


async def run_forever() -> None:
    settings = get_settings()
    broker = RabbitBroker(settings.RABBITMQ_URL)
    publisher = PaymentEventPublisher(broker)

    async with broker:
        await declare_topology(broker, settings)

        while True:
            await publish_once(
                publisher,
                settings.OUTBOX_BATCH_SIZE,
                settings=settings,
            )
            await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL_SECONDS)


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
