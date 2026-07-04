from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        return await self.session.get(Payment, payment_id)

    async def get_by_id_for_update(self, payment_id: UUID) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def add(self, payment: Payment) -> Payment:
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def add_if_absent(self, payment: Payment) -> bool:
        result = await self.session.execute(
            insert(Payment.__table__)
            .values(
                {
                    "id": payment.id,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "description": payment.description,
                    "metadata": payment.metadata_,
                    "status": payment.status,
                    "idempotency_key": payment.idempotency_key,
                    "request_hash": payment.request_hash,
                    "webhook_url": payment.webhook_url,
                    "created_at": payment.created_at,
                    "processed_at": payment.processed_at,
                    "webhook_sent_at": payment.webhook_sent_at,
                    "last_webhook_error": payment.last_webhook_error,
                }
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(Payment.id)
        )
        return result.scalar_one_or_none() is not None
