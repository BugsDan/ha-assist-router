"""Generic routing order, enablement, health adapters and per-agent isolation."""

from base64 import b64decode
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from .test_health import QueueSession, Reply, payload
from .test_router import add_agent, ask, setup_router


@pytest.mark.parametrize("order", [list(range(7)), list(reversed(range(7))), [4, 2, 6, 1, 0, 3, 5]])
async def test_arbitrary_priority_more_than_three_agents(ha, order):
    config = {"agents": [{"entity_id": f"conversation.any_{i}", "enabled": i not in (2, 4)} for i in order]}
    router = setup_router(ha, config)
    agents = [add_agent(ha, f"conversation.any_{i}") for i in range(7)]
    await ask(ha, router)
    first = next(i for i in order if i not in (2, 4))
    assert [len(agent.calls) for agent in agents] == [int(i == first) for i in range(7)]


async def test_one_active_without_health_never_calls_http(ha):
    from custom_components.assist_router.health import HealthChecks

    router = setup_router(ha, {"agents": [{"entity_id": "conversation.only"}]})
    session = SimpleNamespace(get=Mock(side_effect=AssertionError("unexpected HTTP")))
    router.runtime.health = HealthChecks(session, router.runtime.settings)
    agent = add_agent(ha, "conversation.only")
    result = await ask(ha, router)
    assert len(agent.calls) == 1 and result.conversation_id
    session.get.assert_not_called()


async def test_disabled_unavailable_agents_do_not_run_checks(ha, health_data):
    from custom_components.assist_router.health import HealthChecks

    config = {
        "agents": [
            {"entity_id": "conversation.disabled", "enabled": False, "health": health_data},
            {"entity_id": "conversation.missing", "health": health_data},
            {"entity_id": "conversation.only"},
        ]
    }
    router = setup_router(ha, config)
    router.runtime.health = HealthChecks(SimpleNamespace(get=Mock()), router.runtime.settings)
    disabled = add_agent(ha, "conversation.disabled")
    only = add_agent(ha, "conversation.only")
    await ask(ha, router)
    assert "conversation.disabled" not in router.runtime.health.checks
    assert not disabled.calls and len(only.calls) == 1
    assert router.runtime.health.checks["conversation.missing"].last.reason == "not_checked"


async def test_checks_follow_entity_after_reorder_and_are_cached_independently(ha, health_data):
    from custom_components.assist_router.health import HealthChecks
    from custom_components.assist_router.settings import Settings

    config = {
        "agents": [
            {"entity_id": "conversation.first", "health": health_data},
            {"entity_id": "conversation.second", "health": health_data | {"model_key": "second"}},
        ]
    }
    settings = Settings.from_mapping({"agents": list(reversed(config["agents"]))})
    session = QueueSession([Reply(data=payload(key="second")), Reply(data=payload(ids=()))])
    checks = HealthChecks(session, settings)
    assert (await checks.check("conversation.second")).ready
    assert not (await checks.check("conversation.first")).ready
    assert (await checks.check("conversation.second")).ready
    assert not (await checks.check("conversation.first")).ready
    assert len(session.calls) == 2
    assert checks.checks["conversation.second"].settings.model_key == "second"


async def test_health_failure_continues_before_dispatch_and_stops_checks_at_winner(ha, health_data):
    from custom_components.assist_router.health import HealthChecks

    config = {
        "agents": [
            {"entity_id": "conversation.primary", "health": health_data},
            {
                "entity_id": "conversation.secondary",
                "health": {"kind": "http", "url": "http://server/health", "expected_status": 204},
            },
            {"entity_id": "conversation.third", "health": health_data},
        ]
    }
    router = setup_router(ha, config)
    session = QueueSession([Reply(data=payload(ids=())), Reply(status=204)])
    router.runtime.health = HealthChecks(session, router.runtime.settings)
    agents = [add_agent(ha, route["entity_id"]) for route in config["agents"]]
    await ask(ha, router)
    assert [len(agent.calls) for agent in agents] == [0, 1, 0]
    assert [call[0] for call in session.calls] == [health_data["url"], "http://server/health"]


async def test_pending_agent_disabled_on_reload_never_reinterprets_reply(ha, settings_data):
    from custom_components.assist_router.settings import Settings

    router = setup_router(ha, settings_data)
    first = add_agent(ha, "conversation.alpha", follow_up=True)
    other = add_agent(ha, "conversation.beta")
    result = await ask(ha, router)
    settings_data["agents"][0]["enabled"] = False
    router.runtime.settings = Settings.from_mapping(settings_data)
    await ask(ha, router, "Ja", result.conversation_id)
    assert len(first.calls) == 1 and not other.calls


