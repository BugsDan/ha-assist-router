"""Execute unmodified selected HA 2026.10.2 AST nodes with lightweight host doubles.

This is NOT a running HA server. Source is hash-checked before execution. We use
the real session/log/entity/delegation code to expose ID and nested-log mistakes.
"""

import ast
import asyncio
import hashlib
import json
import logging
import re
import textwrap
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import IntFlag, StrEnum
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]


def source_nodes(relative, names, namespace, evidence_file="docs/ha_api_evidence.json"):
    """No rewriting of the selected functions/classes. Only defer annotations."""
    data = (ROOT / "reference" / relative).read_bytes()
    evidence = json.loads((ROOT / evidence_file).read_text())
    assert hashlib.sha256(data).hexdigest() == evidence["sources"][relative]["sha256"]
    try:
        tree = ast.parse(data)
    except SyntaxError:
        # HA's full pipeline uses Python 3.14 syntax outside the selected methods.
        # Dedent exact method blocks; do not rewrite their bodies for Python 3.12.
        lines = data.decode("utf-8").splitlines(keepends=True)
        snippets = []
        for name in names:
            start = next(
                i
                for i, line in enumerate(lines)
                if re.match(rf"\s*(?:async )?(?:def|class) {name}(?:\(|:)", line)
            )
            indent = len(lines[start]) - len(lines[start].lstrip())
            end = start + 1
            while end < len(lines):
                line = lines[end]
                if (
                    re.match(r"\s*(?:(?:async )?def |class |@)", line)
                    and len(line) - len(line.lstrip()) <= indent
                ):
                    break
                end += 1
            snippets.append(textwrap.dedent("".join(lines[start:end])))
        tree = ast.parse("\n".join(snippets))
    nodes = []
    for name in names:
        nodes.append(next(node for node in ast.walk(tree) if getattr(node, "name", None) == name))
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(ROOT / "reference" / relative), "exec"), namespace)


class ResponseType(StrEnum):
    ACTION_DONE = "action_done"
    QUERY_ANSWER = "query_answer"
    ERROR = "error"


class ErrorCode(StrEnum):
    UNKNOWN = "unknown"


class IntentResponse:
    def __init__(self, language):
        self.language = language
        self.response_type = ResponseType.QUERY_ANSWER
        self.speech = {}
        self.data = {}

    def async_set_speech(self, text):
        self.speech = {"plain": {"speech": text}}

    def async_set_error(self, code, text):
        self.response_type = ResponseType.ERROR
        self.error_code = code
        self.async_set_speech(text)

    def as_dict(self):
        return {"speech": self.speech, "response_type": self.response_type, "data": self.data}


class HomeAssistantError(Exception):
    pass


@dataclass
class Context:
    id: str = "context"
    user_id: str = "user"

    def as_dict(self):
        return asdict(self)


class RestoreEntity:
    hass = None
    available = True

    def async_write_ha_state(self):
        pass

    def async_set_context(self, context):
        self.context = context

    async def async_added_to_hass(self):
        pass

    def async_on_remove(self, cb):
        pass


@contextmanager
def trace_context():
    yield SimpleNamespace(add_event=lambda event: None, set_result=lambda **kwargs: None)


