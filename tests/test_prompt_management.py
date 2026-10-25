"""Opt-in configuration, pinned compatibility, revisions and no-side-effect gates."""

from copy import deepcopy
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from .test_config import flow_module, new_flow
from .test_router import add_agent, ask, setup_router

TEXT = "Gemeinsam: ä ö ü é e\u0301 🥐\nZweite Zeile\n"
DIGEST = "a" * 64


def enable(ha, router, text=TEXT, addition="Agent: Café e\u0301", reviews=None):
    from custom_components.assist_router.prompts import PromptManager, PromptSnapshot
    from custom_components.assist_router.settings import Settings

    config = router.runtime.settings.as_dict()
    config["prompt"] = {
        "enabled": True,
        "text": text,
        "reviews": reviews or dict.fromkeys(router.runtime.settings.agents, DIGEST),
    }
    config["agents"][0]["prompt_addition"] = addition
    router.runtime.settings = Settings.from_mapping(config)
    inspector = SimpleNamespace(inspect=AsyncMock(return_value=PromptSnapshot("ready", DIGEST)))
    router.runtime.prompts = PromptManager(router.runtime.settings, inspector)
    return inspector


async def test_disabled_preserves_exact_input_and_never_inspects(ha, settings_data):
    router = setup_router(ha, settings_data)
    agent = add_agent(ha, router.runtime.settings.agents[0])
    router.runtime.prompts.inspector = SimpleNamespace(inspect=AsyncMock(side_effect=AssertionError))
    for incoming in (None, "", TEXT):
        result = await ha.conv.async_converse(
            ha.hass, "Test", None, ha.Context(), "de", router.entity_id, extra_system_prompt=incoming
        )
        assert result.response.response_type != ha.intent.IntentResponseType.ERROR
        assert agent.calls[-1][0].extra_system_prompt == incoming
    router.runtime.prompts.inspector.inspect.assert_not_called()


async def test_enabled_stable_literal_unicode_and_follow_up(ha, settings_data):
    router = setup_router(ha, settings_data)
    agent = add_agent(ha, router.runtime.settings.agents[0], follow_up=True)
    inspector = enable(ha, router, text=TEXT + "{{ do_not_render }}")
    first = await ask(ha, router)
    await ask(ha, router, "Ja, Café e\u0301", first.conversation_id)
    expected = TEXT + "{{ do_not_render }}\n\nAgent: Café e\u0301\n\nZusatz: é ä ö ü e\u0301"
    assert [call[0].extra_system_prompt for call in agent.calls] == [expected, expected]
    assert all(call[0].conversation_id == first.conversation_id for call in agent.calls)
    assert router.runtime.ledger.sessions[first.conversation_id].pending_agent == agent.entity_id
    assert inspector.inspect.await_count == 12  # all three active targets, twice per turn
    assert first.response.data["nested"]["tool_args"]["name"] == "Café e\u0301 🥐"


@pytest.mark.parametrize(
    "reason", ["unknown_source", "base_not_neutral", "agent_not_loaded", "unsupported_integration", "ready"]
)
async def test_any_active_unreviewed_target_blocks_globally_before_health(ha, settings_data, reason):
    from custom_components.assist_router.prompts import PromptSnapshot

    router = setup_router(ha, settings_data)
    agents = [add_agent(ha, entity_id) for entity_id in router.runtime.settings.agents]
    inspector = enable(ha, router)
    inspector.inspect.side_effect = [PromptSnapshot("ready", DIGEST), PromptSnapshot(reason, "b" * 64)]
    result = await ask(ha, router)
    assert result.response.response_type == ha.intent.IntentResponseType.ERROR
    assert not any(agent.calls for agent in agents)
    router.runtime.health.check.assert_not_awaited()
    state = router.runtime.ledger.sessions[result.conversation_id]
    assert state.prompt_stale and not state.blocked


