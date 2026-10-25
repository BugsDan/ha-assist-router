"""Real pinned HA session/log/entity/delegation nodes around the router."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def setup_router(ha, data, ready=True):
    from custom_components.assist_router.health import Health
    from custom_components.assist_router.runtime import Ledger, Runtime
    from custom_components.assist_router.settings import Settings

    settings = Settings.from_mapping(data)
    health = SimpleNamespace(check=AsyncMock(return_value=Health(ready, "ready" if ready else "timeout")))

    async def check(agent_id):
        route = next(route for route in settings.routes if route.entity_id == agent_id)
        return health.check.return_value if route.health else Health(True, "entity_only")

    health.check.side_effect = check
    health.diagnostics = lambda: {}
    runtime = Runtime(settings, health, Ledger())
    router = ha.router_module.AssistRouter(SimpleNamespace(entry_id="entry", runtime_data=runtime))
    router.hass = ha.hass
    router.entity_id = "conversation.assist_router"
    ha.hass.agents[router.entity_id] = router
    ha.hass.state_values[router.entity_id] = SimpleNamespace(
        state="unknown", attributes={"supported_features": 1}
    )
    return router


def add_agent(ha, agent_id, handler=None, *, follow_up=False, available=True):
    class Agent(ha.conv.ConversationEntity):
        supported_languages = "*"

        async def _async_handle_message(self, user_input, chat_log):
            self.calls.append((user_input, chat_log))
            if handler:
                return await handler(user_input, chat_log)
            response = ha.intent.IntentResponse(user_input.language)
            response.async_set_speech("Äpfel, Öl, Gemüse, Café, Crème brûlée?")
            response.data = {"nested": {"tool_args": {"name": "Café e\u0301 🥐"}}}
            chat_log.async_add_assistant_content_without_tools(
                ha.conv.AssistantContent(agent_id=agent_id, content=response.speech["plain"]["speech"])
            )
            return ha.conv.ConversationResult(response, chat_log.conversation_id, follow_up)

    agent = Agent()
    agent.hass = ha.hass
    agent.entity_id = agent_id
    agent.calls = []
    agent.available = available
    ha.hass.agents[agent_id] = agent
    ha.hass.state_values[agent_id] = SimpleNamespace(state="unknown", attributes={"supported_features": 1})
    return agent


async def ask(ha, router, text="Füge Äpfel, Öl, Gemüse und Café e\u0301 🥐 hinzu", cid=None):
    return await ha.conv.async_converse(
        ha.hass,
        text,
        cid,
        ha.Context(),
        "de-CH",
        router.entity_id,
        "device",
        "satellite",
        "Zusatz: é ä ö ü e\u0301",
    )


async def test_local_ready_forwards_all_context_once(ha, settings_data):
    router = setup_router(ha, settings_data)
    agent = add_agent(ha, router.runtime.settings.agents[0])
    add_agent(ha, router.runtime.settings.agents[1])
    result = await ask(ha, router)
    inp, log = agent.calls[0]
    assert len(agent.calls) == 1
    assert inp.context.id == "context" and inp.context.user_id == "user"
    assert inp.language == "de-CH" and inp.device_id == "device" and inp.satellite_id == "satellite"
    assert inp.extra_system_prompt == "Zusatz: é ä ö ü e\u0301"
    assert inp.conversation_id == result.conversation_id == log.conversation_id
    assert [c.role for c in log.content] == ["system", "user", "assistant"]
    assert log.content[1].content == inp.text
    assert result.response.data["nested"]["tool_args"]["name"] == "Café e\u0301 🥐"
    assert not ha.hass.agents[router.runtime.settings.agents[1]].calls


async def test_preflight_fallback_then_priority_recovers(ha, settings_data):
    from custom_components.assist_router.health import Health

    router = setup_router(ha, settings_data, ready=False)
    local = add_agent(ha, router.runtime.settings.agents[0])
    cloud = add_agent(ha, router.runtime.settings.agents[1])
    first = await ask(ha, router, "Wie heisst die Hauptstadt?")
    assert not local.calls and len(cloud.calls) == 1
    router.runtime.health.check.return_value = Health(True, "ready")
    second = await ask(ha, router, "Und wie viele Einwohner hat sie?", first.conversation_id)
    assert second.conversation_id == first.conversation_id
    assert len(local.calls) == 1
    assert [c.role for c in local.calls[0][1].content] == ["system", "user", "assistant", "user", "assistant"]


@pytest.mark.parametrize("missing", ["missing", "unavailable", "disabled"])
async def test_openai_skipped_only_before_dispatch(ha, settings_data, missing):
    router = setup_router(ha, settings_data, ready=False)
    local = add_agent(ha, router.runtime.settings.agents[0])
    if missing != "missing":
        cloud = add_agent(ha, router.runtime.settings.agents[1], available=missing != "disabled")
        if missing == "unavailable":
            ha.hass.state_values[cloud.entity_id].state = "unavailable"
    gemini = add_agent(ha, router.runtime.settings.agents[2])
    await ask(ha, router)
    assert len(gemini.calls) == 1 and not local.calls


async def test_follow_up_stays_with_questioning_agent(ha, settings_data):
    from custom_components.assist_router.health import Health

    router = setup_router(ha, settings_data, ready=False)
    local = add_agent(ha, router.runtime.settings.agents[0])
    cloud = add_agent(ha, router.runtime.settings.agents[1], follow_up=True)
    first = await ask(ha, router)
    router.runtime.health.check.return_value = Health(True, "ready")
    second = await ask(ha, router, "Ja", first.conversation_id)
    assert second.continue_conversation and len(cloud.calls) == 2 and not local.calls
    assert cloud.calls[1][0].text == "Ja"
    assert sum(c.role == "user" for c in cloud.calls[1][1].content) == 2


async def test_unavailable_follow_up_does_not_reinterpret_yes(ha, settings_data):
    router = setup_router(ha, settings_data, ready=False)
    cloud = add_agent(ha, router.runtime.settings.agents[1], follow_up=True)
    gemini = add_agent(ha, router.runtime.settings.agents[2])
    first = await ask(ha, router)
    cloud.available = False
    result = await ask(ha, router, "Ja", first.conversation_id)
    assert result.response.response_type == ha.intent.IntentResponseType.ERROR
    assert not result.continue_conversation and not gemini.calls
    assert len(cloud.calls) == 1


@pytest.mark.parametrize("failure", ["exception", "timeout", "ha_error", "result_error", "id_changed"])
async def test_action_then_error_never_repeats_and_blocks_session(ha, settings_data, failure):
    router = setup_router(ha, settings_data)
    writes = []

    async def handler(inp, log):
        writes.append("Yuvomi Äpfel")
        if failure == "exception":
            raise RuntimeError("secret prompt/token must not be logged")
        if failure == "timeout":
            raise TimeoutError
        if failure == "ha_error":
            raise ha.HomeAssistantError("after action")
        response = ha.intent.IntentResponse(inp.language)
        if failure == "result_error":
            response.async_set_error(ha.intent.IntentResponseErrorCode.UNKNOWN, "Tool failure")
        return ha.conv.ConversationResult(
            response, "changed-id" if failure == "id_changed" else log.conversation_id
        )

    local = add_agent(ha, router.runtime.settings.agents[0], handler)
    cloud = add_agent(ha, router.runtime.settings.agents[1])
    gemini = add_agent(ha, router.runtime.settings.agents[2])
    first = await ask(ha, router)
    assert first.response.response_type == ha.intent.IntentResponseType.ERROR
    assert router.runtime.ledger.sessions[first.conversation_id].blocked
    await ask(ha, router, cid=first.conversation_id)
    assert len(local.calls) == 1 and writes == ["Yuvomi Äpfel"]
    assert not cloud.calls and not gemini.calls


async def test_cancellation_after_tool_start_no_second_dispatch(ha, settings_data):
    router = setup_router(ha, settings_data)
    started = asyncio.Event()

    async def handler(inp, log):
        started.set()
        await asyncio.Event().wait()

    add_agent(ha, router.runtime.settings.agents[0], handler)
    cloud = add_agent(ha, router.runtime.settings.agents[1])
    task = asyncio.create_task(ask(ha, router, cid="external-session"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert router.runtime.ledger.sessions["external-session"].blocked
    await ask(ha, router, cid="external-session")
    assert not cloud.calls


async def test_busy_same_session_rejected_other_session_independent(ha, settings_data):
    router = setup_router(ha, settings_data)
    started, release = asyncio.Event(), asyncio.Event()

    async def handler(inp, log):
        if inp.conversation_id == "first":
            started.set()
            await release.wait()
        response = ha.intent.IntentResponse(inp.language)
        return ha.conv.ConversationResult(response, log.conversation_id)

    local = add_agent(ha, router.runtime.settings.agents[0], handler)
    task = asyncio.create_task(ask(ha, router, cid="first"))
    await started.wait()
    busy = await ask(ha, router, cid="first")
    await ask(ha, router, cid="second")
    assert busy.response.response_type == ha.intent.IntentResponseType.ERROR
    assert len(local.calls) == 2
    release.set()
    await task


async def test_recursive_tool_call_even_new_id_is_blocked(ha, settings_data):
    router = setup_router(ha, settings_data)
    nested = []

    async def handler(inp, log):
        nested.append(await ask(ha, router, cid="different-conversation"))
        return ha.conv.ConversationResult(ha.intent.IntentResponse(inp.language), log.conversation_id)

    local = add_agent(ha, router.runtime.settings.agents[0], handler)
    await ask(ha, router)
    assert len(local.calls) == 1 and nested[0].response.response_type == ha.intent.IntentResponseType.ERROR


async def test_missing_result_id_uses_actual_active_session(ha, settings_data):
    router = setup_router(ha, settings_data)

    async def handler(inp, log):
        return ha.conv.ConversationResult(ha.intent.IntentResponse(inp.language), None, True)

    add_agent(ha, router.runtime.settings.agents[0], handler)
    result = await ask(ha, router)
    assert result.conversation_id in router.runtime.ledger.sessions
    assert result.continue_conversation


async def test_no_agents_gives_stored_error_without_health_call(ha, settings_data):
    router = setup_router(ha, settings_data)
    result = await ask(ha, router)
    assert result.response.response_type == ha.intent.IntentResponseType.ERROR
    router.runtime.health.check.assert_not_called()
    assert ha.hass.data["logs"][result.conversation_id].content[-1].role == "assistant"


async def test_features_follow_leaf_capabilities(ha, settings_data):
    router = setup_router(ha, settings_data)
    assert not router.supported_features
    local = add_agent(ha, router.runtime.settings.agents[0])
    assert router.supported_features == ha.conv.ConversationEntityFeature.CONTROL
    ha.hass.state_values[local.entity_id].attributes.clear()
    assert not router.supported_features


async def test_metadata_cleanup_and_block_survives_runtime_reload(ha, settings_data):
    from custom_components.assist_router.runtime import Runtime

    router = setup_router(ha, settings_data)
    add_agent(ha, router.runtime.settings.agents[0])
    result = await ask(ha, router)
    state = router.runtime.ledger.sessions[result.conversation_id]
    session = ha.hass.data["chat_session"][result.conversation_id]
    assert len(session._cleanup_callbacks) == 2  # one router callback and one core log callback
    await ask(ha, router, cid=result.conversation_id)
    assert len(session._cleanup_callbacks) == 2
    state.blocked = True
    session.async_cleanup()
    assert result.conversation_id in router.runtime.ledger.sessions
    new = Runtime(router.runtime.settings, router.runtime.health, router.runtime.ledger)
    assert new.ledger.sessions[result.conversation_id].blocked
