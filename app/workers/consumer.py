from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from faststream import FastStream
from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.publisher import PaymentEventPublisher
from app.broker.retry import publish_retry_or_dlq
from app.broker.topology import PAYMENTS_NEW_QUEUE, declare_topology
from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.repositories.payments import PaymentRepository
from app.services.consumer import ConsumerProcessingError, PaymentConsumerService
from app.services.gateway import RandomPaymentGateway
from app.services.webhooks import WebhookClient

settings = get_settings()
broker = RabbitBroker(settings.rabbitmq_url)
app = FastStream(broker)

ServiceBuilder = Callable[[AsyncSession], PaymentConsumerService]
RetryScheduler = Callable[[PaymentEventPublisher, dict[str, Any], str], Awaitable[None]]


def build_service(session: AsyncSession) -> PaymentConsumerService:
    return PaymentConsumerService(
        PaymentRepository(session),
        RandomPaymentGateway(settings),
        WebhookClient(settings.webhook_timeout_seconds),
    )


def register_topology_hook(stream_app: FastStream, broker: RabbitBroker) -> None:
    startup = getattr(stream_app, "after_startup", None)
    if startup is None:
        startup = broker.on_startup

    @startup
    async def setup_broker_topology() -> None:
        await declare_topology(broker)


register_topology_hook(app, broker)


async def process_message(
    message: dict[str, Any],
    session_factory,
    retry_publisher: PaymentEventPublisher,
    *,
    service_builder: ServiceBuilder = build_service,
    retry_scheduler: RetryScheduler = publish_retry_or_dlq,
) -> None:
    async with session_factory() as session:
        try:
            payment_id = UUID(message["payment_id"])
            service = service_builder(session)
            await service.process_payment(payment_id)
        except ConsumerProcessingError as exc:
            if exc.retryable:
                await session.commit()
                await retry_scheduler(retry_publisher, message, str(exc))
                return

            await session.rollback()
            return
        except Exception as exc:
            await session.rollback()
            await retry_scheduler(retry_publisher, message, str(exc))
            return

        await session.commit()


@broker.subscriber(PAYMENTS_NEW_QUEUE)
async def handle_payment_created(message: dict[str, Any]) -> None:
    await process_message(
        message,
        get_sessionmaker(),
        PaymentEventPublisher(broker),
    )