async def test_config_drift_during_health_await_never_dispatches(ha, settings_data):
    from custom_components.assist_router.prompts import PromptSnapshot

    router = setup_router(ha, settings_data)
    agent = add_agent(ha, router.runtime.settings.agents[0])
    inspector = enable(ha, router)
    inspector.inspect.side_effect = [
        *[PromptSnapshot("ready", DIGEST)] * 3,
        PromptSnapshot("ready", "b" * 64),
    ]
    result = await ask(ha, router)
    assert result.response.response_type == ha.intent.IntentResponseType.ERROR and not agent.calls
    router.runtime.health.check.assert_awaited_once()


async def test_inspection_exception_is_fail_closed_without_leaking_secret(ha, settings_data):
    router = setup_router(ha, settings_data)
    agent = add_agent(ha, router.runtime.settings.agents[0])
    inspector = enable(ha, router)
    inspector.inspect.side_effect = RuntimeError("secret-token")
    result = await ask(ha, router)
    assert not agent.calls and "secret-token" not in repr(result)
    assert router.runtime.prompts.last["reason"] == "inspection_error"


@pytest.mark.parametrize("change", ["shared", "addition", "review", "disable"])
async def test_prompt_changes_require_new_conversation_with_same_ledger(ha, settings_data, change):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    router = setup_router(ha, settings_data)
    agent = add_agent(ha, router.runtime.settings.agents[0])
    inspector = enable(ha, router)
    first = await ask(ha, router)
    before = len(agent.calls)
    config = router.runtime.settings.as_dict()
    if change == "shared":
        config["prompt"]["text"] += " changed"
    elif change == "addition":
        config["agents"][0]["prompt_addition"] += " changed"
    elif change == "review":
        config["prompt"]["reviews"][agent.entity_id] = "b" * 64
        from custom_components.assist_router.prompts import PromptSnapshot

        inspector.inspect.side_effect = lambda entity_id: PromptSnapshot(
            "ready", "b" * 64 if entity_id == agent.entity_id else DIGEST
        )
    else:
        config["prompt"]["enabled"] = False
    router.runtime.settings = Settings.from_mapping(config)
    router.runtime.prompts = PromptManager(router.runtime.settings, inspector)
    old = await ask(ha, router, cid=first.conversation_id)
    assert old.response.response_type == ha.intent.IntentResponseType.ERROR and len(agent.calls) == before
    fresh = await ask(ha, router)
    assert fresh.conversation_id != first.conversation_id and len(agent.calls) == before + 1
    # Restoring settings does not un-stale a rejected conversation.
    state = router.runtime.ledger.sessions[first.conversation_id]
    assert state.prompt_stale and not state.blocked


async def test_enabling_on_existing_chat_log_after_lost_ledger_rejected(ha, settings_data):
    from custom_components.assist_router.runtime import Ledger

    router = setup_router(ha, settings_data)
    agent = add_agent(ha, router.runtime.settings.agents[0])
    first = await ask(ha, router)
    router.runtime.ledger = Ledger()
    enable(ha, router)
    result = await ask(ha, router, cid=first.conversation_id)
    assert result.response.response_type == ha.intent.IntentResponseType.ERROR and len(agent.calls) == 1


async def test_enabled_dispatch_failure_still_blocks_without_fallback(ha, settings_data):
    router = setup_router(ha, settings_data)

    async def ambiguous(*args):
        raise TimeoutError("tool may have run")

    agent = add_agent(ha, router.runtime.settings.agents[0], handler=ambiguous)
    next_agent = add_agent(ha, router.runtime.settings.agents[1])
    enable(ha, router)
    result = await ask(ha, router)
    enable(ha, router, text="changed")
    await ask(ha, router, cid=result.conversation_id)
    assert len(agent.calls) == 1 and not next_agent.calls
    assert router.runtime.ledger.sessions[result.conversation_id].blocked


async def test_health_fallback_keeps_addition_bound_to_entity(ha, settings_data):
    router = setup_router(ha, settings_data, ready=False)
    local = add_agent(ha, router.runtime.settings.agents[0])
    cloud = add_agent(ha, router.runtime.settings.agents[1])
    enable(ha, router)
    await ask(ha, router)
    assert not local.calls and len(cloud.calls) == 1
    assert cloud.calls[0][0].extra_system_prompt == TEXT + "\n\nZusatz: é ä ö ü e\u0301"


