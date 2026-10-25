"""Host doubles are scoped to each source-contract test, never shipped to HA."""

import importlib
import sys

import pytest

from .core_harness import fake_hass, install


@pytest.fixture
def ha(monkeypatch):
    # The integration imports HA classes at module load. Reload after replacing the host.
    for key in list(sys.modules):
        if key.startswith("custom_components.assist_router"):
            monkeypatch.delitem(sys.modules, key)
    host = install(monkeypatch)
    host.hass = fake_hass()
    host.router_module = importlib.import_module("custom_components.assist_router.conversation")
    yield host


@pytest.fixture
def health_data():
    return {
        "kind": "lm_studio",
        "url": "http://127.0.0.1:1234/api/v1/models",
        "model_key": "google/gemma-4-12b-qat",
        "instance_id": "gemma-instance",
    }


@pytest.fixture
def settings_data(health_data):
    return {
        "agents": [
            {"entity_id": "conversation.alpha", "enabled": True, "health": health_data},
            {"entity_id": "conversation.beta", "enabled": True, "health": None},
            {"entity_id": "conversation.gamma", "enabled": True, "health": None},
        ]
    }
