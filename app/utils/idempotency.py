import hashlib
import json
from decimal import Decimal
from typing import Any

from pydantic import HttpUrl

from app.schemas.payments import PaymentCreate


def normalize_for_hash(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.quantize(Decimal("0.01")), "f")
    if isinstance(value, HttpUrl):
        return str(value)
    if isinstance(value, dict):
        return {key: normalize_for_hash(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [normalize_for_hash(item) for item in value]
    return value


def build_request_hash(payload: PaymentCreate) -> str:
    normalized = normalize_for_hash(payload.model_dump(mode="python"))
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
