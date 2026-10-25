"""Fetch pinned HA source, check used contracts and retain hash evidence. No server calls."""

import ast
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/home-assistant/core/2026.10.2/"
PATHS = [
    "homeassistant/components/conversation/entity.py",
    "homeassistant/components/conversation/agent_manager.py",
    "homeassistant/components/conversation/models.py",
    "homeassistant/components/conversation/chat_log.py",
    "homeassistant/components/conversation/const.py",
    "homeassistant/helpers/chat_session.py",
    "homeassistant/components/assist_pipeline/default_pipeline.py",
    "homeassistant/components/conversation/__init__.py",
    "homeassistant/config_entries.py",
    "pyproject.toml",
    "LICENSE.md",
    "homeassistant/helpers/selector.py",
    "homeassistant/data_entry_flow.py",
    "homeassistant/helpers/entity_registry.py",
]


def verify(sources):
    def find(path, name):
        tree = ast.parse(sources[path])
        return next(node for node in ast.walk(tree) if getattr(node, "name", None) == name)

    manager = PATHS[1]
    converse = find(manager, "async_converse")
    assert [arg.arg for arg in converse.args.args] == [
        "hass",
        "text",
        "conversation_id",
        "context",
        "language",
        "agent_id",
        "device_id",
        "satellite_id",
        "extra_system_prompt",
    ]
    handle = find(PATHS[0], "_async_handle_message")
    assert [arg.arg for arg in handle.args.args] == ["self", "user_input", "chat_log"]
    get_log = find(PATHS[3], "async_get_chat_log")
    assert [arg.arg for arg in get_log.args.args] == ["hass", "session", "user_input"]
    assert "chat_log.conversation_id == session.conversation_id" in sources[PATHS[3]]
    assert "async def async_add_assistant_content_without_tools" not in sources[PATHS[3]]
    assert "def async_add_assistant_content_without_tools" in sources[PATHS[3]]
    assert "async def async_process(self, user_input: ConversationInput)" in sources[PATHS[0]]
    assert "prefer_local_intents" in sources[PATHS[6]]
    assert "async_handle_sentence_triggers" in sources[PATHS[6]]
    assert "async_handle_intents" in sources[PATHS[6]]
    assert "continue_conversation_agent = agent_id" in sources[PATHS[6]]
    assert "async_converse" in sources[PATHS[7]] and "async_get_agent" in sources[PATHS[7]]
    assert "runtime_data" in sources[PATHS[8]]
    assert 'requires-python = ">=3.14.2"' in sources[PATHS[9]]
    selectors = sources["homeassistant/helpers/selector.py"]
    assert 'probatio.Optional("reorder", default=False)' in selectors
    assert "class EntitySelectorConfig" in selectors and "class EntitySelector(" in selectors
    assert 'probatio.Optional("include_entities")' in selectors
    assert 'probatio.Optional("exclude_entities")' in selectors
    assert "def async_show_menu(" in sources["homeassistant/data_entry_flow.py"]
    assert "description_placeholders:" in sources["homeassistant/data_entry_flow.py"]
    assert "def async_update_entry(" in sources[PATHS[8]]
    assert "def async_get(" in sources["homeassistant/helpers/entity_registry.py"]


def main():
    sources = {}
    evidence = {"version": "2026.10.2", "sources": {}}
    for path in PATHS:
        data = urlopen(BASE + path, timeout=30).read()
        sources[path] = data.decode("utf-8")
        destination = ROOT / "reference" / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        evidence["sources"][path] = {"url": BASE + path, "sha256": hashlib.sha256(data).hexdigest()}
    verify(sources)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/ha_api_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Pinned HA 2026.10.2 API contracts verified; source hashes saved.")


if __name__ == "__main__":
    main()
