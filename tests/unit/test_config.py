from app.core.config import Settings


def test_settings_accept_required_values() -> None:
    settings = Settings(
        API_KEY="secret",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        RABBITMQ_URL="amqp://guest:guest@localhost:5672/",
    )

    assert settings.API_KEY == "secret"
    assert settings.OUTBOX_BATCH_SIZE == 50
    assert settings.DEFAULT_OUTBOX_MAX_ATTEMPTS == 3
    assert settings.DEFAULT_OUTBOX_RETRY_CAP_SECONDS == 60
    assert settings.DEFAULT_PAYMENT_PROCESSING_RETRY_DELAYS_SECONDS == (2, 4, 8)
