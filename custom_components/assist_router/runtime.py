"""Small routing state machine, independent of Home Assistant internals."""

from contextvars import ContextVar
from dataclasses import dataclass

from .const import MAX_SESSIONS
from .prompts import PromptManager

ROUTE_STACK = ContextVar("assist_router_stack", default=())


@dataclass
class SessionState:
    prompt_revision: str | None = None
    prompt_stale: bool = False
    busy: bool = False
    blocked: bool = False
    pending_agent: str | None = None
    cleanup_requested: bool = False
    cleanup_registered: bool = False


class Ledger:
    """Shared across options reloads. Never evict unresolved or active execution."""

    def __init__(self):
        self.sessions: dict[str, SessionState] = {}

    def get(self, conversation_id):
        if conversation_id not in self.sessions:
            if len(self.sessions) >= MAX_SESSIONS:
                return None
            self.sessions[conversation_id] = SessionState()
        return self.sessions[conversation_id]

    def cleanup(self, conversation_id, state):
        state.cleanup_requested = True
        if not state.busy and not state.blocked and self.sessions.get(conversation_id) is state:
            self.sessions.pop(conversation_id)


class Runtime:
    """One currently loaded entry, sharing its safety ledger with its predecessors."""

    def __init__(self, settings, health, ledger):
        self.settings = settings
        self.health = health
        self.ledger = ledger
        self.prompts = PromptManager(settings)
        self.active = True
        self.last_agent = None
        self.last_reason = "not_used"

    async def select(self, state, eligible):
        # An answer to a clarification must not silently change backend.
        candidates = (state.pending_agent,) if state.pending_agent else self.settings.agents
        for agent_id in candidates:
            if agent_id not in self.settings.agents:
                continue
            if not eligible(agent_id):
                continue
            if not (await self.health.check(agent_id)).ready:
                continue
            # Recheck after the network await, before any dispatch.
            if self.active and eligible(agent_id):
                self.last_agent = agent_id
                self.last_reason = "follow_up" if state.pending_agent else "selected"
                return agent_id
        self.last_agent = None
        self.last_reason = "follow_up_unavailable" if state.pending_agent else "no_backend"
        return None
