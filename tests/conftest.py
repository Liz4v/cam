import pytest


@pytest.fixture(scope="session", autouse=True)
def close_cache_db_at_end():
    """No teardown required; DB connections are short-lived."""
    yield
