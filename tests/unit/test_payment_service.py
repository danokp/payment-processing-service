from decimal import Decimal

import pytest

from app.models.payment import PaymentStatus
from app.schemas.payments import PaymentCreate
from app.services.payments import IdempotencyConflictError, PaymentService


class FakePaymentRepository:
    def __init__(self) -> None:
        self.by_key = {}
        self.conflicts_with = None
        self.saved = []

    async def get_by_idempotency_key(self, key: str):
        return self.by_key.get(key)

    async def add_if_absent(self, payment):
        if self.conflicts_with is not None:
            self.by_key[payment.idempotency_key] = self.conflicts_with
            return False

        self.saved.append(payment)
        self.by_key[payment.idempotency_key] = payment
        return True


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.saved = []

    async def add_payment_created(self, payment_id):
        self.saved.append(payment_id)


def payload(amount: str = "10.00") -> PaymentCreate:
    return PaymentCreate(
        amount=Decimal(amount),
        currency="RUB",
        description="Order",
        metadata={},
        webhook_url="https://example.com/webhook",
    )


@pytest.mark.asyncio
async def test_create_payment_writes_payment_and_outbox_event() -> None:
    payments = FakePaymentRepository()
    outbox = FakeOutboxRepository()
    service = PaymentService(payments, outbox)

    payment = await service.create_payment(payload(), "key-1")

    assert payment.status == PaymentStatus.PENDING
    assert payments.saved == [payment]
    assert outbox.saved == [payment.id]


@pytest.mark.asyncio
async def test_repeated_same_key_and_same_body_returns_existing_payment() -> None:
    payments = FakePaymentRepository()
    outbox = FakeOutboxRepository()
    service = PaymentService(payments, outbox)

    first = await service.create_payment(payload(), "key-1")
    second = await service.create_payment(payload(), "key-1")

    assert second is first
    assert outbox.saved == [first.id]


@pytest.mark.asyncio
async def test_repeated_same_key_and_different_body_raises_conflict() -> None:
    payments = FakePaymentRepository()
    outbox = FakeOutboxRepository()
    service = PaymentService(payments, outbox)

    await service.create_payment(payload("10.00"), "key-1")

    with pytest.raises(IdempotencyConflictError):
        await service.create_payment(payload("11.00"), "key-1")


@pytest.mark.asyncio
async def test_collision_after_initial_miss_returns_existing_payment() -> None:
    payments = FakePaymentRepository()
    outbox = FakeOutboxRepository()
    service = PaymentService(payments, outbox)

    existing = await service.create_payment(payload(), "key-1")
    payments.by_key = {}
    payments.conflicts_with = existing
    outbox.saved.clear()

    payment = await service.create_payment(payload(), "key-1")

    assert payment is existing
    assert outbox.saved == []


@pytest.mark.asyncio
async def test_collision_after_initial_miss_with_different_body_raises_conflict() -> None:
    payments = FakePaymentRepository()
    outbox = FakeOutboxRepository()
    service = PaymentService(payments, outbox)

    existing = await service.create_payment(payload("10.00"), "key-1")
    payments.by_key = {}
    payments.conflicts_with = existing
    outbox.saved.clear()

    with pytest.raises(IdempotencyConflictError):
        await service.create_payment(payload("11.00"), "key-1")

    assert outbox.saved == []