def test_revision_ignores_order_health_and_disabled_additions(ha, settings_data):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    router = setup_router(ha, settings_data)
    enable(ha, router)
    config = router.runtime.settings.as_dict()
    config["agents"].reverse()
    config["agents"][-1]["health"]["timeout"] = 0.2
    assert PromptManager(Settings.from_mapping(config)).revision == router.runtime.prompts.revision
    assert router.runtime.prompts.compose("conversation.alpha", None) == TEXT + "\n\nAgent: Café e\u0301"


class InspectedAgent:
    """Source-file allowlisting is tested with a private test-only contract."""

    async def _async_handle_message(self):
        pass

    async def _async_handle_chat_log(self):
        pass

    def _get_extra_body_args(self):
        pass


def inspector_fixture(ha, monkeypatch):
    from custom_components.assist_router.prompts import NEUTRAL_BASELINE, PromptInspector

    flow_module(ha, monkeypatch)
    entity_id = "conversation.alpha"
    subentry = SimpleNamespace(
        subentry_type="conversation",
        data={"prompt": NEUTRAL_BASELINE, "model": "m", "llm_hass_api": ["assist"]},
    )
    entry = SimpleNamespace(
        entry_id="target",
        domain="local_openai",
        data={"api_key": "secret", "server": "http://local/v1"},
        options={},
        subentries={"sub": subentry},
    )
    ha.hass.registry_entries = {
        entity_id: SimpleNamespace(config_entry_id="target", config_subentry_id="sub", platform=entry.domain)
    }
    ha.hass.config_entries = SimpleNamespace(
        async_get_entry=lambda entry_id: entry, async_update_entry=Mock()
    )
    ha.hass.async_add_executor_job = AsyncMock(side_effect=lambda function, *args: function(*args))
    agent = InspectedAgent()
    agent.entry, agent.subentry = entry, subentry
    ha.hass.agents[entity_id] = agent
    digest = sha256(Path(__file__).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    contract = {
        "domains": {
            entry.domain: {
                "methods": dict.fromkeys(
                    ("_async_handle_message", "_async_handle_chat_log"), {__name__: digest}
                )
            }
        }
    }
    return PromptInspector(ha.hass, contract), entry, subentry, agent


async def test_readonly_inspector_hashes_source_and_all_config_without_exposing_it(ha, monkeypatch):
    inspector, entry, subentry, _ = inspector_fixture(ha, monkeypatch)
    snapshot = await inspector.inspect("conversation.alpha")
    assert snapshot.ready and len(snapshot.fingerprint) == 64 and "secret" not in repr(snapshot)
    for data in (entry.data, entry.options, subentry.data):
        before = await inspector.inspect("conversation.alpha")
        data["changed"] = "ä é e\u0301"
        after = await inspector.inspect("conversation.alpha")
        assert after.fingerprint != before.fingerprint and after.ready
    assert ha.hass.async_add_executor_job.await_count == 1  # source only cached, configuration never cached
    entry.data["api_key"] = "rotated"
    assert (await inspector.inspect("conversation.alpha")).fingerprint != snapshot.fingerprint
    ha.hass.config_entries.async_update_entry.assert_not_called()


async def test_inspector_rechecks_binding_after_executor_yield(ha, monkeypatch):
    inspector, entry, subentry, _ = inspector_fixture(ha, monkeypatch)

    def replacing_job(function, *args):
        result = function(*args)
        entry.subentries["sub"] = deepcopy(subentry)
        return result

    ha.hass.async_add_executor_job.side_effect = replacing_job
    assert (await inspector.inspect("conversation.alpha")).reason == "reload_required"


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("prompt", "base_not_neutral"),
        ("source", "unknown_source"),
        ("domain", "unsupported_integration"),
        ("registry", "unknown_config"),
        ("loaded", "reload_required"),
        ("opaque", "opaque_config"),
    ],
)
async def test_inspector_rejects_unknown_changed_or_non_neutral_configuration(ha, monkeypatch, kind, reason):
    inspector, entry, subentry, agent = inspector_fixture(ha, monkeypatch)
    if kind == "prompt":
        subentry.data["prompt"] = "Old conflicting rules"
    elif kind == "source":
        inspector.contracts[entry.domain]["methods"]["_async_handle_message"] = {__name__: "0" * 64}
    elif kind == "domain":
        entry.domain = "unknown"
    elif kind == "registry":
        ha.hass.registry_entries = {}
    elif kind == "loaded":
        agent.subentry = deepcopy(subentry)
    else:
        entry.data["opaque"] = object()
    assert (await inspector.inspect("conversation.alpha")).reason == reason
    ha.hass.config_entries.async_update_entry.assert_not_called()


