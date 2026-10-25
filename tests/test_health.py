"""Read-only metadata probes: parsing, bounds, network deadline, cache and redirects."""

import asyncio
import json
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web


def payload(*, key="google/gemma-4-12b-qat", ids=("gemma-instance",), kind="llm"):
    return {"models": [{"type": kind, "key": key, "loaded_instances": [{"id": value} for value in ids]}]}


class QueueSession:
    """HTTP boundary double. Deadline is separately exercised over a real TCP socket."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class Reply:
    def __init__(self, status=200, data=None, body=None):
        self.status = status
        self.body = body if body is not None else json.dumps(data).encode()
        self.content = SimpleNamespace(iter_chunked=self.chunks)

    async def chunks(self, size):
        for start in range(0, len(self.body), size):
            yield self.body[start : start + size]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.mark.parametrize(
    "data,reason",
    [
        (None, "invalid_schema"),
        ({"data": []}, "invalid_schema"),
        ({"models": [None]}, "invalid_schema"),
        (payload(ids=()), "model_unloaded"),
        (payload(ids=("wrong",)), "instance_missing"),
        (payload(key="other"), "model_missing"),
        (payload(kind="embedding"), "model_missing"),
        ({"models": [{"type": "llm", "key": "google/gemma-4-12b-qat"}]}, "invalid_schema"),
        ({"models": payload()["models"] * 2}, "ambiguous_model"),
        (payload(), "ready"),
    ],
)
def test_exact_model_and_instance(ha, data, reason):
    from custom_components.assist_router.health import parse_models

    result = parse_models(data, "google/gemma-4-12b-qat", "gemma-instance")
    assert result.reason == reason and result.ready == (reason == "ready")


async def test_positive_negative_cache_and_recovery(ha, health_data):
    from custom_components.assist_router.health import ModelHealth
    from custom_components.assist_router.settings import HealthSettings

    settings = HealthSettings.from_mapping(health_data)
    now = [0]
    session = QueueSession([Reply(data=payload()), Reply(status=503), Reply(data=payload())])
    health = ModelHealth(session, settings, lambda: now[0])
    assert (await health.check()).ready
    assert (await health.check()).ready
    now[0] = 3
    assert (await health.check()).reason == "http_503"
    now[0] = 10
    assert (await health.check()).reason == "http_503"
    now[0] = 19
    assert (await health.check()).ready
    assert len(session.calls) == 3


@pytest.mark.parametrize("status", [301, 401, 403, 404, 429, 500])
async def test_http_failure_no_redirect(ha, health_data, status):
    from custom_components.assist_router.health import ModelHealth
    from custom_components.assist_router.settings import HealthSettings

    settings = HealthSettings.from_mapping(health_data)
    session = QueueSession([Reply(status=status)])
    result = await ModelHealth(session, settings).check()
    assert result.reason == f"http_{status}"
    assert session.calls[0][1]["allow_redirects"] is False


@pytest.mark.parametrize(
    "body,reason",
    [("not JSON", "invalid_json"), ("a" * (1024 * 1024 + 1), "response_too_large")],
    ids=["invalid_json", "oversize"],
)
async def test_body_validation(ha, health_data, body, reason):
    from custom_components.assist_router.health import ModelHealth
    from custom_components.assist_router.settings import HealthSettings

    settings = HealthSettings.from_mapping(health_data)
    session = QueueSession([Reply(body=body.encode())])
    assert (await ModelHealth(session, settings).check()).reason == reason


async def test_real_tcp_deadline_and_concurrent_probe_coalescing(ha, health_data):
    from custom_components.assist_router.health import ModelHealth
    from custom_components.assist_router.settings import HealthSettings

    calls = []

    async def models(request):
        calls.append(request.headers.get("Authorization"))
        await asyncio.sleep(0.3)
        return web.json_response(payload())

    app = web.Application()
    app.router.add_get("/api/v1/models", models)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    settings = HealthSettings.from_mapping(
        health_data
        | {
            "url": f"http://127.0.0.1:{port}/api/v1/models",
            "timeout": 0.1,
            "token": "private",
            "auth_type": "bearer",
        }
    )
    try:
        async with aiohttp.ClientSession() as session:
            health = ModelHealth(session, settings)
            loop = asyncio.get_running_loop()
            start = loop.time()
            results = await asyncio.gather(*(health.check() for _ in range(8)))
            assert all(item.reason == "timeout" for item in results)
            assert loop.time() - start < 0.28
            assert calls == ["Bearer private"]
    finally:
        await runner.cleanup()


@pytest.mark.parametrize(
    "changes",
    [
        {"model_key": ""},
        {"url": "http://user:pass@host/api/v1/models"},
        {"url": "http://host/api/v1/models?token=x"},
        {"url": "ftp://host/api/v1/models"},
        {"url": "http://host:99999/api/v1/models"},
        {"timeout": float("nan")},
        {"timeout": 10},
        {"cache_seconds": -1},
        {"token": "bad\nvalue"},
    ],
)
def test_invalid_settings(ha, health_data, changes):
    from custom_components.assist_router.settings import HealthSettings

    with pytest.raises(ValueError):
        HealthSettings.from_mapping(health_data | changes)
