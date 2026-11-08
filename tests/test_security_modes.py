"""Persistent Standard trust, conservative migration, and unchanged Strict gates."""

import json
from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from .test_config import new_flow
from .test_prompt_management import inspector_fixture
from .test_router import add_agent, ask, setup_router


def standard_fixture(ha, monkeypatch):
    inspector, entry, subentry, agent = inspector_fixture(ha, monkeypatch)
    inspector.mode = "standard"
    inspector.host_compatible = False  # Standard deliberately has no exact HA source gate.
    entry.data["base_url"] = "http://backend.example:1234/v1"
    ha.hass.registry_entries["conversation.alpha"].unique_id = "stable-agent-subentry"
    inspector.source_hashes = Mock(side_effect=AssertionError("Standard read source files"))
    return inspector, entry, subentry, agent


def configuration(stamp, mode="standard"):
    return {
        "agents": [{"entity_id": "conversation.alpha"}],
        "prompt": {
            "enabled": True,
            "text": "Gemeinsam: Café e\u0301\nö ü",
            "mode": mode,
            "approvals": {"conversation.alpha": stamp},
        },
    }


@pytest.mark.parametrize(
    ("field", "changed"), [("base_url", "https://replacement.example/v1"), ("api_key", "rotated")]
)
async def test_stale_options_cannot_mask_local_connection_change(ha, monkeypatch, field, changed):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    inspector, entry, _, _ = standard_fixture(ha, monkeypatch)
    initial = await inspector.inspect("conversation.alpha")
    assert initial.ready
    manager = PromptManager(Settings.from_mapping(configuration(initial.fingerprint)), inspector)
    entry.options[field] = entry.data[field]
    assert await manager.validate()

    entry.data[field] = changed
    assert not await manager.validate()
    assert manager.last["reason"] == "conflicting_backend_config"
    assert manager.last["category"] == "security"
    assert changed not in repr(manager.last)

    del entry.options[field]
    assert not await manager.validate()
    assert manager.last["reason"] == "agent_or_backend_changed"


async def test_weaviate_credential_rotation_changes_local_approval(ha, monkeypatch):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    inspector, entry, subentry, _ = standard_fixture(ha, monkeypatch)
    retrieval = {"weaviate_host": "https://retrieval.example", "weaviate_api_key": "first-key"}
    entry.data["weaviate_options"] = retrieval
    initial = await inspector.inspect("conversation.alpha")
    assert initial.ready
    manager = PromptManager(Settings.from_mapping(configuration(initial.fingerprint)), inspector)
    assert await manager.validate()
    subentry.data.update(model="updated-model", temperature=0.6)
    assert await manager.validate()

    entry.options["weaviate_options"] = retrieval.copy()
    retrieval["weaviate_api_key"] = "replacement-key"
    assert not await manager.validate()
    assert manager.last["reason"] == "conflicting_backend_config"
    del entry.options["weaviate_options"]
    assert not await manager.validate()
    assert manager.last["reason"] == "agent_or_backend_changed"
    assert "replacement-key" not in repr(manager.last)
    assert "first-key" not in repr(manager.last)


def test_local_options_cannot_supply_missing_client_url(ha, monkeypatch):
    inspector, entry, subentry, _ = standard_fixture(ha, monkeypatch)
    entry.options["base_url"] = entry.data.pop("base_url")
    registry = ha.hass.registry_entries["conversation.alpha"]
    assert inspector.inspect_standard("conversation.alpha", registry, entry, subentry).reason == (
        "conflicting_backend_config"
    )


async def test_standard_approval_survives_serialized_restart_and_model_parameter_changes(ha, monkeypatch):
    from custom_components.assist_router.prompts import PromptInspector, PromptManager
    from custom_components.assist_router.settings import Settings

    inspector, entry, subentry, agent = standard_fixture(ha, monkeypatch)
    first = await inspector.inspect("conversation.alpha")
    assert first.ready and not first.source_fingerprints
    persisted = json.loads(json.dumps(configuration(first.fingerprint)))
    before = deepcopy(entry.data)
    old_revision = PromptManager(Settings.from_mapping(persisted)).revision
    for model in ("openai/gpt-oss-20b", "Qwen/Qwen3.8", "any/new-model"):
        subentry.data.update(model=model, temperature=0.42, max_tokens=2048)
        subentry.data["request_body_opts"] = {
            "request_body_parameters": [{"Key": "reasoning_effort", "Value": "high"}]
        }
        # A new inspector/manager simulates loss of all in-memory inspection caches.
        restarted = PromptInspector(ha.hass, {"domains": inspector.contracts}, "standard")
        current = await restarted.inspect("conversation.alpha")
        assert current.ready and current.fingerprint == first.fingerprint and current.model == model
        manager = PromptManager(Settings.from_mapping(persisted), restarted)
        assert await manager.validate() and manager.revision == old_revision
        assert "model_parameters_present" in manager.last["warnings"]
    assert entry.data == before
    ha.hass.config_entries.async_update_entry.assert_not_called()
    inspector.source_hashes.assert_not_called()


