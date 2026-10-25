"""UI drafts, ordered entities, independent credentials and version migration."""

import sys
from collections.abc import Sequence
from copy import deepcopy
from enum import StrEnum
from importlib import import_module
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import probatio as vol
import pytest

from .core_harness import source_nodes


def flow_module(ha, monkeypatch):
    class Base:
        def __init_subclass__(cls, **kwargs):
            pass

        def _async_current_entries(self):
            return []

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_show_menu(self, **kwargs):
            return {"type": "menu", **kwargs}

        def async_abort(self, **kwargs):
            return {"type": "abort", **kwargs}

    entries = ModuleType("homeassistant.config_entries")
    menu_namespace = {
        "__name__": __name__,
        "probatio": vol,
        "callback": lambda function: function,
        "FlowResultType": SimpleNamespace(MENU="menu"),
    }
    source_nodes("homeassistant/data_entry_flow.py", ["async_show_menu"], menu_namespace)
    Base.async_show_menu = menu_namespace["async_show_menu"]
    Base._flow_result = dict
    Base.flow_id = "test-flow"
    Base.handler = "assist_router"
    entries.ConfigFlow = entries.OptionsFlow = Base
    monkeypatch.setitem(sys.modules, entries.__name__, entries)
    monkeypatch.setattr(sys.modules["homeassistant"], "config_entries", entries, raising=False)
    registry = ModuleType("homeassistant.helpers.entity_registry")
    registry.async_get = lambda hass: SimpleNamespace(
        entities=getattr(hass, "registry_entries", {}),
        async_get=lambda entity_id: getattr(hass, "registry_entries", {}).get(entity_id),
    )
    monkeypatch.setitem(sys.modules, registry.__name__, registry)
    monkeypatch.setattr(sys.modules["homeassistant.helpers"], "entity_registry", registry, raising=False)
    selector = ModuleType("homeassistant.helpers.selector")
    selector.TextSelector = lambda *args: str
    selector.TextSelectorConfig = dict
    selector.TextSelectorType = SimpleNamespace(PASSWORD="password")
    selector.BooleanSelector = lambda: bool
    selector.EntitySelectorConfig = selector.SelectSelectorConfig = dict

    # Run HA's exact EntitySelector/SelectSelector and their schemas with a small
    # selector base and domain/filter validation doubles, not a selector reimplementation.
    class SelectorBase:
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, config=None):
            self.config = self.CONFIG_SCHEMA(config)

    class Registry:
        def register(self, key):
            return lambda cls: cls

    selector.__dict__.update(
        probatio=vol,
        Selector=SelectorBase,
        SELECTORS=Registry(),
        _LEGACY_ENTITY_SELECTOR_CONFIG_SCHEMA_DICT={},
        ENTITY_WITH_DEVICE_FILTER_SELECTOR_CONFIG_SCHEMA=vol.Schema({"domain": vol.Any(str, [str])}),
        cv=SimpleNamespace(boolean=bool, string=str, entity_id_or_uuid=str),
        valid_entity_id=lambda value: "." in value,
        split_entity_id=lambda value: value.split(".", 1),
        select_option=vol.Schema({vol.Required("value"): str, vol.Required("label"): str}),
        SelectSelectorMode=str,
        StrEnum=StrEnum,
        cast=lambda kind, value: value,
        override=lambda function: function,
        Sequence=Sequence,
    )
    source_nodes(
        "homeassistant/helpers/selector.py",
        [
            "make_selector_config_schema",
            "_validate_selector_reorder_config",
            "EntitySelector",
            "SelectSelector",
            "TextSelectorType",
            "TextSelector",
        ],
        selector.__dict__,
    )
    monkeypatch.setitem(sys.modules, selector.__name__, selector)
    monkeypatch.setattr(sys.modules["homeassistant.helpers"], "selector", selector, raising=False)
    module = import_module("custom_components.assist_router.config_flow")
    return module


def new_flow(ha, monkeypatch):
    module = flow_module(ha, monkeypatch)
    flow = module.ConfigFlow()
    flow.hass = ha.hass
    return module, flow


