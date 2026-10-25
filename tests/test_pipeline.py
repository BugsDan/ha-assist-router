"""Execute HA's pinned recognize_intent/prepare methods, with recognition/audio doubles."""

import logging
from dataclasses import dataclass
from types import MethodType, SimpleNamespace

import pytest

from .core_harness import source_nodes
from .test_router import add_agent, setup_router


def pipeline(ha, router):
    @dataclass
    class Event:
        type: str
        data: dict

    events = []
    host = SimpleNamespace(
        hass=ha.hass,
        context=ha.Context(),
        device_id="device",
        satellite_id=None,
        pipeline=SimpleNamespace(
            conversation_engine=router.entity_id,
            conversation_language="de",
            language="de",
            stt_language="de",
            tts_language="de",
            prefer_local_intents=True,
        ),
        process_event=events.append,
    )
    processor = SimpleNamespace(
        host=host,
        intent_agent=SimpleNamespace(id=router.entity_id),
        _conversation_data=SimpleNamespace(continue_conversation_agent=None),
        _intent_agent_only=False,
        tts_stream=None,
        _streamed_response_text=False,
        _get_all_targets_in_satellite_area=lambda *args: False,
    )
    namespace = {
        "__name__": __name__,
        "conversation": ha.conv,
        "chat_session": ha.session,
        "intent": ha.intent,
        "MATCH_ALL": "*",
        "callback": lambda func: func,
        "PipelineEvent": Event,
        "PipelineEventType": SimpleNamespace(
            INTENT_START="start", INTENT_END="end", INTENT_PROGRESS="progress"
        ),
        "EntityStateAttribute": SimpleNamespace(SUPPORTED_FEATURES="supported_features"),
        "_async_local_fallback_intent_filter": lambda result: False,
        "_LOGGER": logging.getLogger("test.pipeline"),
        "IntentRecognitionError": RuntimeError,
        "async_get_pipeline_conversation_data": lambda hass, session: processor._conversation_data,
    }
    source_nodes(
        "homeassistant/components/assist_pipeline/default_pipeline.py",
        ["recognize_intent", "prepare_recognize_intent"],
        namespace,
    )
    processor.recognize_intent = MethodType(namespace["recognize_intent"], processor)
    processor.prepare_recognize_intent = MethodType(namespace["prepare_recognize_intent"], processor)
    ha.conv.async_get_agent_info = lambda hass, agent_id: SimpleNamespace(id=agent_id)
    return processor, events


@pytest.mark.parametrize("sentence", ["Schalte das Küchenlicht ein", "Schliesse die Rollläden"])
async def test_native_local_command_never_reaches_router(ha, settings_data, sentence):
    router = setup_router(ha, settings_data)
    local = add_agent(ha, router.runtime.settings.agents[0])
    response = ha.intent.IntentResponse("de")
    response.async_set_speech("Erledigt")
    response.response_type = ha.intent.IntentResponseType.ACTION_DONE
    ha.conv.async_handle_intents.return_value = response
    processor, events = pipeline(ha, router)
    speech, _ = await processor.recognize_intent(sentence, "native-session", None)
    assert speech == "Erledigt" and not local.calls
    router.runtime.health.check.assert_not_called()
    assert events[-1].data["processed_locally"] is True


async def test_native_shopping_sentence_trigger_keeps_precedence(ha, settings_data):
    router = setup_router(ha, settings_data)
    local = add_agent(ha, router.runtime.settings.agents[0])
    ha.conv.async_handle_sentence_triggers.return_value = "Auf der Einkaufsliste"
    processor, _ = pipeline(ha, router)
    assert (await processor.recognize_intent("Füge Äpfel hinzu", "shopping", None))[
        0
    ] == "Auf der Einkaufsliste"
    assert not local.calls
    ha.conv.async_handle_intents.assert_not_called()
    router.runtime.health.check.assert_not_called()


async def test_pipeline_follow_up_returns_to_router_not_leaf(ha, settings_data):
    router = setup_router(ha, settings_data, ready=False)
    cloud = add_agent(ha, router.runtime.settings.agents[1], follow_up=True)
    processor, events = pipeline(ha, router)
    await processor.recognize_intent("Welche Sorte?", "followup", None)
    assert processor._conversation_data.continue_conversation_agent == router.entity_id
    session = ha.hass.data["chat_session"]["followup"]
    await processor.prepare_recognize_intent(session)
    assert processor._intent_agent_only and processor.intent_agent.id == router.entity_id
    ha.conv.async_handle_sentence_triggers.reset_mock()
    ha.conv.async_handle_intents.reset_mock()
    await processor.recognize_intent("Die zweite", "followup", None)
    assert len(cloud.calls) == 2
    ha.conv.async_handle_sentence_triggers.assert_not_called()
    ha.conv.async_handle_intents.assert_not_called()
    assert events[-1].data["intent_output"]["conversation_id"] == "followup"
    assert sum(item.role == "user" for item in cloud.calls[-1][1].content) == 2
