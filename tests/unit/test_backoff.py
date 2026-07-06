from app.utils.backoff import retry_delay_seconds


def test_retry_delay_is_exponential() -> None:
    assert retry_delay_seconds(1) == 2
    assert retry_delay_seconds(2) == 4
    assert retry_delay_seconds(3) == 8


def test_retry_delay_is_capped() -> None:
    assert retry_delay_seconds(10) == 60
