from typing import Any

from faststream.rabbit import RabbitBroker

from app.broker.topology import (
    DLQ_ROUTING_KEY,
    PAYMENT_CREATED_ROUTING_KEY,
    PAYMENTS_DLX,
    PAYMENTS_EXCHANGE,
    PAYMENTS_RETRY_EXCHANGE,
    build_retry_routing_keys,
)


class PaymentEventPublisher:
    def __init__(
        self,
        broker: RabbitBroker,
        retry_routing_keys: tuple[str, ...] | None = None,
    ) -> None:
        self.broker = broker
        self.retry_routing_keys = retry_routing_keys or build_retry_routing_keys()

    async def publish_payment_created(self, payload: dict[str, Any]) -> None:
        await self.broker.publish(
            payload,
            exchange=PAYMENTS_EXCHANGE,
            routing_key=PAYMENT_CREATED_ROUTING_KEY,
            persist=True,
        )

    async def publish_processing_retry(
        self, payload: dict[str, Any], retry_count: int
    ) -> None:
        if retry_count < 1 or retry_count > len(self.retry_routing_keys):
            raise ValueError(f"Invalid retry count: {retry_count}")

        await self.broker.publish(
            payload,
            exchange=PAYMENTS_RETRY_EXCHANGE,
            routing_key=self.retry_routing_keys[retry_count - 1],
            headers={"x-retry-count": retry_count},
            persist=True,
        )

    async def publish_processing_dlq(self, payload: dict[str, Any], error: str) -> None:
        await self.broker.publish(
            {**payload, "error": error},
            exchange=PAYMENTS_DLX,
            routing_key=DLQ_ROUTING_KEY,
            persist=True,
        )
