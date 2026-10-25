"""Only this module knows the historical 1.0 provider-role schema."""

from .settings import Settings

LEGACY_DEFAULTS = (
    ("local_agent", "conversation.lm_studio_google_gemma_4_12b_qat_ai_agent"),
    ("openai_agent", "conversation.openai_conversation"),
    ("gemini_agent", "conversation.google_ai_conversation"),
)


def migrate_v1(data):
    agents = [
        {"entity_id": data.get(key, default), "enabled": True, "health": None}
        for key, default in LEGACY_DEFAULTS
    ]
    agents[0]["health"] = {
        "kind": "lm_studio",
        # Never invent a destination. Missing/invalid legacy URLs fail validation
        # atomically, leaving the original entry and credentials untouched.
        "url": data.get("models_url"),
        "model_key": data.get("model_key", ""),
        "instance_id": data.get("instance_id", ""),
        "timeout": data.get("health_timeout", 1.0),
        "cache_seconds": data.get("cache_seconds", 2.0),
        "failure_cache_seconds": data.get("failure_cache_seconds", 15.0),
        "auth_type": "bearer" if data.get("token") else "none",
        "token": data.get("token", ""),
    }
    return Settings.from_mapping({"agents": agents}).as_dict()