async def test_control_feature_ignores_disabled_agent(ha):
    router = setup_router(
        ha,
        {
            "agents": [
                {"entity_id": "conversation.disabled", "enabled": False},
                {"entity_id": "conversation.only"},
            ]
        },
    )
    add_agent(ha, "conversation.disabled")
    add_agent(ha, "conversation.only")
    ha.hass.state_values["conversation.only"].attributes.clear()
    assert not router.supported_features


@pytest.mark.parametrize(
    "settings",
    [
        {"agents": []},
        {"agents": [{"entity_id": "conversation.a", "enabled": False}]},
        {"agents": [{"entity_id": "conversation.a"}] * 2},
        {"agents": [{"entity_id": "light.a"}]},
        {"agents": [{"entity_id": "conversation.home_assistant"}]},
        {"agents": [{"entity_id": "conversation.a", "enabled": "false"}]},
    ],
)
def test_generic_settings_reject_invalid_routes(ha, settings):
    from custom_components.assist_router.settings import Settings

    with pytest.raises(ValueError):
        Settings.from_mapping(settings)


async def test_basic_auth_and_http_status_do_not_require_json_body(ha):
    from custom_components.assist_router.health import ModelHealth
    from custom_components.assist_router.settings import HealthSettings

    settings = HealthSettings.from_mapping(
        {
            "kind": "http",
            "url": "http://local/health",
            "auth_type": "basic",
            "username": "dani",
            "password": "é-secret",
            "expected_status": 204,
        }
    )
    session = QueueSession([Reply(status=204, body=b"not JSON")])
    assert (await ModelHealth(session, settings).check()).ready
    request = session.calls[0][1]
    header = request["headers"]["Authorization"]
    assert b64decode(header.removeprefix("Basic ")).decode("utf-8") == "dani:é-secret"
    assert request["allow_redirects"] is False


@pytest.mark.parametrize("state,instance,ready", [("loaded", "gemma-instance", False), ("present", "", True)])
async def test_model_state_predicate_configurable(ha, health_data, state, instance, ready):
    from custom_components.assist_router.health import ModelHealth
    from custom_components.assist_router.settings import HealthSettings

    settings = HealthSettings.from_mapping(health_data | {"model_state": state, "instance_id": instance})
    assert (await ModelHealth(QueueSession([Reply(data=payload(ids=()))]), settings).check()).ready == ready


async def test_new_adapter_registers_without_routing_changes(ha, monkeypatch):
    from custom_components.assist_router.health import ModelHealth
    from custom_components.assist_router.health_types import CHECK_TYPES, CheckType, Health
    from custom_components.assist_router.settings import HealthSettings

    adapter = CheckType(
        True, lambda settings: None, lambda data, settings: Health(data.get("ready") is True, "custom")
    )
    monkeypatch.setitem(CHECK_TYPES, "future_local", adapter)
    settings = HealthSettings.from_mapping({"kind": "future_local", "url": "http://local/status"})
    assert (await ModelHealth(QueueSession([Reply(data={"ready": True})]), settings).check()).ready


async def test_diagnostic_redacts_all_per_agent_secrets(ha, settings_data):
    from custom_components.assist_router.diagnostics import async_get_config_entry_diagnostics
    from custom_components.assist_router.health import HealthChecks

    settings_data["agents"][0]["health"].update(auth_type="bearer", token="private-token")
    router = setup_router(ha, settings_data)
    router.runtime.health = HealthChecks(object(), router.runtime.settings)
    result = await async_get_config_entry_diagnostics(ha.hass, SimpleNamespace(runtime_data=router.runtime))
    assert "private-token" not in repr(result) and "127.0.0.1" not in repr(result)
    assert result["health"]["conversation.alpha"]["kind"] == "lm_studio"


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "unknown"},
        {"kind": []},
        {"expected_status": 302},
        {"expected_status": 500},
        {"expected_status": True},
        {"auth_type": "basic", "username": "bad:name"},
        {"auth_type": "bearer", "token": ""},
        {"model_state": "present", "instance_id": "unexpected"},
        {"model_state": "unloaded"},
    ],
)
def test_invalid_health_configuration_cannot_be_saved(ha, health_data, changes):
    from custom_components.assist_router.settings import HealthSettings

    with pytest.raises(ValueError):
        HealthSettings.from_mapping(health_data | changes)
