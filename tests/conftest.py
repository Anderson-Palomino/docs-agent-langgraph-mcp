import pytest

from docs_agent.config import Settings


@pytest.fixture
def settings_factory():
    def make(**overrides) -> Settings:
        return Settings(_env_file=None, **overrides)

    return make
