"""Read-only source audit for 1.2 prompt additions; no target integrations are changed."""

import ast
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CORE = "https://raw.githubusercontent.com/home-assistant/core/2026.10.2/"
LOCAL_COMMIT = "37b2334b2c5e5085a0c1081092fff238980e27ac"
LOCAL = f"https://raw.githubusercontent.com/skye-harris/hass_local_openai_llm/{LOCAL_COMMIT}/"
SOURCES = {
    "core/openai_conversation.py": CORE + "homeassistant/components/openai_conversation/conversation.py",
    "core/openai_entity.py": CORE + "homeassistant/components/openai_conversation/entity.py",
    "core/google_conversation.py": CORE
    + "homeassistant/components/google_generative_ai_conversation/conversation.py",
    "core/google_entity.py": CORE + "homeassistant/components/google_generative_ai_conversation/entity.py",
    "core/chat_log.py": CORE + "homeassistant/components/conversation/chat_log.py",
    "core/template.py": CORE + "homeassistant/helpers/template/__init__.py",
    "local/conversation.py": LOCAL + "custom_components/local_openai/conversation.py",
    "local/entity.py": LOCAL + "custom_components/local_openai/entity.py",
    "local/const.py": LOCAL + "custom_components/local_openai/const.py",
    "local/config_flow.py": LOCAL + "custom_components/local_openai/config_flow.py",
    "local/llama_cpp.py": LOCAL + "custom_components/local_openai/entities/llama_cpp.py",
    "local/manifest.json": LOCAL + "custom_components/local_openai/manifest.json",
    "local/LICENSE": LOCAL + "LICENSE",
}


def main():
    evidence = {
        "target_home_assistant": "2026.10.2",
        "local_reference_repository": "https://github.com/skye-harris/hass_local_openai_llm",
        "local_reference_tag": "1.13.0",
        "local_reference_commit": LOCAL_COMMIT,
        "installed_local_version": "unknown; not inferred from entity ID",
        "user_confirmed_local_integration": "skye-harris/hass_local_openai_llm; server type llama.cpp; LM Studio backend",
        "live_provider_requests": False,
        "sources": {},
    }
    sources = {}
    for name, url in SOURCES.items():
        path = f"prompt_compatibility/{name}"
        data = urlopen(url, timeout=30).read()
        target = ROOT / "reference" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        sources[name] = data.decode("utf-8")
        evidence["sources"][path] = {"url": url, "sha256": hashlib.sha256(data).hexdigest()}
    for name in ("core/openai_conversation.py", "core/google_conversation.py", "local/conversation.py"):
        tree = ast.parse(sources[name])
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "async_provide_llm_data"
        ]
        assert len(calls) == 1 and len(calls[0].args) == 4
        assert ast.unparse(calls[0].args[3]) == "user_input.extra_system_prompt"
        assert "CONF_PROMPT" in sources[name]
    shared = sources["core/chat_log.py"]
    assert "user_llm_prompt or llm.DEFAULT_INSTRUCTIONS_PROMPT" in shared
    assert "user_extra_system_prompt or self.extra_system_prompt" in shared
    assert "prompt_parts.append(extra_system_prompt)" in shared
    assert shared.index("llm.DATE_TIME_PROMPT") < shared.index("prompt_parts.append(extra_system_prompt)")
    llama = ast.parse(sources["local/llama_cpp.py"])
    mixin = next(
        node for node in llama.body if isinstance(node, ast.ClassDef) and node.name == "LlamaCppMixin"
    )
    assert not any(getattr(node, "name", None) == "_async_handle_message" for node in mixin.body)
    leaf = next(
        node
        for node in llama.body
        if isinstance(node, ast.ClassDef) and node.name == "LlamaCppConversationEntity"
    )
    assert [ast.unparse(base) for base in leaf.bases] == ["LlamaCppMixin", "LocalAiConversationEntity"]
    constants = {
        target.id: node.value.value
        for node in ast.parse(sources["local/const.py"]).body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    for key, value in {
        "CONF_REQUEST_BODY_OPTS": "request_body_opts",
        "CONF_REQUEST_BODY_PARAMETERS": "request_body_parameters",
        "CONF_CHAT_TEMPLATE_OPTS": "chat_template_opts",
        "CONF_CHAT_TEMPLATE_KWARGS": "chat_template_kwargs",
        "CONF_LLAMACPP_CONFIG": "llamacpp_config",
        "CONF_LLAMACPP_ENABLE_THINKING": "llamacpp_enable_thinking",
    }.items():
        assert constants[key] == value
    assert '"Value": {' in sources["local/config_flow.py"]
    assert '"selector": {"template": None}' in sources["local/config_flow.py"]
    assert 'chat_template_kwargs["enable_thinking"] = bool(' in sources["local/llama_cpp.py"]
    assert "literal_eval(render_result)" in sources["core/template.py"]
    evidence["parameter_policy_1_2_1"] = (
        "narrow constants only; raw parameters remain in full config fingerprints; native llama.cpp thinking override checked"
    )
    evidence["local_reference_manifest_version"] = json.loads(sources["local/manifest.json"])["version"]
    evidence["conclusion"] = (
        "extra_system_prompt is additive in all audited handlers; it does not replace the agent base prompt"
    )
    destination = ROOT / "docs/prompt_compatibility_evidence.json"
    destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Audited core and pinned Local OpenAI reference: additive, not exclusive replacement.")
    print("Installed Local OpenAI identity/version remains unverified.")


if __name__ == "__main__":
    main()
