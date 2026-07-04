from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.payment import Payment, PaymentCurrency, PaymentStatus
from app.schemas.payments import PaymentCreate, PaymentRead


def test_amount_accepts_two_decimal_places() -> None:
    payload = PaymentCreate(
        amount=Decimal("99.99"),
        currency="USD",
        description="Invoice",
        metadata={},
        webhook_url="https://example.com/webhook",
    )

    assert payload.amount == Decimal("99.99")


def test_amount_rejects_more_than_two_decimal_places() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(
            amount=Decimal("99.999"),
            currency="USD",
            description="Invoice",
            metadata={},
            webhook_url="https://example.com/webhook",
        )


def test_payment_read_maps_metadata_from_orm_metadata_attribute() -> None:
    payment = Payment(
        id=uuid4(),
        amount=Decimal("99.99"),
        currency=PaymentCurrency.USD,
        description="Invoice",
        metadata_={"order_id": "1"},
        status=PaymentStatus.PENDING,
        idempotency_key="payment-key",
        request_hash="0" * 64,
        webhook_url="https://example.com/webhook",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert PaymentRead.model_validate(payment).metadata == {"order_id": "1"}
