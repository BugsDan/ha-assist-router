"""Health adapter registry, independent of routing positions and provider roles."""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Health:
    ready: bool
    reason: str


def parse_models(data, model_key: str, instance_id: str, model_state="loaded") -> Health:
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        return Health(False, "invalid_schema")
    models = data["models"]
    if any(not isinstance(item, dict) for item in models):
        return Health(False, "invalid_schema")
    matches = [item for item in models if item.get("key") == model_key and item.get("type") == "llm"]
    if len(matches) != 1:
        return Health(False, "model_missing" if not matches else "ambiguous_model")
    instances = matches[0].get("loaded_instances")
    if not isinstance(instances, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in instances
    ):
        return Health(False, "invalid_schema")
    if model_state == "present":
        return Health(True, "model_present")
    if not instances:
        return Health(False, "model_unloaded")
    if instance_id and not any(item["id"] == instance_id for item in instances):
        return Health(False, "instance_missing")
    return Health(True, "ready")


def validate_model(settings):
    if (
        not isinstance(settings.model_key, str)
        or not settings.model_key.strip()
        or settings.model_key != settings.model_key.strip()
        or not isinstance(settings.instance_id, str)
        or settings.instance_id != settings.instance_id.strip()
        or settings.model_state not in ("loaded", "present")
        or (settings.model_state == "present" and settings.instance_id)
    ):
        raise ValueError("invalid_model")


@dataclass(frozen=True)
class CheckType:
    reads_json: bool
    validate: Callable
    evaluate: Callable
    uses_model: bool = False


CHECK_TYPES = {
    "http": CheckType(False, lambda settings: None, lambda data, settings: Health(True, "ready")),
    "lm_studio": CheckType(
        True,
        validate_model,
        lambda data, settings: parse_models(
            data, settings.model_key, settings.instance_id, settings.model_state
        ),
        uses_model=True,
    ),
}