async def test_v11_migration_is_default_off_and_only_own_entry_updated(ha, settings_data):
    module = import_module("custom_components.assist_router")
    update = Mock()
    ha.hass.config_entries = SimpleNamespace(async_update_entry=update)
    entry = SimpleNamespace(version=2, data={}, options=deepcopy(settings_data))
    assert await module.async_migrate_entry(ha.hass, entry)
    update.assert_called_once()
    assert update.call_args.args == (entry,)
    result = update.call_args.kwargs
    assert result["version"] == 3 and not result["options"]["prompt"]["enabled"]
    assert [item["entity_id"] for item in result["options"]["agents"]] == [
        item["entity_id"] for item in settings_data["agents"]
    ]
    assert (
        result["options"]["agents"][0]["health"]["model_key"]
        == settings_data["agents"][0]["health"]["model_key"]
    )


async def test_ui_opt_in_requires_review_and_never_migrates_targets(ha, monkeypatch):
    from custom_components.assist_router.prompts import PromptSnapshot

    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": ["conversation.a", "conversation.b"]})
    result = await flow.async_step_shared_prompt({"enabled": True, "text": TEXT})
    assert result["errors"]["base"] == "acknowledge_additive"
    values = result["data_schema"]({"enabled": True, "text": TEXT, "acknowledge_additive": True})
    assert values["text"] == TEXT
    assert any(
        getattr(value, "config", {}).get("multiline") for value in result["data_schema"].schema.values()
    )
    await flow.async_step_shared_prompt(values)
    await flow.async_step_agent_prompt({"entity_id": "conversation.b"})
    await flow.async_step_agent_prompt_text({"text": "Ergänzung é\nü"})
    inspector = SimpleNamespace(inspect=AsyncMock(return_value=PromptSnapshot("ready", DIGEST)))
    flow._inspector = inspector
    assert (await flow.async_step_finish())["errors"]["base"] == "prompt_review_required"
    for entity_id in flow._ids():
        form = await flow.async_step_prompt_review({"entity_id": entity_id})
        assert form["description_placeholders"]["fingerprint"] == DIGEST
        assert (await flow.async_step_prompt_review_confirm({"confirm": True}))["type"] == "menu"
    await flow.async_step_order({"agent_order": ["conversation.b", "conversation.a"]})
    saved = await flow.async_step_finish()
    assert saved["options"]["prompt"]["enabled"] and saved["options"]["prompt"]["text"] == TEXT
    assert saved["options"]["agents"][0]["prompt_addition"] == "Ergänzung é\nü"
    assert saved["options"]["prompt"]["reviews"] == {entity_id: DIGEST for entity_id in flow._ids()}


async def test_review_ui_rejects_prompt_changed_while_form_open(ha, monkeypatch):
    from custom_components.assist_router.prompts import PromptSnapshot

    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": ["conversation.a"]})
    flow._inspector = SimpleNamespace(inspect=AsyncMock(return_value=PromptSnapshot("ready", DIGEST)))
    await flow.async_step_prompt_review({"entity_id": "conversation.a"})
    flow._inspector.inspect.return_value = PromptSnapshot("ready", "b" * 64)
    assert (await flow.async_step_prompt_review_confirm({"confirm": True}))["errors"][
        "base"
    ] == "prompt_changed"
    flow._inspector.inspect.return_value = PromptSnapshot("base_not_neutral", DIGEST)
    assert (await flow.async_step_prompt_review_confirm({"confirm": True}))["errors"][
        "base"
    ] == "prompt_not_compatible"
    assert not flow._draft["prompt"]["reviews"]


