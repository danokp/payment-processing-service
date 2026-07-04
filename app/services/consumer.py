from uuid import UUID

from app.core.time import utc_now
from app.models.payment import PaymentStatus


class ConsumerProcessingError(Exception):
    retryable = False


class PaymentNotFoundError(ConsumerProcessingError):
    retryable = False


class InvalidPaymentStateError(ConsumerProcessingError):
    retryable = False


class WebhookDeliveryError(ConsumerProcessingError):
    retryable = True


class PaymentConsumerService:
    def __init__(self, payments, gateway, webhook_client) -> None:
        self.payments = payments
        self.gateway = gateway
        self.webhook_client = webhook_client

    async def process_payment_state(self, payment_id: UUID) -> bool:
        payment = await self.payments.get_by_id_for_update(payment_id)
        if payment is None:
            raise PaymentNotFoundError(str(payment_id))

        if payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}:
            self._validate_terminal_payment(payment)
            return payment.webhook_sent_at is None

        result = await self.gateway.process(payment)
        payment.status = result.status
        payment.processed_at = utc_now()
        payment.last_webhook_error = None
        return True

    async def send_webhook(self, payment_id: UUID) -> None:
        payment = await self.payments.get_by_id_for_update(payment_id)
        if payment is None:
            raise PaymentNotFoundError(str(payment_id))

        if payment.status not in {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}:
            raise InvalidPaymentStateError(
                f"payment {payment.id} is not ready for webhook delivery"
            )

        self._validate_terminal_payment(payment)
        if payment.webhook_sent_at is not None:
            return

        await self._send_webhook(payment)

    def _validate_terminal_payment(self, payment) -> None:
        if payment.processed_at is None:
            raise InvalidPaymentStateError(
                f"terminal payment {payment.id} is missing processed_at"
            )

    async def _send_webhook(self, payment) -> None:
        try:
            await self.webhook_client.send_payment_result(payment)
        except Exception as exc:
            payment.last_webhook_error = str(exc)[:2000]
            raise WebhookDeliveryError(str(exc)) from exc
        payment.webhook_sent_at = utc_now()
        payment.last_webhook_error = None
