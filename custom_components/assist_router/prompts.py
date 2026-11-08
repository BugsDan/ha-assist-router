"""Opt-in shared additions with read-only baseline/source review and revision guards."""

import inspect
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from .local_parameters import has_prompt_override, local_parameters_safe, standard_parameters

NEUTRAL_BASELINE = (
    "Verwende die für diese Anfrage bereitgestellten gemeinsamen Anweisungen sowie "
    "die von Home Assistant bereitgestellten Werkzeuge und Berechtigungen."
)
PASSTHROUGH_REVISION = "passthrough-v1"


def reason_category(reason, warnings=()):
    if reason == "ready":
        return "warning" if warnings else "ready"
    if reason in {
        "unknown_config",
        "unknown_backend",
        "opaque_config",
        "agent_not_loaded",
        "reload_required",
        "invalid_parameter_config",
        "inspection_error",
        "unsupported_integration",
    }:
        return "technical"
    return "security"


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
    warnings: tuple[str, ...] = ()
    model: str | None = None

    @property
    def ready(self):
        return self.reason == "ready"


class PromptInspector:
    """Reads registry/config entries; never changes a target config or sends inference."""

    def __init__(self, hass, contracts, mode="strict"):
        self.hass = hass
        self.contracts = contracts["domains"]
        self.host_compatible = contracts.get("host_compatible", True)
        self.host_fingerprint = contracts.get("chat_log_sha256", "")
        self._source_cache = {}
        self.mode = mode

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
        if self.mode == "strict" and not self.host_compatible:
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
            if self.mode == "standard":
                snapshot = self.inspect_standard(entity_id, registry_entry, entry, subentry)
                return replace(snapshot, warnings=(*snapshot.warnings, "agent_not_loaded"))
            return PromptSnapshot("agent_not_loaded", domain=entry.domain)
        if getattr(agent, "entry", None) is not entry or getattr(agent, "subentry", None) is not subentry:
            return PromptSnapshot("reload_required", domain=entry.domain)
        if self.mode == "standard":
            return self.inspect_standard(entity_id, registry_entry, entry, subentry)
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
        model = subentry.data.get("model", subentry.data.get("chat_model"))
        if not isinstance(model, str) or len(model) > 160 or any(ord(c) < 32 for c in model):
            model = None
        return PromptSnapshot(reason, digest, entry.domain, hashes, model=model)

    @staticmethod
    def inspect_standard(entity_id, registry_entry, entry, subentry):
        """Trust an identity/destination, not a model, version or arbitrary source.

        Only the three supported configuration layouts are understood. This is
        an explicit trust decision about the integration, not source attestation.
        """
        domain = entry.domain
        if domain not in {"local_openai", "openai_conversation", "google_generative_ai_conversation"}:
            return PromptSnapshot("unsupported_integration", domain=domain)
        unique_id = getattr(registry_entry, "unique_id", None)
        if not isinstance(unique_id, str) or not unique_id:
            return PromptSnapshot("unknown_config", domain=domain)
        if not all(isinstance(value, Mapping) for value in (entry.data, entry.options, subentry.data)):
            return PromptSnapshot("opaque_config", domain=domain)
        is_local = domain == "local_openai"
        # Local OpenAI 1.14.0 constructs its client and retrieval connections
        # from entry.data, not from the options overlay used by the router itself.
        connection = entry.data if is_local else {**entry.data, **entry.options}
        if is_local:
            connection_fields = (
                "base_url",
                "api_key",
                "server_type",
                "custom_headers",
                "api_base",
                "api_url",
                "endpoint",
                "organization",
                "project",
                "azure_endpoint",
            )
            if any(
                key in entry.options and entry.options[key] != connection.get(key)
                for key in connection_fields
            ):
                return PromptSnapshot("conflicting_backend_config", domain=domain)
            if "weaviate_options" in entry.options:
                saved = connection.get("weaviate_options", {})
                overlay = entry.options["weaviate_options"]
                if (
                    not isinstance(saved, Mapping)
                    or not isinstance(overlay, Mapping)
                    or any(
                        key in overlay and overlay[key] != saved.get(key)
                        for key in ("weaviate_host", "weaviate_api_key")
                    )
                ):
                    return PromptSnapshot("conflicting_backend_config", domain=domain)
        # A configurable local destination must never be inferred from a model
        # name, entity name, health endpoint or historic private default URL.
        backend = {"provider": domain}
        if domain == "local_openai" and not connection.get("base_url"):
            return PromptSnapshot("unknown_backend", domain=domain)
        for key in ("base_url", "api_base", "api_url", "endpoint"):
            if key not in connection:
                continue
            value = connection[key]
            try:
                url = urlsplit(value)
                if (
                    not isinstance(value, str)
                    or not url.hostname
                    or url.scheme not in ("http", "https")
                    or url.username
                    or url.password
                    or url.query
                    or url.fragment
                    or any(ord(c) < 33 for c in value)
                    or any(marker in value for marker in ("{{", "{%", "{#"))
                ):
                    raise ValueError
                if url.port is not None and not 1 <= url.port <= 65535:
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                return PromptSnapshot("unknown_backend", domain=domain)
            # Match SDK base-URL normalization without hiding distinct proxy
            # paths: /v1 and /v1/ agree, but /v1// remains a different target.
            host = url.hostname
            authority = f"[{host}]" if ":" in host else host
            if url.port is not None and (url.scheme, url.port) not in {("http", 80), ("https", 443)}:
                authority += f":{url.port}"
            path = url.path if url.path.endswith("/") else url.path + "/"
            backend[key] = f"{url.scheme}://{authority}{path}"
        # Headers can select a different virtual host; retrieval changes the
        # trust area too. Persist only their digest, never their values.
        backend["server_type"] = connection.get("server_type", "generic")
        # Authentication/tenant changes can select a different trust area even
        # at the same URL. Only the combined digest is ever stored or displayed.
        backend["credential"] = connection.get("api_key") or ("local-openai" if is_local else "")
        for key in ("organization", "project", "azure_endpoint"):
            backend[key] = connection.get(key) or ""
        try:
            headers = connection.get("custom_headers", {})
            if not isinstance(headers, Mapping) or set(headers) - {"server_headers"}:
                raise ValueError
            rows = headers.get("server_headers", [])
            if not isinstance(rows, (list, tuple)):
                raise ValueError
            effective = {}
            for row in rows:
                if not isinstance(row, Mapping) or set(row) != {"Key", "Value"}:
                    raise ValueError
                key, value = row["Key"], row["Value"]
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ValueError
                if key == "" and value == "":
                    continue
                key = key.lower()
                if not key or key in effective or any(ord(c) < 33 for c in key):
                    raise ValueError
                if any(marker in value for marker in ("{{", "{%", "{#")):
                    return PromptSnapshot("dynamic_request_override", domain=domain)
                effective[key] = value
            backend["headers"] = effective
            retrieval = connection.get("weaviate_options", {})
            if not isinstance(retrieval, Mapping):
                raise ValueError
            backend["retrieval_host"] = retrieval.get("weaviate_host", "")
            retrieval_host = backend["retrieval_host"]
            if not isinstance(retrieval_host, str) or any(
                marker in retrieval_host for marker in ("{{", "{%", "{#")
            ):
                raise ValueError
            if is_local and retrieval_host:
                # The client adds a Bearer header only for a nonempty key.
                retrieval_key = retrieval.get("weaviate_api_key") or ""
                if not isinstance(retrieval_key, str):
                    raise ValueError
                backend["retrieval_credential"] = retrieval_key
        except (ValueError, TypeError):
            return PromptSnapshot("unknown_backend", domain=domain)
        try:
            stamp = fingerprint(
                {
                    "entity_id": entity_id,
                    "unique_id": unique_id,
                    "domain": domain,
                    "entry_id": entry.entry_id,
                    "subentry_id": registry_entry.config_subentry_id,
                    "backend": backend,
                }
            )
        except (ValueError, TypeError, OverflowError):
            return PromptSnapshot("opaque_config", domain=domain)
        reason = "ready"
        warnings = ()
        if any(has_prompt_override(config) for config in (entry.data, entry.options, subentry.data)):
            reason = "unsafe_request_overrides"
        elif entry.data.get("prompt") or entry.options.get("prompt") or "prompt" not in subentry.data:
            reason = "unknown_prompt_config"
        elif subentry.data["prompt"] != NEUTRAL_BASELINE:
            reason = "base_not_neutral"
        if reason == "ready" and domain == "local_openai":
            block, warnings = standard_parameters(subentry.data)
            reason = block or reason
            # Standard never evaluates templates, including request headers.
            headers = connection.get("custom_headers", {})
            if any(marker in str(headers) for marker in ("{{", "{%", "{#")):
                reason = "dynamic_request_override"
        model = subentry.data.get("model", subentry.data.get("chat_model"))
        if not isinstance(model, str) or len(model) > 160 or any(ord(c) < 32 for c in model):
            model = None
        return PromptSnapshot(reason, stamp, domain, warnings=warnings, model=model)


