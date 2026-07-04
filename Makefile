.PHONY: makemigrations migrate test lint format

name ?= migration

makemigrations:
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=/tmp/nebus-payment-processing-dev-venv uv run alembic revision --autogenerate -m "$(name)"

migrate:
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=/tmp/nebus-payment-processing-dev-venv uv run alembic upgrade head

test:
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=/tmp/nebus-payment-processing-dev-venv PYTHONDONTWRITEBYTECODE=1 uv run pytest -v -p no:cacheprovider

lint:
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=/tmp/nebus-payment-processing-dev-venv uv run ruff check .

format:
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT=/tmp/nebus-payment-processing-dev-venv uv run ruff format .
