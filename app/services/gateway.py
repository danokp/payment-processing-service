import asyncio
import random
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.models.payment import Payment, PaymentStatus


@dataclass(frozen=True)
class GatewayResult:
    status: PaymentStatus


class PaymentGateway(Protocol):
    async def process(self, payment: Payment) -> GatewayResult:
        raise NotImplementedError


class RandomPaymentGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def process(self, payment: Payment) -> GatewayResult:
        delay = random.uniform(
            self.settings.payment_gateway_min_delay_seconds,
            self.settings.payment_gateway_max_delay_seconds,
        )
        await asyncio.sleep(delay)
        status = (
            PaymentStatus.SUCCEEDED
            if random.random() < self.settings.payment_gateway_success_rate
            else PaymentStatus.FAILED
        )
        return GatewayResult(status=status)


class FakePaymentGateway:
    def __init__(self, status: PaymentStatus = PaymentStatus.SUCCEEDED) -> None:
        self.status = status

    async def process(self, payment: Payment) -> GatewayResult:
        return GatewayResult(status=self.status)
