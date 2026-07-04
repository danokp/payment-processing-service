# Async Payment Processing Service

FastAPI service for accepting payment requests, processing them asynchronously, and delivering webhook notifications.

## Requirements

- Docker and Docker Compose
- uv
- make

## Start

```sh
make up
make up-d
make migrate
make makemigrations name="describe schema change"
make test
make lint
make format
make down
make clean
```

The API listens on `http://localhost:8000` when started with Docker Compose.

## API

Create a payment:

```sh
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: dev-api-key" \
  -H "Idempotency-Key: order-1001-payment" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "10.00",
    "currency": "RUB",
    "description": "Order 1001",
    "metadata": {
      "order_id": "1001"
    },
    "webhook_url": "http://demo-webhook:9000/webhook"
  }'
```

Get a payment:

```sh
curl http://localhost:8000/api/v1/payments/<payment_id> \
  -H "X-API-Key: dev-api-key"
```

## Demo Webhook

Start the API, workers, and demo webhook receiver:

```sh
make demo-up
```

For the Docker demo, use the Docker-internal webhook URL `http://demo-webhook:9000/webhook`.

## RabbitMQ

RabbitMQ Management UI is available at `http://localhost:15672` with `guest` / `guest`.

Relevant queues:

- `payments.new`
- Retry queues `payments.retry.1`, `payments.retry.2`, and `payments.retry.3`
- DLQ queue `payments.dlq`, bound with routing key `payments.new.dlq`

## Design Trade-offs

- Webhooks are unsigned in the base implementation.
- Webhook retry state is tracked on payments with `webhook_sent_at` and `last_webhook_error`.
- A separate webhook delivery ledger is a possible extension.
- Payment gateway behavior is random in production and deterministic in tests through dependency injection.
