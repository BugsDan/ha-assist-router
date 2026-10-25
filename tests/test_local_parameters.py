"""Safe Local OpenAI values, real request builders, and full-config fingerprints."""

import ast
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from jinja2 import Environment

from .test_prompt_compatibility import SHARED, load, prompt_log
from .test_prompt_management import inspector_fixture


def body(key="reasoning_effort", value="none"):
    return {"request_body_opts": {"request_body_parameters": [{"Key": key, "Value": value}]}}


def template(value="false", key="enable_thinking"):
    return {"chat_template_opts": {"chat_template_kwargs": [{"Key": key, "Value": value}]}}


SAFE = [
    {},
    body(),
    body(value="{{ 'none' }}"),
    template(),
    template("False"),
    template("{{ false }}"),
    body() | template(),
    body("chat_template_kwargs", "{'enable_thinking': False}"),
    body("chat_template_kwargs", "{{ {'enable_thinking': false} }}"),
]


@pytest.mark.parametrize("options", SAFE)
def test_precise_allowlist_accepts_constant_parameters_without_mutation(ha, options):
    from custom_components.assist_router.local_parameters import local_parameters_safe

    before = deepcopy(options)
    assert local_parameters_safe(options, llama_cpp=True)
    assert options == before


BLOCKED = [
    body("messages", "[]"),
    body("system", "old"),
    body("prompt", "old"),
    body("chat_template", "old"),
    body("tools", "[]"),
    body("unknown", "none"),
    body(value="low"),
    body(value="None"),
    body(value="'none'"),
    body(value=None),
    body(value="{{ states('sensor.effort') }}"),
    body(value="{{ 'none' if true else 'low' }}"),
    body(value="{{ 'none' | lower }}"),
    body(value="{{ r'none' }}"),
    body(value="{{ u'none' }}"),
    body(value="{{ '''none''' }}"),
    body(value="{{ 'none' # Python comment\n }}"),
    body(value="{% set x = 'none' %}{{ x }}"),
    template("true"),
    template("True"),
    template("0"),
    template("{{ states('sensor.flag') }}"),
    template(key="system_prompt"),
    template(key="chat_template"),
    template(key="unknown"),
    body("chat_template_kwargs", '{"enable_thinking": false}'),  # static HA string, not a dict
    body("chat_template_kwargs", "{'enable_thinking': False, 'system': 'old'}"),
    body("chat_template_kwargs", "{{ {'enable_thinking': false, 'messages': []} }}"),
    body("chat_template_kwargs", "{'enable_thinking': True}"),
    body("chat_template_kwargs", "{'enable_thinking': False, 'enable_thinking': False}"),
    body(" reasoning_effort", "none"),
    template(key="enable_thinking "),
    {"request_body_opts": None},
    {"request_body_opts": {"request_body_parameters": "none"}},
    {"chat_template_opts": {"chat_template_kwargs": {"enable_thinking": False}}},
    {"request_body_opts": {"request_body_parameters": [{"Key": "reasoning_effort"}]}},
    {"request_body_opts": {"request_body_parameters": [{"Key": "reasoning_effort", "Value": "none"}] * 2}},
    body("chat_template_kwargs", "{'enable_thinking': False}") | template(),
    template() | {"llamacpp_config": {"llamacpp_enable_thinking": True}},
    template() | {"llamacpp_config": {"llamacpp_enable_thinking": "false"}},
]


@pytest.mark.parametrize("options", BLOCKED, ids=[f"blocked_{i}" for i in range(len(BLOCKED))])
def test_unknown_dynamic_or_prompt_changing_parameters_fail_closed(ha, options):
    from custom_components.assist_router.local_parameters import local_parameters_safe

    assert not local_parameters_safe(options, llama_cpp=True)


def test_no_assumed_boolean_override_on_other_server_types_or_legacy_dicts(ha):
    from custom_components.assist_router.local_parameters import local_parameters_safe

    assert local_parameters_safe(body(), llama_cpp=False)
    assert not local_parameters_safe(template(), llama_cpp=False)
    assert not local_parameters_safe(
        body("chat_template_kwargs", "{'enable_thinking': False}"), llama_cpp=True, legacy_templates=True
    )
    assert local_parameters_safe(template(), llama_cpp=True, legacy_templates=True)