async def test_offline_setup_ordered_selector_and_single_agent(ha, monkeypatch):
    module, flow = new_flow(ha, monkeypatch)
    form = await flow.async_step_user()
    validator = next(iter(form["data_schema"].schema.values()))
    assert validator.config["reorder"] and validator.config["multiple"]
    assert validator.config["filter"] == [{"domain": "conversation"}]
    result = await flow.async_step_order(form["data_schema"]({"agent_order": ["conversation.any_agent"]}))
    assert result["type"] == "menu"
    saved = await flow.async_step_finish()
    assert saved["data"] == {} and saved["options"]["agents"][0]["entity_id"] == "conversation.any_agent"
    assert len(saved["options"]["agents"]) == 1
    assert saved["options"]["agents"][0]["health"] is None
    flow._async_current_entries = lambda: [object()]
    assert (await flow.async_step_user())["reason"] == "single_instance_allowed"
    assert module.ConfigFlow.VERSION == 3


async def test_sort_add_remove_enable_and_position_preserve_health(ha, monkeypatch, health_data):
    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": [f"conversation.agent_{i}" for i in range(6)]})
    assert (await flow.async_step_health_agent({"entity_id": "conversation.agent_2"}))[
        "step_id"
    ] == "health_type"
    await flow.async_step_health_type({"kind": "lm_studio"})
    await flow.async_step_health(health_data | {"token": "secret", "auth_type": "bearer"})
    await flow.async_step_enabled({"enabled_agents": ["conversation.agent_0", "conversation.agent_2"]})
    await flow.async_step_order(
        {"agent_order": ["conversation.agent_2", "conversation.agent_0", "conversation.new"]}
    )
    assert flow._draft["agents"][0]["health"]["token"] == "secret"
    assert flow._draft["agents"][2]["enabled"]  # new agents default to enabled
    await flow.async_step_position({"entity_id": "conversation.agent_2", "position": 3})
    result = await flow.async_step_finish()
    assert [item["entity_id"] for item in result["options"]["agents"]] == [
        "conversation.agent_0",
        "conversation.new",
        "conversation.agent_2",
    ]
    assert result["options"]["agents"][2]["health"]["model_key"] == health_data["model_key"]
    assert len(result["options"]["agents"]) == 3


async def test_cannot_save_or_remove_last_active_agent(ha, monkeypatch):
    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": ["conversation.a", "conversation.b"]})
    await flow.async_step_enabled({"enabled_agents": ["conversation.a"]})
    before = deepcopy(flow._draft)
    error = await flow.async_step_enabled({"enabled_agents": []})
    assert error["errors"]["base"] == "no_active_agents" and flow._draft == before
    error = await flow.async_step_order({"agent_order": ["conversation.b"]})
    assert error["errors"]["base"] == "no_active_agents" and flow._draft == before
    assert (await flow.async_step_finish())["type"] == "create_entry"


@pytest.mark.parametrize(
    "order", [[], ["conversation.a", "conversation.a"], ["light.a"], ["conversation.home_assistant"]]
)
async def test_order_rejects_invalid_entities(ha, monkeypatch, order):
    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user()
    assert (await flow.async_step_order({"agent_order": order}))["errors"]["base"] == "invalid_agents"


async def test_router_entities_excluded_from_picker_and_submission(ha, monkeypatch):
    _, flow = new_flow(ha, monkeypatch)
    ha.hass.registry_entries = {
        "own": SimpleNamespace(entity_id="conversation.router_renamed", platform="assist_router")
    }
    form = await flow.async_step_user()
    validator = next(iter(form["data_schema"].schema.values()))
    with pytest.raises(vol.Invalid):
        validator(["conversation.router_renamed"])
    assert (await flow.async_step_order({"agent_order": ["conversation.router_renamed"]}))["errors"]


async def test_options_draft_cancel_keeps_stored_config(ha, monkeypatch, settings_data):
    module = flow_module(ha, monkeypatch)
    stored = deepcopy(settings_data)
    flow = module.OptionsFlow()
    flow.hass = ha.hass
    flow.config_entry = SimpleNamespace(data={}, options=stored)
    await flow.async_step_init()
    await flow.async_step_order({"agent_order": ["conversation.new"]})
    assert stored == settings_data
    saved = await flow.async_step_finish()
    assert saved["data"]["agents"][0]["entity_id"] == "conversation.new"
    assert saved["data"]["agents"][0]["health"] is None


