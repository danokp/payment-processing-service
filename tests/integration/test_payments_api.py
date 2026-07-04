from uuid import uuid4

from httpx import AsyncClient


async def test_create_payment_requires_api_key(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments",
        headers={"Idempotency-Key": "key-1"},
        json={
            "amount": "10.00",
            "currency": "RUB",
            "description": "Order",
            "metadata": {},
            "webhook_url": "https://example.com/webhook",
        },
    )

    assert response.status_code == 401


async def test_create_payment_returns_accepted(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments",
        headers={"X-API-Key": "test-key", "Idempotency-Key": "key-1"},
        json={
            "amount": "10.00",
            "currency": "RUB",
            "description": "Order",
            "metadata": {"order_id": "1"},
            "webhook_url": "https://example.com/webhook",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert "payment_id" in body
    assert "created_at" in body


async def test_repeated_key_with_different_body_returns_conflict(
    client: AsyncClient,
) -> None:
    headers = {"X-API-Key": "test-key", "Idempotency-Key": "key-conflict"}
    base = {
        "amount": "10.00",
        "currency": "RUB",
        "description": "Order",
        "metadata": {},
        "webhook_url": "https://example.com/webhook",
    }
    await client.post("/api/v1/payments", headers=headers, json=base)

    changed = {**base, "amount": "11.00"}
    response = await client.post("/api/v1/payments", headers=headers, json=changed)

    assert response.status_code == 409


async def test_repeated_same_key_and_body_returns_same_payment_id(
    client: AsyncClient,
) -> None:
    headers = {"X-API-Key": "test-key", "Idempotency-Key": "key-repeat"}
    payload = {
        "amount": "10.00",
        "currency": "RUB",
        "description": "Order",
        "metadata": {"order_id": "1"},
        "webhook_url": "https://example.com/webhook",
    }

    first = await client.post("/api/v1/payments", headers=headers, json=payload)
    second = await client.post("/api/v1/payments", headers=headers, json=payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["payment_id"] == first.json()["payment_id"]


async def test_get_payment_returns_full_payment_data(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/payments",
        headers={"X-API-Key": "test-key", "Idempotency-Key": "key-get"},
        json={
            "amount": "10.00",
            "currency": "RUB",
            "description": "Order",
            "metadata": {"order_id": "1"},
            "webhook_url": "https://example.com/webhook",
        },
    )
    payment_id = create_response.json()["payment_id"]

    response = await client.get(
        f"/api/v1/payments/{payment_id}", headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == payment_id
    assert body["amount"] == "10.00"
    assert body["currency"] == "RUB"
    assert body["description"] == "Order"
    assert body["metadata"] == {"order_id": "1"}
    assert body["status"] == "pending"
    assert body["idempotency_key"] == "key-get"
    assert body["webhook_url"] == "https://example.com/webhook"
    assert body["processed_at"] is None
    assert body["webhook_sent_at"] is None


async def test_get_unknown_payment_returns_not_found(client: AsyncClient) -> None:
    response = await client.get(
        f"/api/v1/payments/{uuid4()}", headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 404
