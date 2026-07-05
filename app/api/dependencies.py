from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.repositories.outbox import OutboxRepository
from app.repositories.payments import PaymentRepository
from app.services.payments import PaymentService


def get_api_key_settings() -> Settings:
    return get_settings()


async def require_api_key(
    settings: Annotated[Settings, Depends(get_api_key_settings)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )


def get_payment_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentService:
    return PaymentService(PaymentRepository(session), OutboxRepository(session), session)
