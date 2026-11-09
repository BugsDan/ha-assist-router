"""Regression tests for health-first routing and editable offline configuration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from .test_config import new_flow
from .test_prompt_management import enable
from .test_router import add_agent, ask, setup_router


async def test_unreviewed_offline_target_does_not_block_available_agent(ha, settings_data):
    router = setup_router(ha, settings_data, ready=False)
    local = add_agent(ha, router.runtime.settings.agents[0])
    cloud = add_agent(ha, router.runtime.settings.agents[1])
    inspector = enable(ha, router)
    inspector.inspect.side_effect = AssertionError("must not inspect")
    result = await ask(ha, router)
    assert result.response.response_type != ha.intent.IntentResponseType.ERROR
    assert not local.calls and len(cloud.calls) == 1
    inspector.inspect.assert_not_called()


async def test_invalid_body_failure_does_not_retry(ha, settings_data):
    async def fail(*args):
        raise ValueError("invalid body with private data")

    router = setup_router(ha, settings_data)
    local = add_agent(ha, router.runtime.settings.agents[0], handler=fail)
    cloud = add_agent(ha, router.runtime.settings.agents[1])
    enable(ha, router)
    result = await ask(ha, router)
    await ask(ha, router, cid=result.conversation_id)
    assert len(local.calls) == 1 and not cloud.calls
    assert router.runtime.ledger.sessions[result.conversation_id].blocked
    assert "private data" not in repr(result)


async def test_selection_retains_disabled_health_and_can_restore(ha, monkeypatch, health_data):
    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": ["conversation.a", "conversation.b"]})
    flow._draft["agents"][1]["health"] = health_data
    await flow.async_step_order({"agent_order": ["conversation.a"]})
    saved = await flow.async_step_finish()
    assert saved["options"]["agents"][1]["enabled"] is False
    assert saved["options"]["agents"][1]["health"]["model_key"] == health_data["model_key"]
    await flow.async_step_order({"agent_order": ["conversation.b", "conversation.a"]})
    assert flow._draft["agents"][0]["enabled"]
    assert flow._draft["agents"][0]["health"]["model_key"] == health_data["model_key"]


async def test_ui_save_offline_does_not_inspect_and_hides_redundant_menus(ha, monkeypatch):
    _, flow = new_flow(ha, monkeypatch)
    menu = await flow.async_step_user({"agent_order": ["conversation.a"]})
    assert set(menu["menu_options"]) == {"order", "health_agent", "shared_prompt", "finish"}
    flow._inspector = SimpleNamespace(inspect=AsyncMock(side_effect=AssertionError("offline")))
    await flow.async_step_shared_prompt({"enabled": True, "text": "Café äöü", "acknowledge_additive": True})
    saved = await flow.async_step_finish()
    assert saved["options"]["prompt"]["text"] == "Café äöü"
    flow._inspector.inspect.assert_not_called()


async def test_legacy_additions_preserved_until_explicitly_cleared(ha, monkeypatch):
    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": ["conversation.a"]})
    flow._draft["agents"][0]["prompt_addition"] = "Alte Ergänzung"
    await flow.async_step_shared_prompt({"enabled": True, "text": "Café", "acknowledge_additive": True})
    assert flow._draft["agents"][0]["prompt_addition"] == "Alte Ergänzung"
    await flow.async_step_shared_prompt(
        {"enabled": True, "text": "Café", "acknowledge_additive": True, "clear_legacy_additions": True}
    )
    assert flow._draft["agents"][0]["prompt_addition"] == ""


async def test_existing_130_settings_keep_prompt_priority_health_and_inactive_agents(
    ha, monkeypatch, settings_data
):
    from copy import deepcopy

    from .test_config import flow_module

    old = deepcopy(settings_data)
    old["agents"][1]["enabled"] = False
    old["agents"][0]["prompt_addition"] = "model-specific ä"
    old["prompt"] = {
        "enabled": True,
        "text": "Gemeinsam é",
        "mode": "strict",
        "reviews": {"conversation.alpha": "a" * 64},
    }
    module = flow_module(ha, monkeypatch)
    flow = module.OptionsFlow()
    flow.hass = ha.hass
    flow.config_entry = SimpleNamespace(data={}, options=old)
    await flow.async_step_init()
    result = await flow.async_step_finish()
    saved = result["data"]
    assert [r["entity_id"] for r in saved["agents"]] == [r["entity_id"] for r in old["agents"]]
    assert saved["agents"][1]["enabled"] is False
    assert saved["agents"][0]["health"]["model_key"] == old["agents"][0]["health"]["model_key"]
    assert saved["agents"][0]["prompt_addition"] == "model-specific ä"
    assert saved["prompt"]["text"] == "Gemeinsam é"
    assert saved["prompt"]["reviews"] == old["prompt"]["reviews"]