async def test_credentials_retain_replace_clear_and_new_endpoint(ha, monkeypatch, health_data):
    module, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": ["conversation.a"]})
    await flow.async_step_health_agent({"entity_id": "conversation.a"})
    await flow.async_step_health_type({"kind": "lm_studio"})
    previous = health_data | {"token": "private-old", "auth_type": "bearer"}
    await flow.async_step_health(previous)
    form = await flow.async_step_health()
    assert "private-old" not in repr(form)
    assert module.merge_health(previous, {"token": ""}, "lm_studio")["token"] == "private-old"
    assert module.merge_health(previous, {"token": "new"}, "lm_studio")["token"] == "new"
    cleared = module.merge_health(previous, {"clear_credentials": True}, "lm_studio")
    assert cleared["auth_type"] == "none" and not cleared["token"]
    with pytest.raises(ValueError, match="invalid_auth"):
        module.merge_health(previous, {"url": "http://another/api/v1/models", "token": ""}, "lm_studio")
    invalid = await flow.async_step_health(previous | {"token": "do-not-echo", "url": "bad"})
    assert "do-not-echo" not in repr(invalid)


async def test_health_type_remove_and_basic_http_configured_through_ui(ha, monkeypatch):
    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": ["conversation.a"]})
    await flow.async_step_health_agent({"entity_id": "conversation.a"})
    form = await flow.async_step_health_type({"kind": "http"})
    values = form["data_schema"](
        {
            "url": "http://backend/health",
            "expected_status": 204,
            "auth_type": "basic",
            "username": "user",
            "password": "secret",
        }
    )
    assert (await flow.async_step_health(values))["type"] == "menu"
    assert flow._draft["agents"][0]["health"]["expected_status"] == 204
    await flow.async_step_health_type({"kind": "none"})
    assert flow._draft["agents"][0]["health"] is None


async def test_v1_migration_merges_options_and_preserves_health(ha):
    module = import_module("custom_components.assist_router")
    ha.hass.config_entries = SimpleNamespace(async_update_entry=Mock())
    entry = SimpleNamespace(
        version=1,
        data={
            "models_url": "http://old.example/api/v1/models",
            "model_key": "old-model",
            "instance_id": "old-instance",
            "token": "old",
        },
        options={
            "models_url": "https://models.example/proxy/api/v1/models",
            "local_agent": "conversation.custom",
            "model_key": "new-model",
            "token": "new",
            "cache_seconds": 3,
        },
    )
    assert await module.async_migrate_entry(ha.hass, entry)
    args = ha.hass.config_entries.async_update_entry.call_args.kwargs
    assert args["version"] == 3 and args["data"] == {} and args["minor_version"] == 1
    routes = args["options"]["agents"]
    assert routes[0]["entity_id"] == "conversation.custom"
    assert routes[0]["health"]["model_key"] == "new-model"
    assert routes[0]["health"]["url"] == entry.options["models_url"]
    assert routes[0]["health"]["token"] == "new" and routes[0]["health"]["cache_seconds"] == 3
    assert routes[1]["health"] is None and routes[2]["health"] is None


async def test_migration_rejects_invalid_or_future_config_without_mutation(ha):
    module = import_module("custom_components.assist_router")
    update = Mock()
    ha.hass.config_entries = SimpleNamespace(async_update_entry=update)
    assert not await module.async_migrate_entry(ha.hass, SimpleNamespace(version=1, data={}, options={}))
    assert not await module.async_migrate_entry(ha.hass, SimpleNamespace(version=4))
    assert await module.async_migrate_entry(ha.hass, SimpleNamespace(version=3))
    update.assert_not_called()


async def test_setup_unload_and_reload_retain_safety_ledger(ha, settings_data):
    module = import_module("custom_components.assist_router")
    ha.hass.http_session = object()
    ha.hass.config_entries = SimpleNamespace(
        async_forward_entry_setups=AsyncMock(), async_unload_platforms=AsyncMock(return_value=True)
    )
    entry = SimpleNamespace(
        entry_id="entry",
        data=settings_data,
        options={},
        async_on_unload=lambda cb: None,
        add_update_listener=lambda cb: lambda: None,
    )
    assert await module.async_setup_entry(ha.hass, entry)
    ledger = entry.runtime_data.ledger
    ledger.get("uncertain").blocked = True
    old_runtime = entry.runtime_data
    assert await module.async_unload_entry(ha.hass, entry)
    assert not old_runtime.active
    assert await module.async_setup_entry(ha.hass, entry)
    assert entry.runtime_data.ledger is ledger and ledger.sessions["uncertain"].blocked
    ha.hass.config_entries.async_unload_platforms.return_value = False
    assert not await module.async_unload_entry(ha.hass, entry)
    assert entry.runtime_data.active
