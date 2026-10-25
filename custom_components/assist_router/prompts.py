"""Opt-in shared additions with read-only baseline/source review and revision guards."""

import inspect
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from .local_parameters import local_parameters_safe

NEUTRAL_BASELINE = (
    "Verwende die für diese Anfrage bereitgestellten gemeinsamen Anweisungen sowie "
    "die von Home Assistant bereitgestellten Werkzeuge und Berechtigungen."
)
PASSTHROUGH_REVISION = "passthrough-v1"


def plain(value):
    """Canonical JSON without stringifying opaque objects or altering text codepoints."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("opaque_config")
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("opaque_config")


def fingerprint(value):
    return sha256(
        json.dumps(
            plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class PromptSnapshot:
    reason: str
    fingerprint: str = ""
    domain: str = ""
    source_fingerprints: dict = field(default_factory=dict)

    @property
    def ready(self):
        return self.reason == "ready"


class PromptInspector:
    """Reads registry/config entries; never changes a target config or sends inference."""

    def __init__(self, hass, contracts):
        self.hass = hass
        self.contracts = contracts["domains"]
        self.host_compatible = contracts.get("host_compatible", True)
        self.host_fingerprint = contracts.get("chat_log_sha256", "")
        self._source_cache = {}

    @staticmethod
    def source_hashes(methods, contract):
        result = {}
        try:
            for name, method in methods.items():
                if method.__name__ != name:
                    return None
                expected = contract["methods"][name].get(method.__module__)
                filename = inspect.getsourcefile(method)
                if expected is None or filename is None:
                    return None
                # Universal-newline reading accepts equivalent CRLF installations.
                digest = sha256(Path(filename).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                if digest != expected:
                    return None
                result[name] = digest
        except (OSError, TypeError, UnicodeError):
            return None
        return result

    async def inspect(self, entity_id):
        if not self.host_compatible:
            return PromptSnapshot("unknown_ha_source")
        # Imports are deliberately lazy: off mode has no registry/provider inspection.
        from homeassistant.components import conversation
        from homeassistant.helpers import entity_registry as er

        registry_entry = er.async_get(self.hass).async_get(entity_id)
        if (
            registry_entry is None
            or not registry_entry.config_entry_id
            or not registry_entry.config_subentry_id
        ):
            return PromptSnapshot("unknown_config")
        entry = self.hass.config_entries.async_get_entry(registry_entry.config_entry_id)
        if entry is None or entry.domain not in self.contracts or registry_entry.platform != entry.domain:
            return PromptSnapshot("unsupported_integration")
        subentry = entry.subentries.get(registry_entry.config_subentry_id)
        if subentry is None or subentry.subentry_type != "conversation":
            return PromptSnapshot("unknown_config", domain=entry.domain)
        agent = conversation.async_get_agent(self.hass, entity_id)
        if agent is None:
            return PromptSnapshot("agent_not_loaded", domain=entry.domain)
        if getattr(agent, "entry", None) is not entry or getattr(agent, "subentry", None) is not subentry:
            return PromptSnapshot("reload_required", domain=entry.domain)
        contract = self.contracts[entry.domain]
        methods = {name: getattr(agent, name, None) for name in contract["methods"]}
        if any(not inspect.ismethod(method) for method in methods.values()):
            return PromptSnapshot("unknown_source", domain=entry.domain)
        cache_key = (entry.domain, tuple(method.__func__ for method in methods.values()))
        if cache_key not in self._source_cache:
            self._source_cache[cache_key] = await self.hass.async_add_executor_job(
                self.source_hashes, methods, contract
            )
        source_hashes = self._source_cache[cache_key]
        if source_hashes is None:
            return PromptSnapshot("unknown_source", domain=entry.domain)
        # Source inspection yields to HA. Never certify an object replaced meanwhile.
        current_registry = er.async_get(self.hass).async_get(entity_id)
        if (
            current_registry is None
            or current_registry.config_entry_id != registry_entry.config_entry_id
            or current_registry.config_subentry_id != registry_entry.config_subentry_id
            or current_registry.platform != registry_entry.platform
            or self.hass.config_entries.async_get_entry(entry.entry_id) is not entry
            or entry.subentries.get(registry_entry.config_subentry_id) is not subentry
            or conversation.async_get_agent(self.hass, entity_id) is not agent
        ):
            return PromptSnapshot("reload_required", domain=entry.domain)
        hashes = {"ha_chat_log": self.host_fingerprint, **source_hashes}
        try:
            digest = fingerprint(
                {
                    "entity_id": entity_id,
                    "entry_id": entry.entry_id,
                    "domain": entry.domain,
                    "subentry_id": registry_entry.config_subentry_id,
                    "source": hashes,
                    "entry_data": entry.data,
                    "entry_options": entry.options,
                    "subentry_data": subentry.data,
                }
            )
        except (ValueError, TypeError, OverflowError):
            return PromptSnapshot("opaque_config", domain=entry.domain)
        reason = "ready" if subentry.data.get("prompt") == NEUTRAL_BASELINE else "base_not_neutral"
        if contract.get("parameter_policy") == "local_openai_v1":
            if not local_parameters_safe(
                subentry.data,
                llama_cpp=methods["_get_extra_body_args"].__module__
                == "custom_components.local_openai.entities.llama_cpp",
                legacy_templates=getattr(self.hass.config, "legacy_templates", False),
            ):
                reason = "unsafe_request_overrides"
        return PromptSnapshot(reason, digest, entry.domain, hashes)


async def async_make_inspector(hass):
    from homeassistant.components import conversation

    def read():
        contracts = json.loads(Path(__file__).with_name("prompt_contracts.json").read_text(encoding="utf-8"))
        try:
            source = Path(inspect.getsourcefile(conversation.ChatLog)).read_text(encoding="utf-8")
            if sha256(source.encode("utf-8")).hexdigest() != contracts["chat_log_sha256"]:
                contracts["domains"] = {}
                contracts["host_compatible"] = False
        except (OSError, TypeError, UnicodeError):
            contracts["domains"] = {}
            contracts["host_compatible"] = False
        return contracts

    return PromptInspector(hass, await hass.async_add_executor_job(read))


class PromptManager:
    """Stable suffixes only. This neither replaces HA prefixes nor claims exclusivity."""

    def __init__(self, settings, inspector=None):
        self.settings = settings
        self.inspector = inspector
        self.last = {"reason": "disabled" if not settings.prompt.enabled else "not_checked"}
        self.checks = {}
        self.static = {
            route.entity_id: "\n\n".join(
                part for part in (settings.prompt.text, route.prompt_addition) if part != ""
            )
            for route in settings.routes
        }
        self.revision = (
            PASSTHROUGH_REVISION
            if not settings.prompt.enabled
            else fingerprint(
                {
                    "text": settings.prompt.text,
                    "agents": {
                        route.entity_id: {
                            "addition": route.prompt_addition,
                            "review": settings.prompt.reviews.get(route.entity_id),
                        }
                        for route in settings.routes
                        if route.enabled
                    },
                }
            )
        )

    async def validate(self):
        if not self.settings.prompt.enabled:
            return True
        for entity_id in self.settings.agents:
            try:
                snapshot = (
                    await self.inspector.inspect(entity_id)
                    if self.inspector
                    else PromptSnapshot("unknown_source")
                )
            except Exception:
                # Fail closed without exposing provider config, secrets or prompt text.
                snapshot = PromptSnapshot("inspection_error")
            reason = snapshot.reason
            if snapshot.ready:
                reason = (
                    "ready"
                    if self.settings.prompt.reviews.get(entity_id) == snapshot.fingerprint
                    else "review_changed_or_missing"
                )
            self.last = {
                "entity_id": entity_id,
                "reason": reason,
                "current_fingerprint": snapshot.fingerprint,
                "reviewed_fingerprint": self.settings.prompt.reviews.get(entity_id, ""),
                "source_fingerprints": snapshot.source_fingerprints,
            }
            self.checks[entity_id] = dict(self.last)
            if reason != "ready":
                return False
        return True

    def compose(self, entity_id, incoming):
        if not self.settings.prompt.enabled:
            return incoming
        static = self.static[entity_id]
        return static if incoming is None or incoming == "" else static + "\n\n" + incoming
