import httpx

from app.db.models.payment import Payment


class WebhookClient:
    def __init__(
        self,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = client

    async def send_payment_result(self, payment: Payment) -> None:
        payload = {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "amount": str(payment.amount),
            "currency": payment.currency.value,
            "processed_at": payment.processed_at.isoformat()
            if payment.processed_at
            else None,
        }
        if self.client is not None:
            response = await self.client.post(payment.webhook_url, json=payload)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(payment.webhook_url, json=payload)
        response.raise_for_status()
