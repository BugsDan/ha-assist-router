"""Tool payload integrity and uncertain execution use the pinned HA ChatLog code."""

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

from .test_router import add_agent, ask, setup_router


async def test_real_chatlog_tool_arguments_and_result_not_reencoded(ha, settings_data):
    router = setup_router(ha, settings_data)
    arguments = {"name": "Äpfel Öl Gemüse Café e\u0301 🥐", "quantity": 2, "nested": ["ü", {"é": None}]}

    @dataclass
    class ToolInput:
        id: str
        tool_name: str
        tool_args: dict
        external: bool = False

    @dataclass
    class ToolResult:
        data: dict
        error: bool = False

    tool_input = ToolInput("tool-1", "yuvomi_add_shopping_item", arguments)
    seen = []

    async def execute(value):
        seen.append(value.tool_args)
        return ToolResult({"name": value.tool_args["name"], "ok": True})

    ha.hass.async_create_task = lambda coro, **kwargs: asyncio.create_task(coro)

    async def handler(inp, log):
        log.llm_api = SimpleNamespace(async_call_tool=execute)
        content = ha.conv.AssistantContent(agent_id=inp.agent_id, tool_calls=[tool_input])
        results = [item async for item in log.async_add_assistant_content(content)]
        response = ha.intent.IntentResponse(inp.language)
        response.async_set_speech(results[0].result.data["name"])
        log.async_add_assistant_content_without_tools(
            ha.conv.AssistantContent(agent_id=inp.agent_id, content=response.speech["plain"]["speech"])
        )
        return ha.conv.ConversationResult(response, log.conversation_id)

    local = add_agent(ha, router.runtime.settings.agents[0], handler)
    result = await ask(ha, router)
    assert seen == [arguments] and seen[0] is arguments
    assert result.response.speech["plain"]["speech"] == arguments["name"]
    log = local.calls[0][1]
    assert log.content[2].tool_calls[0] is tool_input
    assert log.content[3].result.data["name"] == arguments["name"]


async def test_running_background_action_after_agent_error_not_replayed(ha, settings_data):
    router = setup_router(ha, settings_data)
    release = asyncio.Event()
    writes = []
    tasks = []

    async def action():
        await release.wait()
        writes.append("Äpfel")

    async def handler(inp, log):
        tasks.append(asyncio.create_task(action()))
        raise RuntimeError("model stream lost after tool task scheduled")

    local = add_agent(ha, router.runtime.settings.agents[0], handler)
    cloud = add_agent(ha, router.runtime.settings.agents[1])
    result = await ask(ha, router)
    await ask(ha, router, cid=result.conversation_id)
    assert len(local.calls) == 1 and not cloud.calls and not writes
    release.set()
    await asyncio.gather(*tasks)
    assert writes == ["Äpfel"]


async def test_unload_during_health_never_dispatches(ha, settings_data):
    from custom_components.assist_router.health import Health

    router = setup_router(ha, settings_data)
    local = add_agent(ha, router.runtime.settings.agents[0])
    cloud = add_agent(ha, router.runtime.settings.agents[1])

    async def health(agent_id):
        router.runtime.active = False
        return Health(True, "ready")

    router.runtime.health.check = AsyncMock(side_effect=health)
    result = await ask(ha, router)
    assert result.response.response_type == ha.intent.IntentResponseType.ERROR
    assert not local.calls and not cloud.calls


def test_capacity_never_evicts_uncertain_execution(ha):
    from custom_components.assist_router.const import MAX_SESSIONS
    from custom_components.assist_router.runtime import Ledger

    ledger = Ledger()
    for i in range(MAX_SESSIONS):
        ledger.get(str(i)).blocked = True
    assert ledger.get("new") is None
    ledger.cleanup("0", ledger.sessions["0"])
    assert "0" in ledger.sessions


async def test_diagnostics_excludes_all_credentials_and_content(ha, settings_data):
    from custom_components.assist_router.diagnostics import async_get_config_entry_diagnostics
    from custom_components.assist_router.health import Health

    settings_data["agents"][0]["health"].update(token="secret-token", auth_type="bearer")
    router = setup_router(ha, settings_data)
    router.runtime.health.last = Health(False, "timeout")
    diagnostic = await async_get_config_entry_diagnostics(
        ha.hass, SimpleNamespace(runtime_data=router.runtime)
    )
    assert "secret-token" not in repr(diagnostic)
    assert "127.0.0.1" not in repr(diagnostic)
    assert "model_key" not in diagnostic
