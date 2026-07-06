from typing import Protocol
from uuid import UUID

from uuid6 import uuid7

from app.core.time import utc_now
from app.db.models.payment import Payment, PaymentStatus
from app.schemas.payments import PaymentCreate
from app.utils.idempotency import build_request_hash


class PaymentWriter(Protocol):
    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        raise NotImplementedError

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        raise NotImplementedError

    async def add_if_absent(self, payment: Payment) -> bool:
        raise NotImplementedError


class OutboxWriter(Protocol):
    async def add_payment_created(self, payment_id: UUID) -> object:
        raise NotImplementedError


class TransactionSession(Protocol):
    async def commit(self) -> None:
        raise NotImplementedError

    async def rollback(self) -> None:
        raise NotImplementedError


class IdempotencyConflictError(Exception):
    pass


class PaymentService:
    def __init__(
        self,
        payments: PaymentWriter,
        outbox: OutboxWriter,
        session: TransactionSession,
    ) -> None:
        self.payments = payments
        self.outbox = outbox
        self.session = session

    async def create_payment(self, payload: PaymentCreate, idempotency_key: str) -> Payment:
        try:
            payment = await self._create_payment(payload, idempotency_key)
            await self.session.commit()
            return payment
        except Exception:
            await self.session.rollback()
            raise

    async def _create_payment(
        self, payload: PaymentCreate, idempotency_key: str
    ) -> Payment:
        request_hash = build_request_hash(payload)
        existing = await self.payments.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflictError(
                    "idempotency key was used with another request"
                )
            return existing

        payment = Payment(
            id=uuid7(),
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            metadata_=payload.metadata,
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            webhook_url=str(payload.webhook_url),
            created_at=utc_now(),
        )
        inserted = await self.payments.add_if_absent(payment)
        if inserted:
            await self.outbox.add_payment_created(payment.id)
            return payment

        existing = await self.payments.get_by_idempotency_key(idempotency_key)
        if existing is None:
            raise RuntimeError("idempotency conflict row was not found")
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError("idempotency key was used with another request")
        return existing

    async def get_payment(self, payment_id: UUID) -> Payment | None:
        return await self.payments.get_by_id(payment_id)
