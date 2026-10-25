"""Delegate once to an existing conversation agent, retaining HA chat context."""

import asyncio
from dataclasses import replace
from typing import Literal

from homeassistant.components import conversation
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers import intent
from homeassistant.helpers.chat_session import async_get_chat_session
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN
from .runtime import ROUTE_STACK


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AssistRouter(entry)])


class AssistRouter(conversation.ConversationEntity):
    """Never interprets tool arguments, retries a turn, or calls a provider directly."""

    _attr_name = "Assist Router"
    _attr_has_entity_name = True
    _attr_supports_streaming = False

    def __init__(self, entry):
        self._attr_unique_id = entry.entry_id
        self.runtime = entry.runtime_data

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return "*"

    @property
    def supported_features(self):
        # CONTROL controls native HA intent filtering, not delegation permissions.
        if not self.hass:
            return conversation.ConversationEntityFeature(0)
        return (
            conversation.ConversationEntityFeature.CONTROL
            if any(
                (state := self.hass.states.get(agent_id))
                and state.attributes.get("supported_features", 0)
                & conversation.ConversationEntityFeature.CONTROL
                for agent_id in self.runtime.settings.agents
            )
            else conversation.ConversationEntityFeature(0)
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, list(self.runtime.settings.agents), self._target_changed
            )
        )

    @callback
    def _target_changed(self, event):
        self.async_write_ha_state()

    def _eligible(self, agent_id):
        if agent_id == self.entity_id:
            return False
        agent = conversation.async_get_agent(self.hass, agent_id)
        if agent is None or isinstance(agent, AssistRouter):
            return False
        state = self.hass.states.get(agent_id)
        if state is None or state.state == STATE_UNAVAILABLE or not agent.available:
            return False
        return True

    def _error(self, user_input, conversation_id, message, chat_log=None):
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, message)
        if chat_log is not None:
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(agent_id=self.entity_id, content=message)
            )
        return conversation.ConversationResult(response=response, conversation_id=conversation_id)

    async def async_process(self, user_input):
        # Guard before opening a log or waiting on state: recursive tool calls must not deadlock.
        if ROUTE_STACK.get():
            return self._error(user_input, user_input.conversation_id, "Routing-Schleife blockiert.")
        if not self.runtime.active:
            return self._error(user_input, user_input.conversation_id, "Der Router wird neu geladen.")
        with async_get_chat_session(self.hass, user_input.conversation_id) as session:
            state = self.runtime.ledger.get(session.conversation_id)
            if state is None:
                return self._error(user_input, session.conversation_id, "Router-Sitzungslimit erreicht.")
            if state.busy or state.blocked:
                return self._error(
                    user_input,
                    session.conversation_id,
                    "Eine frühere Anfrage läuft noch oder ihr Ausgang ist unklar. "
                    "Bitte den tatsächlichen Zustand prüfen; keine Aktion automatisch wiederholen.",
                )
            state.busy = True
            if not state.cleanup_registered:
                state.cleanup_registered = True
                session.async_on_cleanup(lambda: self.runtime.ledger.cleanup(session.conversation_id, state))
            stack_token = ROUTE_STACK.set((DOMAIN,))
            try:
                with conversation.async_get_chat_log(self.hass, session, user_input) as chat_log:
                    return await self._async_handle_message(user_input, chat_log)
            finally:
                ROUTE_STACK.reset(stack_token)
                state.busy = False
                if state.cleanup_requested:
                    self.runtime.ledger.cleanup(session.conversation_id, state)

    async def _async_handle_message(self, user_input, chat_log):
        runtime = self.runtime
        state = runtime.ledger.sessions[chat_log.conversation_id]
        if state.prompt_revision is None:
            # Enabling additions on a pre-existing log would retain old system content.
            if runtime.settings.prompt.enabled and len(chat_log.content) > 2:
                state.prompt_stale = True
            state.prompt_revision = runtime.prompts.revision
        if state.prompt_stale or state.prompt_revision != runtime.prompts.revision:
            state.prompt_stale = True
            return self._error(
                user_input,
                chat_log.conversation_id,
                "Die Prompt-Konfiguration dieses Gesprächs ist veraltet. Bitte ein neues Gespräch beginnen.",
            )
        if not await runtime.prompts.validate():
            state.prompt_stale = True
            return self._prompt_error(user_input, chat_log)
        agent_id = await runtime.select(state, self._eligible)
        if agent_id is None:
            return self._error(
                user_input,
                chat_log.conversation_id,
                "Der Agent für die offene Rückfrage ist nicht verfügbar. Bitte später erneut versuchen "
                "oder ein neues Gespräch mit dem vollständigen Anliegen beginnen."
                if state.pending_agent
                else "Derzeit ist kein Conversation Agent verfügbar.",
                chat_log,
            )
        # Health checks yield to HA: review again in case a target changed meanwhile.
        if not await runtime.prompts.validate():
            state.prompt_stale = True
            return self._prompt_error(user_input, chat_log)
        if not runtime.active:
            return self._error(user_input, chat_log.conversation_id, "Der Router wird neu geladen.")
        # Every error below is AFTER dispatch: never call a different agent here.
        try:
            result = await conversation.async_converse(
                hass=self.hass,
                text=user_input.text,
                conversation_id=chat_log.conversation_id,
                context=user_input.context,
                language=user_input.language,
                agent_id=agent_id,
                device_id=user_input.device_id,
                satellite_id=user_input.satellite_id,
                extra_system_prompt=runtime.prompts.compose(agent_id, user_input.extra_system_prompt),
            )
            if result.conversation_id not in (None, chat_log.conversation_id):
                state.blocked = True
                runtime.last_reason = "conversation_id_changed"
                return self._error(
                    user_input,
                    chat_log.conversation_id,
                    "Der Agent hat die Conversation-ID gewechselt. Der Ausführungsstatus ist unklar; "
                    "bitte vor einer erneuten Aktion den tatsächlichen Zustand prüfen.",
                    chat_log,
                )
            if result.response.response_type == intent.IntentResponseType.ERROR:
                state.blocked = True
                state.pending_agent = None
                runtime.last_reason = "agent_error_no_retry"
                # Keep the structured original error, but do not invite an automatic follow-up.
                return replace(result, conversation_id=chat_log.conversation_id, continue_conversation=False)
            state.pending_agent = agent_id if result.continue_conversation else None
            if result.conversation_id is None:
                result = replace(result, conversation_id=chat_log.conversation_id)
            return result
        except asyncio.CancelledError:
            state.blocked = True
            runtime.last_reason = "cancelled_no_retry"
            raise
        except Exception:
            # Provider error text can contain prompts, arguments or credentials. Never log it.
            state.blocked = True
            state.pending_agent = None
            runtime.last_reason = "exception_no_retry"
            return self._error(
                user_input,
                chat_log.conversation_id,
                "Der Agent-Aufruf ist fehlgeschlagen. Eine Aktion könnte bereits ausgeführt sein. "
                "Es erfolgt keine automatische Wiederholung; bitte den tatsächlichen Zustand prüfen.",
                chat_log,
            )

    def _prompt_error(self, user_input, chat_log):
        self.runtime.last_reason = "prompt_review_required"
        return self._error(
            user_input,
            chat_log.conversation_id,
            "Die Agent-Prompt-Prüfung ist nicht freigegeben oder hat sich geändert. "
            "Bitte die Prompt-Prüfung in den Router-Optionen durchführen und ein neues Gespräch beginnen.",
        )
