"""LM Studio JIT is an opt-in routing decision, never a second inference."""

import pytest

from .test_config import new_flow
from .test_health import QueueSession, Reply, payload
from .test_router import add_agent, ask, setup_router


def inventory(*models):
    return {"models": list(models)}


@pytest.mark.parametrize(
    "models,instance,eligible",
    [
        (inventory(*payload(ids=())["models"]), "", True),
        (inventory(*payload(ids=())["models"]), "specific", False),
        (inventory(*payload(ids=())["models"], *payload(key="other")["models"]), "", False),
        (
            inventory(
                *payload(ids=())["models"],
                {"type": "embedding", "key": "embed", "loaded_instances": [{"id": "embed"}]},
            ),
            "",
            False,
        ),
        (inventory(*payload(ids=())["models"], {"type": "llm", "key": "bad"}), "", False),
    ],
)
def test_jit_requires_empty_complete_inventory_and_no_instance(ha, models, instance, eligible):
    from custom_components.assist_router.health_types import parse_models

    result = parse_models(models, "google/gemma-4-12b-qat", instance)
    assert result.reason == "model_unloaded" and result.jit_available is eligible


@pytest.mark.parametrize("enabled", [False, True])
async def test_jit_selects_local_only_when_enabled(ha, settings_data, enabled):
    from custom_components.assist_router.health import HealthChecks
    from custom_components.assist_router.settings import Settings

    settings_data["jit_load"] = enabled
    settings_data["agents"][0]["health"]["instance_id"] = ""
    router = setup_router(ha, settings_data)
    local = add_agent(ha, router.runtime.settings.agents[0])
    cloud = add_agent(ha, router.runtime.settings.agents[1])
    session = QueueSession([Reply(data=payload(ids=()))])
    router.runtime.health = HealthChecks(session, Settings.from_mapping(settings_data))
    result = await ask(ha, router)
    assert result.response.response_type != ha.intent.IntentResponseType.ERROR
    assert len(local.calls) == int(enabled) and len(cloud.calls) == int(not enabled)
    assert len(session.calls) == 1


async def test_jit_failure_does_not_try_another_agent(ha, settings_data):
    from custom_components.assist_router.health import HealthChecks

    async def failed(*args):
        raise TimeoutError("load or tool may have completed")

    settings_data["jit_load"] = True
    settings_data["agents"][0]["health"]["instance_id"] = ""
    router = setup_router(ha, settings_data)
    local = add_agent(ha, router.runtime.settings.agents[0], handler=failed)
    cloud = add_agent(ha, router.runtime.settings.agents[1])
    session = QueueSession([Reply(data=payload(ids=()))])
    router.runtime.health = HealthChecks(session, router.runtime.settings)
    result = await ask(ha, router)
    await ask(ha, router, cid=result.conversation_id)
    assert len(local.calls) == 1 and not cloud.calls
    assert router.runtime.ledger.sessions[result.conversation_id].blocked


async def test_jit_not_selected_on_http_error_or_missing_model(ha, settings_data):
    from custom_components.assist_router.health import HealthChecks

    for reply in [Reply(status=503), Reply(data=payload(key="different", ids=()))]:
        settings_data["jit_load"] = True
        router = setup_router(ha, settings_data)
        local = add_agent(ha, router.runtime.settings.agents[0])
        cloud = add_agent(ha, router.runtime.settings.agents[1])
        router.runtime.health = HealthChecks(QueueSession([reply]), router.runtime.settings)
        await ask(ha, router)
        assert not local.calls and len(cloud.calls) == 1


async def test_jit_empty_inventory_not_cached_but_normal_failures_are(ha, health_data):
    from custom_components.assist_router.health import ModelHealth
    from custom_components.assist_router.settings import HealthSettings

    settings = HealthSettings.from_mapping(health_data | {"instance_id": ""})
    session = QueueSession([Reply(data=payload(ids=())), Reply(data=payload()), Reply(status=503)])
    check = ModelHealth(session, settings, clock=lambda: 0, jit=True)
    assert (await check.check()).jit_available
    assert (await check.check()).ready
    assert (await check.check()).ready and len(session.calls) == 2


async def test_jit_toggle_default_off_and_saved_offline(ha, monkeypatch):
    _, flow = new_flow(ha, monkeypatch)
    form = await flow.async_step_user()
    values = form["data_schema"]({"agent_order": ["conversation.a"]})
    assert values["jit_load"] is False
    await flow.async_step_order({"agent_order": ["conversation.a"], "jit_load": True})
    assert (await flow.async_step_finish())["options"]["jit_load"] is True
