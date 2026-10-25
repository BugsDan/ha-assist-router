"""Real Home Assistant runtime tests. Run separately on Linux / Python >=3.14.2.

No SDKs, provider credentials or production HA instance are used.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("homeassistant", reason="Requires installed Home Assistant 2026.10.2 on Linux")

from homeassistant.components import conversation
from homeassistant.components.conversation.const import DATA_COMPONENT
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from custom_components.assist_router.conversation import AssistRouter
from custom_components.assist_router.health import Health
from custom_components.assist_router.prompts import PromptManager, PromptSnapshot
from custom_components.assist_router.runtime import Ledger, Runtime
from custom_components.assist_router.settings import Settings


@pytest.mark.ha
@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("shared", [False, True])
async def test_real_core_entity_chatlog_followup_and_failure(tmp_path, fail, shared):
    hass = HomeAssistant(str(tmp_path))
    calls = []

    class Leaf(conversation.ConversationEntity):
        _attr_name = "Router Test Leaf"
        _attr_unique_id = "router-test-leaf"

        @property
        def supported_languages(self):
            return "*"

        async def _async_handle_message(self, user_input, chat_log):
            calls.append((user_input, list(chat_log.content)))
            if fail:
                raise RuntimeError("action may already have executed")
            response = intent.IntentResponse(language=user_input.language)
            response.async_set_speech("Äpfel oder Café?")
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(agent_id=self.entity_id, content="Äpfel oder Café?")
            )
            return conversation.ConversationResult(response, chat_log.conversation_id, True)

    try:
        assert await async_setup_component(hass, "conversation", {})
        component = hass.data[DATA_COMPONENT]
        leaf = Leaf()
        await component.async_add_entities([leaf])
        settings = Settings.from_mapping(
            {
                "agents": [{"entity_id": leaf.entity_id, "enabled": True, "health": None}],
                "prompt": {
                    "enabled": shared,
                    "text": "Gemeinsam: Café e\u0301\nö ü",
                    "reviews": {leaf.entity_id: "a" * 64},
                },
            }
        )
        runtime = Runtime(
            settings, SimpleNamespace(check=AsyncMock(return_value=Health(True, "ready"))), Ledger()
        )
        runtime.prompts = PromptManager(
            settings, SimpleNamespace(inspect=AsyncMock(return_value=PromptSnapshot("ready", "a" * 64)))
        )
        router = AssistRouter(SimpleNamespace(entry_id="router-test", runtime_data=runtime))
        await component.async_add_entities([router])
        first = await conversation.async_converse(
            hass, "Äpfel Öl Gemüse Café e\u0301", None, Context(), "de", router.entity_id
        )
        assert first.conversation_id is not None
        assert calls[0][0].extra_system_prompt == ("Gemeinsam: Café e\u0301\nö ü" if shared else None)
        second = await conversation.async_converse(
            hass, "Die zweite", first.conversation_id, Context(), "de", router.entity_id
        )
        assert second.conversation_id == first.conversation_id
        if fail:
            assert len(calls) == 1
            assert second.response.response_type == intent.IntentResponseType.ERROR
        else:
            assert len(calls) == 2 and second.continue_conversation
            assert sum(item.role == "user" for item in calls[1][1]) == 2
            assert calls[0][0].text == "Äpfel Öl Gemüse Café e\u0301"
    finally:
        await hass.async_stop()
