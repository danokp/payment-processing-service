import asyncio
import logging

from faststream.rabbit import RabbitBroker

from app.broker.publisher import PaymentEventPublisher
from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models.outbox import OutboxEvent
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
) -> int:
    sessionmaker = get_sessionmaker()
    published_count = 0

    async with sessionmaker() as session:
        async with session.begin():
            repository = OutboxRepository(session)
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
    broker = RabbitBroker(settings.rabbitmq_url)
    publisher = PaymentEventPublisher(broker)

    async with broker:
        while True:
            await publish_once(publisher, settings.outbox_batch_size)
            await asyncio.sleep(settings.outbox_poll_interval_seconds)


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
