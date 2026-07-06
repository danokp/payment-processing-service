from typing import Any

from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue
from faststream.rabbit.schemas.queue import ClassicQueueArgs

from app.core.config import Settings, get_settings

PAYMENT_CREATED_ROUTING_KEY = "payments.new"
DLQ_ROUTING_KEY = "payments.new.dlq"

PAYMENTS_EXCHANGE = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)
PAYMENTS_RETRY_EXCHANGE = RabbitExchange("payments.retry", type=ExchangeType.DIRECT, durable=True)
PAYMENTS_DLX = RabbitExchange("payments.dlx", type=ExchangeType.DIRECT, durable=True)

PAYMENTS_NEW_QUEUE = RabbitQueue(
    "payments.new",
    durable=True,
    routing_key=PAYMENT_CREATED_ROUTING_KEY,
)

PAYMENTS_DLQ = RabbitQueue(
    "payments.dlq",
    durable=True,
    routing_key=DLQ_ROUTING_KEY,
)


def build_retry_routing_keys(settings: Settings | None = None) -> tuple[str, ...]:
    settings = settings or get_settings()
    retry_delays = settings.DEFAULT_PAYMENT_PROCESSING_RETRY_DELAYS_SECONDS
    return tuple(
        f"payments.retry.{attempt}"
        for attempt in range(1, len(retry_delays) + 1)
    )


def build_retry_queues(settings: Settings | None = None) -> tuple[RabbitQueue, ...]:
    settings = settings or get_settings()
    retry_delays = settings.DEFAULT_PAYMENT_PROCESSING_RETRY_DELAYS_SECONDS
    routing_keys = build_retry_routing_keys(settings)
    return tuple(
        RabbitQueue(
            routing_key,
            durable=True,
            routing_key=routing_key,
            arguments=retry_queue_arguments(delay_seconds),
        )
        for routing_key, delay_seconds in zip(
            routing_keys,
            retry_delays,
            strict=True,
        )
    )


def retry_queue_arguments(delay_seconds: int) -> ClassicQueueArgs:
    return {
        "x-message-ttl": delay_seconds * 1000,
        "x-dead-letter-exchange": PAYMENTS_EXCHANGE.name,
        "x-dead-letter-routing-key": PAYMENT_CREATED_ROUTING_KEY,
    }


async def declare_topology(broker: Any, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    retry_routing_keys = build_retry_routing_keys(settings)
    retry_queues = build_retry_queues(settings)

    payments_exchange = await broker.declare_exchange(PAYMENTS_EXCHANGE)
    retry_exchange = await broker.declare_exchange(PAYMENTS_RETRY_EXCHANGE)
    dlx_exchange = await broker.declare_exchange(PAYMENTS_DLX)

    payments_new_queue = await broker.declare_queue(PAYMENTS_NEW_QUEUE)
    await payments_new_queue.bind(
        payments_exchange,
        routing_key=PAYMENT_CREATED_ROUTING_KEY,
    )

    for retry_queue, routing_key in zip(retry_queues, retry_routing_keys, strict=True):
        declared_retry_queue = await broker.declare_queue(retry_queue)
        await declared_retry_queue.bind(retry_exchange, routing_key=routing_key)

    dlq = await broker.declare_queue(PAYMENTS_DLQ)
    await dlq.bind(dlx_exchange, routing_key=DLQ_ROUTING_KEY)
