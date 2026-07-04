from decimal import Decimal

from app.schemas.payments import PaymentCreate
from app.services.idempotency import build_request_hash


def test_request_hash_is_stable_for_equivalent_payloads() -> None:
    first = PaymentCreate(
        amount=Decimal("10.00"),
        currency="RUB",
        description="Order",
        metadata={"b": 2, "a": 1},
        webhook_url="https://example.com/webhook",
    )
    second = PaymentCreate(
        amount=Decimal("10.0"),
        currency="RUB",
        description="Order",
        metadata={"a": 1, "b": 2},
        webhook_url="https://example.com/webhook",
    )

    assert build_request_hash(first) == build_request_hash(second)


def test_request_hash_changes_when_amount_changes() -> None:
    first = PaymentCreate(
        amount=Decimal("10.00"),
        currency="RUB",
        description="Order",
        metadata={},
        webhook_url="https://example.com/webhook",
    )
    second = PaymentCreate(
        amount=Decimal("11.00"),
        currency="RUB",
        description="Order",
        metadata={},
        webhook_url="https://example.com/webhook",
    )

    assert build_request_hash(first) != build_request_hash(second)
