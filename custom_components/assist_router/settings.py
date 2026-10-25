"""Immutable provider-independent routes and per-agent health configuration."""

import math
import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

from .health_types import CHECK_TYPES


def valid_agent_id(value):
    return (
        isinstance(value, str)
        and re.fullmatch(r"conversation\.[a-z0-9_]+", value) is not None
        and value != "conversation.home_assistant"
    )


@dataclass(frozen=True)
class HealthSettings:
    kind: str
    url: str
    timeout: float = 1.0
    cache_seconds: float = 2.0
    failure_cache_seconds: float = 15.0
    expected_status: int = 200
    auth_type: str = "none"
    token: str = field(default="", repr=False)
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    model_key: str = ""
    instance_id: str = ""
    model_state: str = "loaded"

    @classmethod
    def from_mapping(cls, data):
        if not isinstance(data, dict):
            raise ValueError("invalid_health")
        try:
            settings = cls(**data)
        except TypeError:
            raise ValueError("invalid_health") from None
        if not isinstance(settings.kind, str) or settings.kind not in CHECK_TYPES:
            raise ValueError("invalid_health")
        try:
            url = urlsplit(settings.url)
            port = url.port
        except (ValueError, TypeError, AttributeError):
            raise ValueError("invalid_url") from None
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or (port is not None and not 1 <= port <= 65535)
            or any(char.isspace() or ord(char) < 32 for char in settings.url)
        ):
            raise ValueError("invalid_url")
        if settings.auth_type not in ("none", "bearer", "basic"):
            raise ValueError("invalid_auth")
        for secret in (settings.token, settings.username, settings.password):
            if not isinstance(secret, str) or any(ord(char) < 32 or ord(char) == 127 for char in secret):
                raise ValueError("invalid_auth")
        if settings.auth_type == "bearer" and not settings.token:
            raise ValueError("invalid_auth")
        if settings.auth_type == "basic" and (not settings.username or ":" in settings.username):
            raise ValueError("invalid_auth")
        if isinstance(settings.expected_status, bool) or not isinstance(settings.expected_status, int):
            raise ValueError("invalid_status")
        if not 200 <= settings.expected_status <= 299:
            raise ValueError("invalid_status")
        for value, lower, upper in (
            (settings.timeout, 0.1, 3),
            (settings.cache_seconds, 0, 5),
            (settings.failure_cache_seconds, 0, 60),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("invalid_budget")
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError("invalid_budget")
        CHECK_TYPES[settings.kind].validate(settings)
        values = asdict(settings)
        if settings.auth_type != "bearer":
            values["token"] = ""
        if settings.auth_type != "basic":
            values.update(username="", password="")
        return cls(**values)


@dataclass(frozen=True)
class AgentConfig:
    entity_id: str
    enabled: bool = True
    health: HealthSettings | None = None
    prompt_addition: str = field(default="", repr=False)

    @classmethod
    def from_mapping(cls, data):
        if not isinstance(data, dict) or set(data) - {"entity_id", "enabled", "health", "prompt_addition"}:
            raise ValueError("invalid_agents")
        if not valid_agent_id(data.get("entity_id")) or type(data.get("enabled", True)) is not bool:
            raise ValueError("invalid_agents")
        health = data.get("health")
        addition = data.get("prompt_addition", "")
        validate_prompt_text(addition)
        return cls(
            data["entity_id"],
            data.get("enabled", True),
            HealthSettings.from_mapping(health) if health is not None else None,
            addition,
        )


def validate_prompt_text(value):
    if not isinstance(value, str) or len(value) > 32768:
        raise ValueError("invalid_prompt")


@dataclass(frozen=True)
class PromptSettings:
    enabled: bool = False
    text: str = field(default="", repr=False)
    reviews: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(cls, data):
        if not isinstance(data, dict) or set(data) - {"enabled", "text", "reviews"}:
            raise ValueError("invalid_prompt")
        if type(data.get("enabled", False)) is not bool:
            raise ValueError("invalid_prompt")
        text = data.get("text", "")
        validate_prompt_text(text)
        if data.get("enabled") and not text.strip():
            raise ValueError("invalid_prompt")
        reviews = data.get("reviews", {})
        if not isinstance(reviews, dict) or any(
            not valid_agent_id(key) or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for key, value in reviews.items()
        ):
            raise ValueError("invalid_prompt")
        return cls(data.get("enabled", False), text, dict(reviews))


@dataclass(frozen=True)
class Settings:
    routes: tuple[AgentConfig, ...]
    prompt: PromptSettings = field(default_factory=PromptSettings)

    @property
    def agents(self):
        """Only enabled entities participate in routing and CONTROL capability."""
        return tuple(route.entity_id for route in self.routes if route.enabled)

    @classmethod
    def from_mapping(cls, data):
        if (
            not isinstance(data, dict)
            or set(data) - {"agents", "prompt"}
            or not isinstance(data.get("agents"), list)
        ):
            raise ValueError("invalid_agents")
        routes = tuple(AgentConfig.from_mapping(item) for item in data["agents"])
        ids = [route.entity_id for route in routes]
        if len(ids) != len(set(ids)):
            raise ValueError("invalid_agents")
        if not any(route.enabled for route in routes):
            raise ValueError("no_active_agents")
        return cls(routes, PromptSettings.from_mapping(data.get("prompt", {})))

    def as_dict(self):
        return {"agents": [asdict(route) for route in self.routes], "prompt": asdict(self.prompt)}
