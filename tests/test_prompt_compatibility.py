"""Audited provider handlers, additive assembly and request transport contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from .core_harness import source_nodes

EVIDENCE = "docs/prompt_compatibility_evidence.json"
SHARED = "Gemeinsam: Äpfel, Öl, Gemüse, Café e\u0301 🥐"


def load(relative, names, namespace):
    source_nodes("prompt_compatibility/" + relative, names, namespace, evidence_file=EVIDENCE)
    return namespace


def prompt_log(ha):
    """Real ChatLog assembler; template rendering/LLM API discovery are host doubles."""

    class API:
        async def async_get_api_instance(self, context):
            return self.instance

    ha.conv.llm = SimpleNamespace(
        API=API,
        DEFAULT_INSTRUCTIONS_PROMPT="HA_DEFAULT_BASE",
        DATE_TIME_PROMPT="HA_CLOCK",
        LLMContext=lambda **kwargs: SimpleNamespace(**kwargs),
        async_get_apis=lambda hass: [],
    )
    log = ha.conv.ChatLog(ha.hass, "prompt-test")
    log.async_add_user_content(ha.conv.UserContent(content="Testanfrage"))
    log.async_trace = lambda details: None
    clock = ["CLOCK_1"]

    async def render(context, text, language, user_name):
        return clock[0] if text == "HA_CLOCK" else text

    log._async_expand_prompt_template = render
    context = SimpleNamespace(language="de", context=None)
    return log, context, API, clock


@pytest.mark.parametrize("provider", ["openai", "google", "local"])
@pytest.mark.parametrize("baseline", ["old", "neutral"])
async def test_audited_handler_appends_extra_and_keeps_existing_agent_prompt(ha, provider, baseline):
    from custom_components.assist_router.prompts import NEUTRAL_BASELINE, PromptManager
    from custom_components.assist_router.settings import Settings

    base = "OLD_CONFLICTING_AGENT_RULE" if baseline == "old" else NEUTRAL_BASELINE
    extra = SHARED
    if baseline == "neutral":
        manager = PromptManager(
            Settings.from_mapping(
                {"agents": [{"entity_id": "conversation.a"}], "prompt": {"enabled": True, "text": SHARED}}
            )
        )
        extra = manager.compose("conversation.a", None)
    log, _, _, _ = prompt_log(ha)
    ha.hass.auth = SimpleNamespace(async_get_user=lambda user: None)
    # Use no user_id so the real assembler need not await an authentication service.
    ctx = ha.Context(user_id=None)
    inp = ha.conv.ConversationInput(
        text="Test",
        context=ctx,
        conversation_id="prompt-test",
        device_id=None,
        satellite_id=None,
        language="de",
        agent_id="conversation.a",
        extra_system_prompt=extra,
    )
    captured = []

    async def capture(chat_log, **kwargs):
        captured.append(chat_log.content[0].content)

    ha.conv.async_get_result_from_chat_log = lambda user, chat: ha.conv.ConversationResult(
        ha.intent.IntentResponse("de"), chat.conversation_id
    )
    agent = SimpleNamespace(
        hass=ha.hass,
        subentry=SimpleNamespace(data={"prompt": base}),
        _async_handle_chat_log=capture,
    )
    namespace = {
        "__name__": __name__,
        "conversation": ha.conv,
        "CONF_PROMPT": "prompt",
        "CONF_LLM_HASS_API": "llm_hass_api",
        "DOMAIN": provider,
        "override": lambda function: function,
        "llm": ha.conv.llm,
        "CONF_PARALLEL_TOOL_CALLS": "parallel_tool_calls",
        "CONF_ALWAYS_CONTINUE_CONVERSATION": "always_continue",
        "CONF_ALWAYS_CONTINUE_CONVERSATION_DEFAULT": False,
    }
    path = {
        "openai": "core/openai_conversation.py",
        "google": "core/google_conversation.py",
        "local": "local/conversation.py",
    }[provider]
    handler = load(path, ["_async_handle_message"], namespace)["_async_handle_message"]
    result = await handler(agent, inp, log)
    assert result.conversation_id == "prompt-test"
    assert captured == [base + "\nCLOCK_1\n" + SHARED]


async def test_empty_base_uses_ha_default_instead_of_removing_it(ha):
    log, context, _, _ = prompt_log(ha)
    await log.async_provide_llm_data(context, None, "", SHARED)
    assert log.content[0].content == "HA_DEFAULT_BASE\nCLOCK_1\n" + SHARED


async def test_assembler_overwrites_router_prepopulated_system_message(ha):
    log, context, _, _ = prompt_log(ha)
    log.content[0] = ha.conv.SystemContent(content="ROUTER_REPLACEMENT")
    await log.async_provide_llm_data(context, None, "AGENT_BASE", SHARED)
    assert "ROUTER_REPLACEMENT" not in log.content[0].content
    assert log.content[0].content.startswith("AGENT_BASE\n")


async def test_tool_prompt_and_tool_object_are_preserved(ha):
    log, context, API, _ = prompt_log(ha)
    tool = SimpleNamespace(name="Yuvomi_Add", parameters={"name": "Café e\u0301"})
    instance = SimpleNamespace(api_prompt="EXISTING_TOOL_INSTRUCTIONS", tools=[tool])
    api = API()
    api.instance = instance
    await log.async_provide_llm_data(context, api, "AGENT_BASE", SHARED)
    assert log.content[0].content == "AGENT_BASE\nEXISTING_TOOL_INSTRUCTIONS\nCLOCK_1\n" + SHARED
    assert log.llm_api is instance and log.llm_api.tools[0] is tool


async def test_static_extra_is_after_dynamic_clock_and_not_repeated(ha):
    log, context, _, clock = prompt_log(ha)
    await log.async_provide_llm_data(context, None, "STATIC_BASE", SHARED)
    first = log.content[0].content
    clock[0] = "CLOCK_2"
    await log.async_provide_llm_data(context, None, "STATIC_BASE", SHARED)
    second = log.content[0].content
    assert first != second and second.count(SHARED) == 1
    assert second.index("CLOCK_2") < second.index(SHARED)


@pytest.mark.parametrize("empty", [None, ""])
async def test_empty_extra_does_not_clear_existing_chatlog_prompt(ha, empty):
    log, context, _, _ = prompt_log(ha)
    await log.async_provide_llm_data(context, None, "BASE", SHARED)
    await log.async_provide_llm_data(context, None, "BASE", empty)
    assert SHARED in log.content[0].content


async def test_extra_is_literal_not_a_second_template_render(ha):
    log, context, _, _ = prompt_log(ha)
    await log.async_provide_llm_data(context, None, "BASE", "{{ now() }} / é")
    assert log.content[0].content.endswith("{{ now() }} / é")


def test_openai_converter_keeps_composed_prompt_as_developer_message(ha):
    namespace = {"__name__": __name__, "conversation": ha.conv, "EasyInputMessageParam": dict}
    convert = load("core/openai_entity.py", ["_convert_content_to_param"], namespace)[
        "_convert_content_to_param"
    ]
    result = convert([ha.conv.SystemContent(content=SHARED)])
    assert result == [{"type": "message", "role": "developer", "content": SHARED}]


async def test_local_converter_keeps_composed_prompt_as_system_message(ha):
    namespace = {"__name__": __name__, "conversation": ha.conv, "ChatCompletionSystemMessageParam": dict}
    convert = load("local/entity.py", ["_convert_content_to_chat_message"], namespace)[
        "_convert_content_to_chat_message"
    ]
    result = await convert(SimpleNamespace(), ha.conv.SystemContent(content=SHARED), "prompt-test")
    assert result == {"role": "system", "content": SHARED}


@pytest.mark.parametrize("model", ["gemini-test", "gemma-test"])
async def test_google_request_assembly_preserves_prompt_or_explicit_fallback(ha, model):
    log, _, _, _ = prompt_log(ha)
    log.content[0] = ha.conv.SystemContent(content=SHARED)
    create = Mock(return_value=SimpleNamespace())
    config = SimpleNamespace()
    agent = SimpleNamespace(
        subentry=SimpleNamespace(data={"chat_model": model}),
        default_model=model,
        create_generate_content_config=lambda: config,
        _genai_client=SimpleNamespace(aio=SimpleNamespace(chats=SimpleNamespace(create=create))),
    )
    namespace = {
        "__name__": __name__,
        "conversation": ha.conv,
        "MAX_TOOL_ITERATIONS": 10,
        "CONF_USE_GOOGLE_SEARCH_TOOL": "google_search",
        "CONF_CHAT_MODEL": "chat_model",
        "Content": SimpleNamespace,
        "Part": SimpleNamespace(from_text=lambda **kw: SimpleNamespace(**kw)),
        "AutomaticFunctionCallingConfig": SimpleNamespace,
        "cast": lambda kind, value: value,
    }
    method = load("core/google_entity.py", ["_async_handle_chat_log"], namespace)["_async_handle_chat_log"]
    # max_iterations=0 captures the real provider config assembly without sending anything.
    await method(agent, log, max_iterations=0)
    request = create.call_args.kwargs
    if model.startswith("gemini"):
        assert request["config"].system_instruction == SHARED
    else:
        assert request["config"].system_instruction is None
        assert request["history"][0].parts[0].text == SHARED


def test_llama_cpp_variant_inherits_shared_prompt_handler(ha):
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "reference/prompt_compatibility/local/llama_cpp.py").read_text(encoding="utf-8"))
    mixin = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LlamaCppMixin"
    )
    assert "_async_handle_message" not in {getattr(node, "name", None) for node in mixin.body}