async def test_standard_update_replaces_methods_without_new_approval(ha, monkeypatch):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    inspector, entry, subentry, agent = standard_fixture(ha, monkeypatch)
    first = await inspector.inspect("conversation.alpha")
    # Changed source layout, callable types and version are irrelevant to Standard.
    agent._async_handle_message = None
    agent._async_handle_chat_log = lambda: None
    entry.data["integration_version"] = "future-update"
    subentry.data["llamacpp_config"] = {"llamacpp_thinking_mode": "first_loop"}
    manager = PromptManager(Settings.from_mapping(configuration(first.fingerprint)), inspector)
    assert await manager.validate()
    inspector.source_hashes.assert_not_called()


async def test_integration_reload_with_new_objects_keeps_persisted_trust(ha, monkeypatch):
    inspector, entry, _, _ = standard_fixture(ha, monkeypatch)
    first = await inspector.inspect("conversation.alpha")
    replacement = deepcopy(entry)
    ha.hass.config_entries.async_get_entry = lambda _: replacement
    ha.hass.agents["conversation.alpha"] = SimpleNamespace(
        entry=replacement, subentry=replacement.subentries["sub"]
    )
    current = await inspector.inspect("conversation.alpha")
    assert current.ready and current.fingerprint == first.fingerprint


async def test_model_change_preserves_followup_context_and_unicode(ha, monkeypatch):
    from custom_components.assist_router.prompts import PromptManager

    inspector, entry, subentry, _ = standard_fixture(ha, monkeypatch)
    stamp = (await inspector.inspect("conversation.alpha")).fingerprint
    router = setup_router(ha, configuration(stamp))
    router.runtime.prompts = PromptManager(router.runtime.settings, inspector)
    leaf = add_agent(ha, "conversation.alpha", follow_up=True)
    leaf.entry, leaf.subentry = entry, subentry
    first = await ask(ha, router, "Äpfel Café e\u0301")
    subentry.data.update(model="Qwen/Qwen3.8", temperature=0.6)
    second = await ask(ha, router, "Ja, Öl ü é e\u0301", first.conversation_id)
    assert second.conversation_id == first.conversation_id and len(leaf.calls) == 2
    assert leaf.calls[1][0].text == "Ja, Öl ü é e\u0301"
    # HA copies the ChatLog between turns; history and IDs must survive, not
    # Python object identity (async_get_chat_log uses dataclasses.replace).
    first_log, second_log = leaf.calls[0][1], leaf.calls[1][1]
    assert first_log.conversation_id == second_log.conversation_id
    assert second_log.content[: len(first_log.content)] == first_log.content
    assert [item.content for item in second_log.content if item.role == "user"] == [
        "Äpfel Café e\u0301",
        "Ja, Öl ü é e\u0301",
    ]
    assert router.runtime.ledger.sessions[first.conversation_id].pending_agent == "conversation.alpha"
    assert leaf.calls[1][0].extra_system_prompt.startswith("Gemeinsam: Café e\u0301\nö ü")


async def test_ordinary_update_adding_empty_defaults_preserves_backend_trust(ha, monkeypatch):
    inspector, entry, subentry, _ = standard_fixture(ha, monkeypatch)
    first = await inspector.inspect("conversation.alpha")
    entry.data.update(server_type="generic", custom_headers={"server_headers": []}, weaviate_options={})
    entry.options.update(unrelated_ui_setting=True)
    subentry.data.update(max_message_history=10, strip_emojis=True, parallel_tool_calls=False)
    current = await inspector.inspect("conversation.alpha")
    assert current.ready and current.fingerprint == first.fingerprint


