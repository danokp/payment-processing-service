from app.core.config import Settings


def test_settings_accept_required_values() -> None:
    settings = Settings(
        api_key="secret",
        database_url="postgresql+asyncpg://u:p@localhost:5432/db",
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
    )

    assert settings.api_key == "secret"
    assert settings.outbox_batch_size == 50