async def async_make_inspector(hass, mode="strict"):
    from homeassistant.components import conversation

    def read():
        contracts = json.loads(Path(__file__).with_name("prompt_contracts.json").read_text(encoding="utf-8"))
        if mode == "standard":
            return contracts  # No source reads or exact HA/agent hashes in Standard.
        try:
            source = Path(inspect.getsourcefile(conversation.ChatLog)).read_text(encoding="utf-8")
            if sha256(source.encode("utf-8")).hexdigest() != contracts["chat_log_sha256"]:
                contracts["domains"] = {}
                contracts["host_compatible"] = False
        except (OSError, TypeError, UnicodeError):
            contracts["domains"] = {}
            contracts["host_compatible"] = False
        return contracts

    return PromptInspector(hass, await hass.async_add_executor_job(read), mode)


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
        reviews = settings.prompt.reviews if settings.prompt.mode == "strict" else settings.prompt.approvals
        self.revision = (
            PASSTHROUGH_REVISION
            if not settings.prompt.enabled
            else fingerprint(
                {
                    "text": settings.prompt.text,
                    "agents": {
                        route.entity_id: {
                            "addition": route.prompt_addition,
                            "review": reviews.get(route.entity_id),
                        }
                        for route in settings.routes
                        if route.enabled
                    },
                }
            )
        )
        if settings.prompt.enabled and settings.prompt.mode == "standard":
            self.revision = fingerprint({"mode": "standard", "revision": self.revision})

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
            reviews = (
                self.settings.prompt.reviews
                if self.settings.prompt.mode == "strict"
                else self.settings.prompt.approvals
            )
            if snapshot.ready:
                reason = (
                    "ready"
                    if reviews.get(entity_id) == snapshot.fingerprint
                    else (
                        "review_changed_or_missing"
                        if self.settings.prompt.mode == "strict"
                        else "agent_or_backend_changed"
                        if entity_id in reviews
                        else "approval_missing"
                    )
                )
            self.last = {
                "entity_id": entity_id,
                "reason": reason,
                "current_fingerprint": snapshot.fingerprint,
                "reviewed_fingerprint": reviews.get(entity_id, ""),
                "source_fingerprints": snapshot.source_fingerprints,
                "mode": self.settings.prompt.mode,
                "warnings": list(snapshot.warnings),
                "model": snapshot.model,
                "category": reason_category(reason, snapshot.warnings),
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
