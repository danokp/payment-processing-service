from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.payment import PaymentCurrency, PaymentStatus


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: PaymentCurrency
    description: str = Field(min_length=1, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl

    @field_validator("amount")
    @classmethod
    def validate_two_decimal_places(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:
            raise ValueError("amount must have at most 2 decimal places")
        return value


class PaymentCreateResponse(BaseModel):
    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    currency: PaymentCurrency
    description: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
    webhook_sent_at: datetime | None
