import pytest


@pytest.fixture(scope="session", autouse=True)
def session_setup():
    """Session-level setup fixture."""
    yield