def local_namespace(ha):
    """Use exact pinned mixin/base request builders; no provider clients are loaded."""
    namespace = {"__name__": "custom_components.local_openai.entities.llama_cpp"}
    const_path = Path(__file__).resolve().parents[1] / "reference/prompt_compatibility/local/const.py"
    for node in ast.parse(const_path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    namespace[target.id] = node.value.value
    load("local/llama_cpp.py", ["LlamaCppMixin"], namespace)
    return namespace


def apply_policy(inspector, agent, ha):
    namespace = local_namespace(ha)
    method = namespace["LlamaCppMixin"]._get_extra_body_args
    agent._get_extra_body_args = MethodType(method, agent)
    path = Path(__file__).resolve().parents[1] / "reference/prompt_compatibility/local/llama_cpp.py"
    contract = inspector.contracts["local_openai"]
    contract["methods"]["_get_extra_body_args"] = {method.__module__: sha256(path.read_bytes()).hexdigest()}
    contract["parameter_policy"] = "local_openai_v1"


@pytest.mark.parametrize("options", [body(), body() | template(), body("messages", "[]")])
async def test_runtime_inspector_applies_policy_and_never_changes_target(ha, monkeypatch, options):
    inspector, entry, subentry, agent = inspector_fixture(ha, monkeypatch)
    apply_policy(inspector, agent, ha)
    subentry.data.update(options)
    before = deepcopy(subentry.data)
    snapshot = await inspector.inspect("conversation.alpha")
    assert snapshot.ready == ("messages" not in repr(options))
    assert subentry.data == before
    ha.hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.parametrize(
    "initial,changed",
    [
        (body(), body(value="{{ 'none' }}")),
        (template(), template("{{ false }}")),
        (body(), {}),
        (template(), {}),
    ],
)
async def test_allowed_parameters_stay_fingerprinted_and_require_new_review(
    ha, monkeypatch, initial, changed
):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    inspector, _, subentry, agent = inspector_fixture(ha, monkeypatch)
    apply_policy(inspector, agent, ha)
    subentry.data.update(initial)
    baseline = deepcopy(subentry.data)
    approved = await inspector.inspect("conversation.alpha")
    assert approved.ready
    settings = Settings.from_mapping(
        {
            "agents": [{"entity_id": "conversation.alpha"}],
            "prompt": {
                "enabled": True,
                "text": SHARED,
                "reviews": {"conversation.alpha": approved.fingerprint},
            },
        }
    )
    manager = PromptManager(settings, inspector)
    assert await manager.validate()
    subentry.data.pop("request_body_opts", None)
    subentry.data.pop("chat_template_opts", None)
    subentry.data.update(changed)
    current = await inspector.inspect("conversation.alpha")
    assert current.ready and current.fingerprint != approved.fingerprint
    assert not await manager.validate() and manager.last["reason"] == "review_changed_or_missing"
    assert initial.items() <= baseline.items()  # inspector did not canonicalize away raw values
    settings_data = settings.as_dict()
    settings_data["prompt"]["reviews"]["conversation.alpha"] = current.fingerprint
    reviewed_manager = PromptManager(Settings.from_mapping(settings_data), inspector)
    assert await reviewed_manager.validate()
    assert reviewed_manager.revision != manager.revision  # old conversations must start anew


@pytest.mark.parametrize("target", ["effort", "thinking", "native_thinking"])
async def test_changed_allowed_value_becomes_unsafe_even_with_manually_matching_digest(
    ha, monkeypatch, target
):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    inspector, _, subentry, agent = inspector_fixture(ha, monkeypatch)
    apply_policy(inspector, agent, ha)
    subentry.data.update(body() | template())
    approved = await inspector.inspect("conversation.alpha")
    if target == "effort":
        subentry.data["request_body_opts"]["request_body_parameters"][0]["Value"] = "high"
    elif target == "thinking":
        subentry.data["chat_template_opts"]["chat_template_kwargs"][0]["Value"] = "true"
    else:
        subentry.data["llamacpp_config"] = {"llamacpp_enable_thinking": True}
    changed = await inspector.inspect("conversation.alpha")
    assert changed.fingerprint != approved.fingerprint and changed.reason == "unsafe_request_overrides"
    settings = Settings.from_mapping(
        {
            "agents": [{"entity_id": "conversation.alpha"}],
            "prompt": {
                "enabled": True,
                "text": SHARED,
                "reviews": {"conversation.alpha": changed.fingerprint},
            },
        }
    )
    assert not await PromptManager(settings, inspector).validate()


@pytest.mark.parametrize(
    "options",
    [
        body() | template(),
        body() | template("{{ false }}"),
        body("chat_template_kwargs", "{{ {'enable_thinking': false} }}"),
    ],
)
async def test_actual_local_request_builders_preserve_prompt_and_send_safe_values(ha, options):
    """Actual Local code + Jinja2; HA's static result parsing is a host double."""
    environment = Environment()

    class Template:
        def __init__(self, text, hass):
            self.text = text

        def async_render(self):
            text = self.text
            if any(marker in text for marker in ("{{", "{%", "{#")):
                text = environment.from_string(text).render().strip()
            try:
                result = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return text
            return text if isinstance(result, str) else result

    namespace = local_namespace(ha)
    namespace.update(
        template=SimpleNamespace(Template=Template),
        conversation=ha.conv,
        ChatCompletionSystemMessageParam=dict,
        ChatCompletionUserMessageParam=dict,
        ChatCompletionContentPartTextParam=dict,
    )
    base_namespace = dict(namespace, __name__=__name__, _LOGGER=SimpleNamespace(debug=lambda *args: None))
    load(
        "local/entity.py",
        ["_get_extra_body_args", "_convert_content_to_chat_message", "_async_handle_chat_log"],
        base_namespace,
    )
    Base = type(
        "Base",
        (),
        {name: base_namespace[name] for name in ("_get_extra_body_args", "_convert_content_to_chat_message")},
    )

    class Agent(namespace["LlamaCppMixin"], Base):
        pass

    agent = object.__new__(Agent)
    agent.hass = ha.hass
    agent.subentry = SimpleNamespace(data=options)
    agent.options, agent.server_options = options, {}
    agent.entry = SimpleNamespace(runtime_data=object())
    agent._async_get_model = AsyncMock(return_value="test-model")
    agent._trim_history = lambda messages, count: messages
    agent._maybe_inject_context = AsyncMock(
        side_effect=lambda messages, method, tools, user: (messages, tools)
    )
    agent._run_agent_loop = AsyncMock()
    log, _, _, _ = prompt_log(ha)
    log.content[0] = ha.conv.SystemContent(content=SHARED)
    log.llm_api = None
    await base_namespace["_async_handle_chat_log"](agent, log)
    model_args = agent._run_agent_loop.call_args.args[1]
    assert model_args["messages"][0] == {"role": "system", "content": SHARED}
    assert model_args["extra_body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert model_args["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    if "reasoning_effort" in repr(options):
        assert model_args["extra_body"]["reasoning_effort"] == "none"