async def test_backend_canonicalization_keeps_equivalent_urls_but_not_distinct_paths(ha, monkeypatch):
    inspector, entry, _, _ = standard_fixture(ha, monkeypatch)
    entry.data["base_url"] = "http://Backend.Example:80/v1"
    before = await inspector.inspect("conversation.alpha")
    entry.data["base_url"] = "http://backend.example/v1/"
    assert (await inspector.inspect("conversation.alpha")).fingerprint == before.fingerprint
    entry.data["base_url"] = "http://backend.example/v1//"
    assert (await inspector.inspect("conversation.alpha")).fingerprint != before.fingerprint


async def test_approved_unloaded_agent_can_fall_back_without_bypassing_config_gate(ha, monkeypatch):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    inspector, _, subentry, _ = standard_fixture(ha, monkeypatch)
    stamp = (await inspector.inspect("conversation.alpha")).fingerprint
    ha.hass.agents.pop("conversation.alpha")
    manager = PromptManager(Settings.from_mapping(configuration(stamp)), inspector)
    assert await manager.validate()
    assert "agent_not_loaded" in manager.last["warnings"]
    subentry.data["prompt"] = "not neutral"
    assert not await manager.validate() and manager.last["reason"] == "base_not_neutral"


async def test_standard_routes_to_next_approved_agent_when_first_is_unloaded(ha, monkeypatch):
    from custom_components.assist_router.prompts import NEUTRAL_BASELINE, PromptManager

    inspector, entry, _, _ = standard_fixture(ha, monkeypatch)
    beta = SimpleNamespace(subentry_type="conversation", data={"prompt": NEUTRAL_BASELINE})
    entry.subentries["beta"] = beta
    ha.hass.registry_entries["conversation.beta"] = SimpleNamespace(
        config_entry_id=entry.entry_id, config_subentry_id="beta", unique_id="beta", platform="local_openai"
    )
    ha.hass.agents["conversation.beta"] = SimpleNamespace(entry=entry, subentry=beta)
    approvals = {
        entity_id: (await inspector.inspect(entity_id)).fingerprint
        for entity_id in ("conversation.alpha", "conversation.beta")
    }
    config = configuration(approvals["conversation.alpha"])
    config["agents"].append({"entity_id": "conversation.beta"})
    config["prompt"]["approvals"] = approvals
    router = setup_router(ha, config)
    router.runtime.prompts = PromptManager(router.runtime.settings, inspector)
    ha.hass.agents.pop("conversation.alpha")
    leaf = add_agent(ha, "conversation.beta")
    leaf.entry, leaf.subentry = entry, beta
    result = await ask(ha, router)
    assert len(leaf.calls) == 1 and result.response.response_type != ha.intent.IntentResponseType.ERROR
    assert router.runtime.last_agent == "conversation.beta"


async def test_real_standard_review_ui_persists_only_after_confirm_and_finish(ha, monkeypatch):
    inspector, entry, _, _ = standard_fixture(ha, monkeypatch)
    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": ["conversation.alpha"]})
    flow._inspector = inspector
    await flow.async_step_shared_prompt(
        {"enabled": True, "text": "Gemeinsam: é", "acknowledge_additive": True}
    )
    await flow.async_step_prompt_review({"entity_id": "conversation.alpha"})
    assert (await flow.async_step_prompt_review_confirm({"confirm": False}))["errors"][
        "base"
    ] == "prompt_confirm_required"
    entry.data["base_url"] = "https://new-backend.example/v1"
    assert (await flow.async_step_prompt_review_confirm({"confirm": True}))["errors"][
        "base"
    ] == "prompt_changed"
    assert flow._draft["prompt"]["approvals"] == {}
    await flow.async_step_prompt_review_confirm({"confirm": True})
    saved = await flow.async_step_finish()
    assert saved["type"] == "create_entry"
    assert saved["options"]["prompt"]["mode"] == "standard"
    assert len(saved["options"]["prompt"]["approvals"]["conversation.alpha"]) == 64
    ha.hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.parametrize(
    "change", ["url", "entry", "subentry", "unique", "headers", "server_type", "credential", "tenant"]
)
async def test_standard_changed_identity_or_backend_requires_confirmation(ha, monkeypatch, change):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    inspector, entry, subentry, agent = standard_fixture(ha, monkeypatch)
    first = await inspector.inspect("conversation.alpha")
    if change == "url":
        entry.data["base_url"] = "https://different.example/v1"
    elif change == "entry":
        entry.entry_id = "different-entry"
    elif change == "subentry":
        entry.subentries["new-subentry"] = entry.subentries.pop("sub")
        ha.hass.registry_entries["conversation.alpha"].config_subentry_id = "new-subentry"
    elif change == "unique":
        ha.hass.registry_entries["conversation.alpha"].unique_id = "replacement"
    elif change == "headers":
        entry.data["custom_headers"] = {"server_headers": [{"Key": "Host", "Value": "new.example"}]}
    elif change == "credential":
        entry.data["api_key"] = "rotated"
    elif change == "tenant":
        entry.data["project"] = "different-project"
    else:
        entry.data["server_type"] = "new-provider-type"
    manager = PromptManager(Settings.from_mapping(configuration(first.fingerprint)), inspector)
    assert not await manager.validate()
    assert manager.last["reason"] == "agent_or_backend_changed"
    assert "different.example" not in repr(manager.last)


