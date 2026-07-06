def retry_delay_seconds(attempt: int, cap_seconds: int = 60) -> int:
    return min(2**attempt, cap_seconds)
