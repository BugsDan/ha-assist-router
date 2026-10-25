"""No URL, credentials, session IDs, messages, arguments or provider exceptions."""


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = entry.runtime_data
    states = list(runtime.ledger.sessions.values())
    return {
        "active": runtime.active,
        "last_agent": runtime.last_agent,
        "last_reason": runtime.last_reason,
        "prompt": {
            "enabled": runtime.settings.prompt.enabled,
            "revision": runtime.prompts.revision,
            "last_check": runtime.prompts.last,
            "agent_checks": runtime.prompts.checks,
        },
        "health": runtime.health.diagnostics(),
        "agents": [
            {"entity_id": route.entity_id, "enabled": route.enabled} for route in runtime.settings.routes
        ],
        "sessions": len(states),
        "busy_sessions": sum(state.busy for state in states),
        "blocked_sessions": sum(state.blocked for state in states),
        "stale_prompt_sessions": sum(state.prompt_stale for state in states),
        "pending_sessions": sum(state.pending_agent is not None for state in states),
    }
