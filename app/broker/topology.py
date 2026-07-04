from typing import Any

from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue

PAYMENT_CREATED_ROUTING_KEY = "payments.new"
RETRY_ROUTING_KEYS = ("payments.retry.1", "payments.retry.2", "payments.retry.3")
DLQ_ROUTING_KEY = "payments.new.dlq"

PAYMENTS_EXCHANGE = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)
PAYMENTS_RETRY_EXCHANGE = RabbitExchange("payments.retry", type=ExchangeType.DIRECT, durable=True)
PAYMENTS_DLX = RabbitExchange("payments.dlx", type=ExchangeType.DIRECT, durable=True)

PAYMENTS_NEW_QUEUE = RabbitQueue(
    "payments.new",
    durable=True,
    routing_key=PAYMENT_CREATED_ROUTING_KEY,
)

PAYMENTS_RETRY_1_QUEUE = RabbitQueue(
    "payments.retry.1",
    durable=True,
    routing_key=RETRY_ROUTING_KEYS[0],
    arguments={
        "x-message-ttl": 2000,
        "x-dead-letter-exchange": PAYMENTS_EXCHANGE.name,
        "x-dead-letter-routing-key": PAYMENT_CREATED_ROUTING_KEY,
    },
)
PAYMENTS_RETRY_2_QUEUE = RabbitQueue(
    "payments.retry.2",
    durable=True,
    routing_key=RETRY_ROUTING_KEYS[1],
    arguments={
        "x-message-ttl": 4000,
        "x-dead-letter-exchange": PAYMENTS_EXCHANGE.name,
        "x-dead-letter-routing-key": PAYMENT_CREATED_ROUTING_KEY,
    },
)
PAYMENTS_RETRY_3_QUEUE = RabbitQueue(
    "payments.retry.3",
    durable=True,
    routing_key=RETRY_ROUTING_KEYS[2],
    arguments={
        "x-message-ttl": 8000,
        "x-dead-letter-exchange": PAYMENTS_EXCHANGE.name,
        "x-dead-letter-routing-key": PAYMENT_CREATED_ROUTING_KEY,
    },
)

PAYMENTS_DLQ = RabbitQueue(
    "payments.dlq",
    durable=True,
    routing_key=DLQ_ROUTING_KEY,
)


async def declare_topology(broker: Any) -> None:
    payments_exchange = await broker.declare_exchange(PAYMENTS_EXCHANGE)
    retry_exchange = await broker.declare_exchange(PAYMENTS_RETRY_EXCHANGE)
    dlx_exchange = await broker.declare_exchange(PAYMENTS_DLX)

    payments_new_queue = await broker.declare_queue(PAYMENTS_NEW_QUEUE)
    await payments_new_queue.bind(
        payments_exchange,
        routing_key=PAYMENT_CREATED_ROUTING_KEY,
    )

    retry_1_queue = await broker.declare_queue(PAYMENTS_RETRY_1_QUEUE)
    await retry_1_queue.bind(retry_exchange, routing_key=RETRY_ROUTING_KEYS[0])

    retry_2_queue = await broker.declare_queue(PAYMENTS_RETRY_2_QUEUE)
    await retry_2_queue.bind(retry_exchange, routing_key=RETRY_ROUTING_KEYS[1])

    retry_3_queue = await broker.declare_queue(PAYMENTS_RETRY_3_QUEUE)
    await retry_3_queue.bind(retry_exchange, routing_key=RETRY_ROUTING_KEYS[2])

    dlq = await broker.declare_queue(PAYMENTS_DLQ)
    await dlq.bind(dlx_exchange, routing_key=DLQ_ROUTING_KEY)
