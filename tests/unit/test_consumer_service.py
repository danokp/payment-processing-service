from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.time import utc_now
from app.db.models.payment import Payment, PaymentCurrency, PaymentStatus
from app.services.consumer import (
    InvalidPaymentStateError,
    PaymentConsumerService,
    PaymentNotFoundError,
    WebhookDeliveryError,
)
from app.services.gateway import GatewayResult


class FakePayments:
    def __init__(self, payment):
        self.payment = payment
        self.locked_ids = []

    async def get_by_id(self, payment_id):
        return self.payment if self.payment.id == payment_id else None

    async def get_by_id_for_update(self, payment_id):
        self.locked_ids.append(payment_id)
        return self.payment if self.payment.id == payment_id else None


class FakeGateway:
    def __init__(self):
        self.calls = 0

    async def process(self, payment):
        self.calls += 1
        return GatewayResult(status=PaymentStatus.SUCCEEDED)


class FakeWebhook:
    def __init__(self):
        self.calls = 0

    async def send_payment_result(self, payment):
        self.calls += 1


class FailingWebhook:
    def __init__(self):
        self.calls = 0

    async def send_payment_result(self, payment):
        self.calls += 1
        raise RuntimeError("webhook down")


def make_payment(
    status=PaymentStatus.PENDING,
    webhook_sent_at=None,
    processed_at=None,
):
    return Payment(
        id=uuid4(),
        amount=Decimal("10.00"),
        currency=PaymentCurrency.RUB,
        description="Order",
        metadata_={},
        status=status,
        idempotency_key="key",
        request_hash="hash",
        webhook_url="https://example.com/webhook",
        created_at=utc_now(),
        processed_at=processed_at,
        webhook_sent_at=webhook_sent_at,
    )


@pytest.mark.asyncio
async def test_pending_payment_is_processed_and_webhook_is_sent() -> None:
    payment = make_payment()
    payments = FakePayments(payment)
    gateway = FakeGateway()
    webhook = FakeWebhook()
    service = PaymentConsumerService(payments, gateway, webhook)

    needs_webhook = await service.process_payment_state(payment.id)

    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.processed_at is not None
    assert payment.webhook_sent_at is None
    assert gateway.calls == 1
    assert webhook.calls == 0
    assert needs_webhook is True
    assert payments.locked_ids == [payment.id]

    await service.send_webhook(payment.id)

    assert webhook.calls == 1
    assert payment.webhook_sent_at is not None


@pytest.mark.asyncio
async def test_terminal_payment_with_sent_webhook_is_ack_only() -> None:
    payment = make_payment(
        PaymentStatus.SUCCEEDED,
        webhook_sent_at=utc_now(),
        processed_at=utc_now(),
    )
    gateway = FakeGateway()
    webhook = FakeWebhook()
    service = PaymentConsumerService(FakePayments(payment), gateway, webhook)

    needs_webhook = await service.process_payment_state(payment.id)

    assert gateway.calls == 0
    assert webhook.calls == 0
    assert needs_webhook is False


@pytest.mark.asyncio
async def test_terminal_payment_without_webhook_sends_webhook_only() -> None:
    payment = make_payment(PaymentStatus.SUCCEEDED, processed_at=utc_now())
    gateway = FakeGateway()
    webhook = FakeWebhook()
    service = PaymentConsumerService(FakePayments(payment), gateway, webhook)

    needs_webhook = await service.process_payment_state(payment.id)

    assert gateway.calls == 0
    assert webhook.calls == 0
    assert needs_webhook is True

    await service.send_webhook(payment.id)

    assert webhook.calls == 1
    assert payment.webhook_sent_at is not None


@pytest.mark.asyncio
async def test_webhook_failure_is_recorded_and_reraised_for_retry() -> None:
    payment = make_payment()
    gateway = FakeGateway()
    webhook = FailingWebhook()
    service = PaymentConsumerService(FakePayments(payment), gateway, webhook)

    needs_webhook = await service.process_payment_state(payment.id)

    assert needs_webhook is True
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.processed_at is not None
    assert payment.last_webhook_error is None
    assert payment.webhook_sent_at is None
    assert gateway.calls == 1
    assert webhook.calls == 0

    with pytest.raises(WebhookDeliveryError, match="webhook down"):
        await service.send_webhook(payment.id)

    assert webhook.calls == 1


@pytest.mark.asyncio
async def test_missing_payment_is_non_retryable() -> None:
    payment = make_payment()
    service = PaymentConsumerService(FakePayments(payment), FakeGateway(), FakeWebhook())

    with pytest.raises(PaymentNotFoundError) as exc_info:
        await service.process_payment_state(uuid4())

    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_terminal_payment_without_processed_at_is_invalid_state() -> None:
    payment = make_payment(PaymentStatus.SUCCEEDED)
    gateway = FakeGateway()
    webhook = FakeWebhook()
    service = PaymentConsumerService(FakePayments(payment), gateway, webhook)

    with pytest.raises(InvalidPaymentStateError) as exc_info:
        await service.process_payment_state(payment.id)

    assert exc_info.value.retryable is False
    assert gateway.calls == 0
    assert webhook.calls == 0
    assert payment.webhook_sent_at is None
