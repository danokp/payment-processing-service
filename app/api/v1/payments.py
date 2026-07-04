from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_payment_service, require_api_key
from app.db.session import get_session
from app.schemas.payments import PaymentCreate, PaymentCreateResponse, PaymentRead
from app.services.payments import IdempotencyConflictError, PaymentService

router = APIRouter(
    prefix="/api/v1/payments",
    tags=["payments"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PaymentCreateResponse,
)
async def create_payment(
    payload: PaymentCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    service: Annotated[PaymentService, Depends(get_payment_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentCreateResponse:
    try:
        payment = await service.create_payment(payload, idempotency_key)
        await session.commit()
    except IdempotencyConflictError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was used with another request",
        ) from exc

    return PaymentCreateResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment(
    payment_id: UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentRead:
    payment = await service.get_payment(payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found"
        )

    return PaymentRead.model_validate(payment)