@pytest.mark.parametrize(
    "extra,expected",
    [
        ({"prompt": "Conflicting business rules"}, "base_not_neutral"),
        ({"system_prompt": "Other rules"}, "unsafe_request_overrides"),
        (
            {"request_body_opts": {"request_body_parameters": [{"Key": "messages", "Value": "[]"}]}},
            "unclassified_request_override",
        ),
        (
            {"request_body_opts": {"request_body_parameters": [{"Key": "tools", "Value": "[]"}]}},
            "unclassified_request_override",
        ),
        (
            {"chat_template_opts": {"chat_template_kwargs": [{"Key": "system", "Value": "other"}]}},
            "unsafe_request_overrides",
        ),
        (
            {
                "request_body_opts": {
                    "request_body_parameters": [{"Key": "temperature", "Value": "{{ states('secret') }}"}]
                }
            },
            "dynamic_request_override",
        ),
        ({"request_body_opts": "invalid"}, "invalid_parameter_config"),
    ],
)
async def test_standard_safety_violations_remain_blocking(ha, monkeypatch, extra, expected):
    inspector, _, subentry, _ = standard_fixture(ha, monkeypatch)
    subentry.data.update(extra)
    before = deepcopy(subentry.data)
    result = await inspector.inspect("conversation.alpha")
    assert not result.ready and result.reason == expected
    assert subentry.data == before


async def test_thinking_conflict_warns_without_invalidating_approval(ha, monkeypatch):
    inspector, _, subentry, _ = standard_fixture(ha, monkeypatch)
    first = await inspector.inspect("conversation.alpha")
    subentry.data.update(
        {
            "chat_template_opts": {"chat_template_kwargs": [{"Key": "enable_thinking", "Value": "false"}]},
            "llamacpp_config": {"llamacpp_thinking_mode": "always"},
        }
    )
    result = await inspector.inspect("conversation.alpha")
    assert result.ready and result.fingerprint == first.fingerprint
    assert "thinking_settings_may_override_request" in result.warnings


async def test_standard_inspector_never_reads_ha_or_agent_source(ha, monkeypatch):
    from custom_components.assist_router import prompts

    monkeypatch.setattr(prompts.inspect, "getsourcefile", Mock(side_effect=AssertionError))
    ha.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *args: fn(*args))
    inspector = await prompts.async_make_inspector(ha.hass, "standard")
    assert inspector.mode == "standard"
    prompts.inspect.getsourcefile.assert_not_called()


async def test_mode_switch_requires_explicit_confirmation_and_separate_approval(ha, monkeypatch):
    _, flow = new_flow(ha, monkeypatch)
    await flow.async_step_user({"agent_order": ["conversation.alpha"]})
    assert flow._draft["prompt"]["mode"] == "standard"
    await flow.async_step_security_mode({"mode": "strict"})
    flow._draft["prompt"]["reviews"] = {"conversation.alpha": "a" * 64}
    for value in ({"mode": "standard"}, {"mode": "standard", "confirm_standard": False}):
        form = await flow.async_step_security_mode(value)
        assert form["errors"]["base"] == "confirm_standard_required"
        assert flow._draft["prompt"]["mode"] == "strict"
    await flow.async_step_security_mode({"mode": "standard", "confirm_standard": True})
    assert flow._draft["prompt"]["approvals"] == {}
    assert flow._draft["prompt"]["reviews"] == {"conversation.alpha": "a" * 64}


