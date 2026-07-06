# Async Payment Processing Service

FastAPI service for accepting payment requests, processing them asynchronously, and delivering webhook notifications.

## Requirements

- Docker and Docker Compose
- uv
- make

## Start

Prepare a local uv environment for development on a new machine:

```sh
make setup
```

This installs Python 3.12 for uv if needed and syncs dependencies from `uv.lock`.
It is not required before `make up`: Docker Compose builds the application image
with Python 3.12 and installs production dependencies inside the container.

Start the full stack in the foreground:

```sh
make up
```

Detached mode:

```sh
make up-d
```

Apply migrations manually:

```sh
make migrate
```

Stop services:

```sh
make down
```

Clean containers and volumes:

```sh
make clean
```

The API listens on `http://localhost:8000` when started with Docker Compose.

## Local Development

Prepare or refresh the local uv environment:

```sh
make setup
```

Generate a migration after model changes:

```sh
make makemigrations name="describe schema change"
```

Run tests:

```sh
make test
```

Run lint:

```sh
make lint
```

Format code:

```sh
make format
```

## Demo Webhook

Start the API, workers, and demo webhook receiver:

```sh
make demo-up
```

Use the Docker-internal webhook URL `http://demo-webhook:9000/webhook` in payment requests.

Follow demo logs:

```sh
make demo-logs
```

## API

Create a payment after starting the demo stack:

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

## RabbitMQ

RabbitMQ Management UI is available at `http://localhost:15672` with `guest` / `guest`.

Relevant queues:

- `payments.new`
- Retry queues `payments.retry.1`, `payments.retry.2`, and `payments.retry.3`
- DLQ queue `payments.dlq`, bound with routing key `payments.new.dlq`
