"""Lazy per-agent read-only HTTP probes with independent bounded caches."""

import asyncio
import json
from base64 import b64encode
from time import monotonic

import aiohttp

from .const import MAX_RESPONSE_BYTES
from .health_types import CHECK_TYPES, Health, parse_models
from .settings import HealthSettings

__all__ = ["Health", "HealthChecks", "ModelHealth", "parse_models"]


class ModelHealth:
    """One check; concurrent callers share a result, including with TTL zero."""

    def __init__(self, session: aiohttp.ClientSession, settings: HealthSettings, clock=monotonic):
        self.session = session
        self.settings = settings
        self.clock = clock
        self.last = Health(False, "not_checked")
        self._expires = 0.0
        self._generation = 0
        self._lock = asyncio.Lock()

    async def check(self) -> Health:
        generation = self._generation
        async with self._lock:
            if self.clock() < self._expires or generation != self._generation:
                return self.last
            self.last = await self._probe()
            self._generation += 1
            ttl = self.settings.cache_seconds if self.last.ready else self.settings.failure_cache_seconds
            self._expires = self.clock() + ttl
            return self.last

    async def _probe(self) -> Health:
        settings = self.settings
        headers = {"Authorization": f"Bearer {settings.token}"} if settings.auth_type == "bearer" else {}
        if settings.auth_type == "basic":
            credentials = b64encode(f"{settings.username}:{settings.password}".encode("utf-8")).decode(
                "ascii"
            )
            headers["Authorization"] = f"Basic {credentials}"
        timeout = aiohttp.ClientTimeout(total=settings.timeout, connect=min(0.5, settings.timeout))
        adapter = CHECK_TYPES[settings.kind]
        try:
            async with asyncio.timeout(settings.timeout):
                async with self.session.get(
                    settings.url, headers=headers, timeout=timeout, allow_redirects=False
                ) as response:
                    if response.status != settings.expected_status:
                        return Health(False, f"http_{response.status}")
                    if not adapter.reads_json:
                        return adapter.evaluate(None, settings)
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(16384):
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            return Health(False, "response_too_large")
                    return adapter.evaluate(json.loads(body.decode("utf-8")), settings)
        except TimeoutError:
            return Health(False, "timeout")
        except (json.JSONDecodeError, UnicodeError, RecursionError):
            return Health(False, "invalid_json")
        except aiohttp.ClientError:
            return Health(False, "connection_error")


class HealthChecks:
    """No configured check means no network request. Each route owns its cache."""

    def __init__(self, session, settings):
        self.checks = {
            route.entity_id: ModelHealth(session, route.health)
            for route in settings.routes
            if route.enabled and route.health is not None
        }

    async def check(self, agent_id):
        check = self.checks.get(agent_id)
        return await check.check() if check else Health(True, "entity_only")

    def diagnostics(self):
        return {
            agent_id: {"ready": check.last.ready, "reason": check.last.reason, "kind": check.settings.kind}
            for agent_id, check in self.checks.items()
        }