@pytest.mark.parametrize("value", [None, 42, "x" * 32769], ids=["none", "number", "too_long"])
def test_invalid_prompt_rejected_without_coercing(ha, value):
    from custom_components.assist_router.settings import PromptSettings

    with pytest.raises(ValueError, match="invalid_prompt"):
        PromptSettings.from_mapping({"text": value})


async def test_diagnostics_contains_fingerprints_but_no_prompt_or_secret(ha, settings_data):
    from custom_components.assist_router.diagnostics import async_get_config_entry_diagnostics

    router = setup_router(ha, settings_data)
    enable(ha, router)
    await router.runtime.prompts.validate()
    diagnostic = await async_get_config_entry_diagnostics(
        ha.hass, SimpleNamespace(runtime_data=router.runtime)
    )
    assert diagnostic["prompt"]["enabled"] and DIGEST in repr(diagnostic)
    assert TEXT not in repr(diagnostic) and "Agent: Café" not in repr(diagnostic)


@pytest.mark.parametrize(
    "options",
    [
        {"request_body_opts": {"request_body_parameters": [{"Key": "messages", "Value": "[]"}]}},
        {"chat_template_opts": {"chat_template_kwargs": [{"Key": "system", "Value": "old rules"}]}},
        {"request_body_opts": "opaque"},
    ],
)
async def test_local_custom_request_overrides_rejected(ha, monkeypatch, options):
    inspector, _, subentry, _ = inspector_fixture(ha, monkeypatch)
    contract = inspector.contracts["local_openai"]
    contract["parameter_policy"] = "local_openai_v1"
    contract["methods"]["_get_extra_body_args"] = contract["methods"]["_async_handle_message"]
    subentry.data.update(options)
    assert (await inspector.inspect("conversation.alpha")).reason == "unsafe_request_overrides"


async def test_installed_chatlog_source_must_match_pinned_reference(ha, monkeypatch):
    from custom_components.assist_router import prompts

    ha.hass.async_add_executor_job = AsyncMock(side_effect=lambda function, *args: function(*args))
    reference = Path(__file__).resolve().parents[1] / "reference/prompt_compatibility/core/chat_log.py"
    monkeypatch.setattr(prompts.inspect, "getsourcefile", lambda obj: str(reference))
    inspector = await prompts.async_make_inspector(ha.hass)
    assert set(inspector.contracts) == {
        "local_openai",
        "openai_conversation",
        "google_generative_ai_conversation",
    }
    original_read = Path.read_text

    def changed_read(path, *args, **kwargs):
        return original_read(path, *args, **kwargs) + ("\n# update\n" if path == reference else "")

    monkeypatch.setattr(Path, "read_text", changed_read)
    inspector = await prompts.async_make_inspector(ha.hass)
    assert not inspector.contracts and not inspector.host_compatible
    assert (await inspector.inspect("conversation.alpha")).reason == "unknown_ha_source"


async def test_unload_during_second_review_does_not_dispatch(ha, settings_data):
    from custom_components.assist_router.prompts import PromptSnapshot

    router = setup_router(ha, settings_data)
    agent = add_agent(ha, router.runtime.settings.agents[0])
    inspector = enable(ha, router)
    count = 0

    async def check(entity_id):
        nonlocal count
        count += 1
        if count == 4:
            router.runtime.active = False
        return PromptSnapshot("ready", DIGEST)

    inspector.inspect.side_effect = check
    result = await ask(ha, router)
    assert result.response.response_type == ha.intent.IntentResponseType.ERROR and not agent.calls


async def test_rejected_conversation_stays_stale_after_configuration_restored(ha, settings_data):
    from custom_components.assist_router.prompts import PromptSnapshot

    router = setup_router(ha, settings_data)
    agent = add_agent(ha, router.runtime.settings.agents[0])
    inspector = enable(ha, router)
    first = await ask(ha, router)
    inspector.inspect.return_value = PromptSnapshot("base_not_neutral", DIGEST)
    await ask(ha, router, cid=first.conversation_id)
    inspector.inspect.return_value = PromptSnapshot("ready", DIGEST)
    await ask(ha, router, cid=first.conversation_id)
    assert len(agent.calls) == 1
    await ask(ha, router)
    assert len(agent.calls) == 2