@pytest.mark.parametrize("enabled", [False, True])
async def test_121_migration_preserves_prompt_reviews_routes_health_and_ledger(ha, settings_data, enabled):
    from custom_components.assist_router.settings import Settings

    module = import_module("custom_components.assist_router")
    config = deepcopy(settings_data)
    config["prompt"] = {
        "enabled": enabled,
        "text": "Café ö\ne\u0301",
        "reviews": {"conversation.alpha": "a" * 64},
    }
    original = deepcopy(config)
    entry = SimpleNamespace(version=3, minor_version=1, data={}, options=config)
    ha.hass.config_entries = SimpleNamespace(async_update_entry=Mock())
    ha.hass.data["assist_router"] = {"existing-ledger": object()}
    ledger = dict(ha.hass.data["assist_router"])
    assert await module.async_migrate_entry(ha.hass, entry)
    saved = ha.hass.config_entries.async_update_entry.call_args.kwargs
    assert saved["minor_version"] == 2 and saved["version"] == 3
    expected = Settings.from_mapping(original).as_dict()
    assert saved["options"] == expected
    assert saved["options"]["prompt"]["mode"] == "strict"
    assert config == original and ha.hass.data["assist_router"] == ledger


async def test_standard_dispatch_failure_and_mode_change_cannot_unblock_actions(ha, monkeypatch):
    from custom_components.assist_router.prompts import PromptManager
    from custom_components.assist_router.settings import Settings

    inspector, _, _, _ = standard_fixture(ha, monkeypatch)
    stamp = (await inspector.inspect("conversation.alpha")).fingerprint
    router = setup_router(ha, configuration(stamp))
    router.runtime.prompts = PromptManager(router.runtime.settings, inspector)
    # Keep the inspected object's binding while giving it the fake agent's handler.
    inspected = ha.hass.agents["conversation.alpha"]

    async def fail(inp, log):
        raise TimeoutError("private result may already be written")

    agent = add_agent(ha, "conversation.alpha", handler=fail)
    agent.entry, agent.subentry = inspected.entry, inspected.subentry
    first = await ask(ha, router)
    assert len(agent.calls) == 1 and router.runtime.ledger.sessions[first.conversation_id].blocked
    config = router.runtime.settings.as_dict()
    config["prompt"]["mode"] = "strict"
    router.runtime.settings = Settings.from_mapping(config)
    router.runtime.prompts = PromptManager(router.runtime.settings, inspector)
    await ask(ha, router, cid=first.conversation_id)
    assert len(agent.calls) == 1


def test_tool_diagnostics_never_reads_arguments_names_or_result_data(ha, settings_data):
    router = setup_router(ha, settings_data)

    class PrivateResult:
        error = True

        @property
        def data(self):
            raise AssertionError("private result accessed")

    log = SimpleNamespace(
        content=[
            SimpleNamespace(role="assistant", tool_calls=[object()]),
            SimpleNamespace(role="tool_result", result=PrivateResult()),
        ]
    )
    router.runtime.observe_tools(log, 0)
    assert router.runtime.last_tools == {
        "agent": None,
        "visibility": "native_chat_log_only",
        "calls": 1,
        "results": 1,
        "errors": 1,
        "unknown_results": 0,
    }


def test_diagnostic_failure_does_not_change_safety_state(ha, settings_data):
    router = setup_router(ha, settings_data)

    class BrokenLog:
        @property
        def content(self):
            raise ValueError("private provider details")

    router.runtime.observe_tools(BrokenLog(), 0)
    assert router.runtime.last_tools["visibility"] == "unavailable"
    assert "private" not in repr(router.runtime.last_tools)


async def test_current_standard_configuration_is_not_re_migrated(ha, monkeypatch):
    from custom_components.assist_router.settings import Settings

    inspector, _, _, _ = standard_fixture(ha, monkeypatch)
    saved = Settings.from_mapping(
        configuration((await inspector.inspect("conversation.alpha")).fingerprint)
    ).as_dict()
    entry = SimpleNamespace(version=3, minor_version=2, data={}, options=saved)
    before = deepcopy(saved)
    assert await import_module("custom_components.assist_router").async_migrate_entry(ha.hass, entry)
    assert entry.options == before
    ha.hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.parametrize(
    "value", ["{% set x = states('private') %}{{ x }}", "{# hidden #}{{ states('private') }}"]
)
async def test_standard_blocks_all_dynamic_template_forms(ha, monkeypatch, value):
    inspector, _, subentry, _ = standard_fixture(ha, monkeypatch)
    subentry.data["request_body_opts"] = {"request_body_parameters": [{"Key": "temperature", "Value": value}]}
    assert (await inspector.inspect("conversation.alpha")).reason == "dynamic_request_override"
