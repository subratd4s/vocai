"""All automated tests are offline, even when the developer has credentials."""

import httpx
import pytest


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("MAX_INPUT_CHARACTERS", raising=False)

    def block_network(*args, **kwargs):
        raise AssertionError("Live HTTP is forbidden in automated tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", block_network)
