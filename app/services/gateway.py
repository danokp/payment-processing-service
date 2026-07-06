import asyncio
import random
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.db.models.payment import Payment, PaymentStatus


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
            self.settings.PAYMENT_GATEWAY_MIN_DELAY_SECONDS,
            self.settings.PAYMENT_GATEWAY_MAX_DELAY_SECONDS,
        )
        await asyncio.sleep(delay)
        status = (
            PaymentStatus.SUCCEEDED
            if random.random() < self.settings.PAYMENT_GATEWAY_SUCCESS_RATE
            else PaymentStatus.FAILED
        )
        return GatewayResult(status=status)


class FakePaymentGateway:
    def __init__(self, status: PaymentStatus = PaymentStatus.SUCCEEDED) -> None:
        self.status = status

    async def process(self, payment: Payment) -> GatewayResult:
        return GatewayResult(status=self.status)
