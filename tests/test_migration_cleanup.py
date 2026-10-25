"""No guessed legacy host; explicit destinations and current options stay intact."""

from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def legacy_data():
    return {"model_key": "model/exact", "instance_id": "instance-a", "token": "test-token"}


@pytest.mark.parametrize("value", [None, "", "not-an-endpoint", "file:///models"])
async def test_missing_or_invalid_legacy_url_rejects_atomically(ha, value):
    module = import_module("custom_components.assist_router")
    data = legacy_data()
    if value is not None:
        data["models_url"] = value
    entry = SimpleNamespace(version=1, data=data, options={})
    before = deepcopy(vars(entry))
    update = Mock()
    ha.hass.config_entries = SimpleNamespace(async_update_entry=update)
    assert not await module.async_migrate_entry(ha.hass, entry)
    update.assert_not_called()
    assert vars(entry) == before


@pytest.mark.parametrize("source", ["data", "options"])
async def test_explicit_legacy_url_and_credentials_preserved_without_network(ha, source):
    module = import_module("custom_components.assist_router")
    # Synthetic private host proves existing LAN configurations remain supported.
    host = ".".join(("192", "168", "42", "42"))
    url = f"https://{host}:1234/proxy/api/v1/models"
    data = legacy_data()
    data.update(health_timeout=0.7, cache_seconds=3, failure_cache_seconds=9)
    options = {}
    (data if source == "data" else options)["models_url"] = url
    entry = SimpleNamespace(version=1, data=data, options=options)
    before = deepcopy(vars(entry))
    update = Mock()
    ha.hass.config_entries = SimpleNamespace(async_update_entry=update)
    assert await module.async_migrate_entry(ha.hass, entry)
    update.assert_called_once()
    saved = update.call_args.kwargs["options"]
    health = saved["agents"][0]["health"]
    assert health["url"] == url and health["token"] == data["token"]
    assert health["model_key"] == data["model_key"] and health["instance_id"] == data["instance_id"]
    assert health["timeout"] == 0.7 and health["cache_seconds"] == 3 and health["failure_cache_seconds"] == 9
    assert health["auth_type"] == "bearer" and not saved["prompt"]["enabled"]
    assert vars(entry) == before  # Only HA's atomic update API receives the result.


async def test_invalid_url_option_does_not_fall_back_to_data(ha):
    module = import_module("custom_components.assist_router")
    entry = SimpleNamespace(
        version=1,
        data=legacy_data() | {"models_url": "https://models.example/api/v1/models"},
        options={"models_url": None},
    )
    update = Mock()
    ha.hass.config_entries = SimpleNamespace(async_update_entry=update)
    assert not await module.async_migrate_entry(ha.hass, entry)
    update.assert_not_called()


@pytest.mark.parametrize("storage", ["data", "options"])
async def test_current_configuration_and_prompt_fingerprints_untouched(ha, settings_data, storage):
    module = import_module("custom_components.assist_router")
    from custom_components.assist_router.prompts import PromptManager, fingerprint
    from custom_components.assist_router.settings import Settings

    config = deepcopy(settings_data)
    config["agents"].reverse()
    config["agents"][0]["prompt_addition"] = "Ergänzung: Café e\u0301"
    config["agents"][1]["enabled"] = False
    config["prompt"] = {
        "enabled": True,
        "text": "Gemeinsam: ä ö ü é\nZeile 2",
        "reviews": {route["entity_id"]: "a" * 64 for route in config["agents"]},
    }
    config = Settings.from_mapping(config).as_dict()
    entry = SimpleNamespace(version=3, minor_version=1, data={}, options={})
    setattr(entry, storage, config)
    before = deepcopy(vars(entry))
    digest = fingerprint(config)
    revision = PromptManager(Settings.from_mapping(config)).revision
    update = Mock()
    ha.hass.config_entries = SimpleNamespace(async_update_entry=update)
    assert await module.async_migrate_entry(ha.hass, entry)
    update.assert_not_called()
    assert vars(entry) == before and getattr(entry, storage) is config
    assert fingerprint(config) == digest
    assert PromptManager(Settings.from_mapping(config)).revision == revision


async def test_schema_two_keeps_order_health_and_disabled_agents(ha, settings_data):
    module = import_module("custom_components.assist_router")
    from custom_components.assist_router.settings import Settings

    config = deepcopy(settings_data)
    config["agents"].reverse()
    config["agents"][0]["enabled"] = False
    entry = SimpleNamespace(version=2, data={}, options=config)
    update = Mock()
    ha.hass.config_entries = SimpleNamespace(async_update_entry=update)
    assert await module.async_migrate_entry(ha.hass, entry)
    saved = update.call_args.kwargs["options"]
    assert [route["entity_id"] for route in saved["agents"]] == [
        route["entity_id"] for route in config["agents"]
    ]
    assert [route["enabled"] for route in saved["agents"]] == [route["enabled"] for route in config["agents"]]
    assert saved["agents"][-1]["health"]["url"] == config["agents"][-1]["health"]["url"]
    assert saved["agents"] == Settings.from_mapping(config).as_dict()["agents"]
    assert not saved["prompt"]["enabled"]