def install(monkeypatch):
    def module(name, **attrs):
        item = ModuleType(name)
        item.__dict__.update(attrs)
        item.__path__ = []
        monkeypatch.setitem(__import__("sys").modules, name, item)
        return item

    def callback(function):
        return function

    clock = SimpleNamespace(utcnow=lambda: datetime.now(timezone.utc))
    intent = SimpleNamespace(
        IntentResponse=IntentResponse, IntentResponseType=ResponseType, IntentResponseErrorCode=ErrorCode
    )
    module("homeassistant")
    components = module("homeassistant.components")
    helpers = module("homeassistant.helpers", intent=intent)
    module("homeassistant.helpers.intent", **vars(intent))
    module("homeassistant.core", callback=callback, Context=Context)
    module(
        "homeassistant.const",
        STATE_UNAVAILABLE="unavailable",
        Platform=SimpleNamespace(CONVERSATION="conversation"),
    )
    module("homeassistant.helpers.event", async_track_state_change_event=lambda *args: lambda: None)
    module("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda hass: hass.http_session)

    session = module("homeassistant.helpers.chat_session")
    counter = iter(range(1, 10000))

    def ulid():
        return "01" + str(next(counter)).zfill(24)

    def validate_ulid(value):
        if len(value) != 26:
            raise ValueError

    session.__dict__.update(
        dataclass=dataclass,
        field=field,
        dt_util=clock,
        callback=callback,
        contextmanager=contextmanager,
        current_session=ContextVar("test_session", default=None),
        DATA_CHAT_SESSION="chat_session",
        DATA_CHAT_SESSION_CLEANUP="cleanup",
        SessionCleanup=lambda hass: SimpleNamespace(schedule=lambda: None),
        ulid_now=ulid,
        ulid_to_bytes=validate_ulid,
        LOGGER=logging.getLogger("test.session"),
    )
    source_nodes(
        "homeassistant/helpers/chat_session.py", ["ChatSession", "async_get_chat_session"], session.__dict__
    )
    helpers.chat_session = session

    conv = module("homeassistant.components.conversation")
    components.conversation = conv

    class Feature(IntFlag):
        CONTROL = 1

    conv.__dict__.update(
        dataclass=dataclass,
        field=field,
        replace=replace,
        asdict=asdict,
        callback=callback,
        contextmanager=contextmanager,
        abstractmethod=lambda method: method,
        final=lambda method: method,
        override=lambda method: method,
        RestoreEntity=RestoreEntity,
        dt_util=clock,
        current_chat_log=ContextVar("test_log", default=None),
        utcnow=clock.utcnow,
        DATA_CHAT_LOGS="logs",
        DATA_SUBSCRIPTIONS="subscriptions",
        DOMAIN="conversation",
        HOME_ASSISTANT_AGENT="home_assistant",
        ConversationEntityFeature=Feature,
        intent=intent,
        _async_notify_subscribers=lambda *args: None,
        LOGGER=logging.getLogger("test.log"),
        _LOGGER=logging.getLogger("test.agent"),
        async_get_chat_session=session.async_get_chat_session,
        HomeAssistantError=HomeAssistantError,
        asyncio=asyncio,
        async_conversation_trace=trace_context,
        ConversationTraceEvent=lambda *args: None,
        ConversationTraceEventType=SimpleNamespace(ASYNC_PROCESS="process"),
        dataclasses=__import__("dataclasses"),
    )
    # The loader must write into the module dictionary used by the actual functions.
    conv.StrEnum = StrEnum
    source_nodes("homeassistant/components/conversation/const.py", ["ChatLogEventType"], conv.__dict__)
    source_nodes(
        "homeassistant/components/conversation/models.py",
        ["ConversationInput", "ConversationResult"],
        conv.__dict__,
    )
    source_nodes(
        "homeassistant/components/conversation/chat_log.py",
        [
            "SystemContent",
            "UserContent",
            "AssistantContent",
            "ToolResultContent",
            "ChatLog",
            "async_get_chat_log",
        ],
        conv.__dict__,
    )
    source_nodes("homeassistant/components/conversation/entity.py", ["ConversationEntity"], conv.__dict__)
    conv.async_get_agent = lambda hass, agent_id: hass.agents.get(agent_id)
    source_nodes("homeassistant/components/conversation/agent_manager.py", ["async_converse"], conv.__dict__)
    conv.async_handle_sentence_triggers = AsyncMock(return_value=None)
    conv.async_handle_intents = AsyncMock(return_value=None)
    return SimpleNamespace(
        conv=conv, session=session, intent=intent, Context=Context, HomeAssistantError=HomeAssistantError
    )


def fake_hass():
    states = {}
    return SimpleNamespace(
        data={},
        agents={},
        states=SimpleNamespace(get=states.get),
        state_values=states,
        config=SimpleNamespace(language="de"),
    )
