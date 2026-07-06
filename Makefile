.PHONY: setup up up-d makemigrations migrate test lint format logs down clean demo-up demo-logs

name ?= migration
PYTHON_VERSION ?= 3.12
COMPOSE := docker compose
DEMO_COMPOSE := docker compose -f docker-compose.yml -f docker-compose.demo.yml
RUFF_CACHE_DIR := /tmp/nebus-payment-processing-ruff-cache

setup:
	uv python install $(PYTHON_VERSION)
	uv sync --locked --python $(PYTHON_VERSION)

up: migrate
	$(COMPOSE) up --build

up-d: migrate
	$(COMPOSE) up --build -d

makemigrations:
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=/tmp/nebus-payment-processing-dev-venv uv run alembic revision --autogenerate -m "$(name)"

migrate:
	$(COMPOSE) up -d --wait postgres
	$(COMPOSE) run --rm --no-deps --build api alembic upgrade head

test:
	$(COMPOSE) up -d --wait postgres
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=/tmp/nebus-payment-processing-dev-venv PYTHONDONTWRITEBYTECODE=1 uv run pytest -v -p no:cacheprovider

lint:
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=/tmp/nebus-payment-processing-dev-venv RUFF_CACHE_DIR=$(RUFF_CACHE_DIR) uv run ruff check .

format:
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=/tmp/nebus-payment-processing-dev-venv RUFF_CACHE_DIR=$(RUFF_CACHE_DIR) uv run ruff format .

logs:
	$(COMPOSE) logs -f

down:
	$(DEMO_COMPOSE) down --remove-orphans

clean:
	$(DEMO_COMPOSE) down --volumes --remove-orphans

demo-up: migrate
	$(DEMO_COMPOSE) up --build

demo-logs:
	$(DEMO_COMPOSE) logs -f
