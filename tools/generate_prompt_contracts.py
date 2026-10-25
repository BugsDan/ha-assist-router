"""Generate the installed allowlist from the explicitly audited reference sources."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    evidence = json.loads((ROOT / "docs/prompt_compatibility_evidence.json").read_text(encoding="utf-8"))
    sources = evidence["sources"]

    def digest(name):
        return sources["prompt_compatibility/" + name]["sha256"]

    domains = {}
    for domain, handler, entity, module in (
        (
            "openai_conversation",
            "core/openai_conversation.py",
            "core/openai_entity.py",
            "homeassistant.components.openai_conversation",
        ),
        (
            "google_generative_ai_conversation",
            "core/google_conversation.py",
            "core/google_entity.py",
            "homeassistant.components.google_generative_ai_conversation",
        ),
        ("local_openai", "local/conversation.py", "local/entity.py", "custom_components.local_openai"),
    ):
        methods = {
            "_async_handle_message": {module + ".conversation": digest(handler)},
            "_async_handle_chat_log": {module + ".entity": digest(entity)},
        }
        if domain == "local_openai":
            methods["_convert_content_to_chat_message"] = {
                module + ".entity": digest(entity),
                module + ".entities.llama_cpp": digest("local/llama_cpp.py"),
            }
            methods["_get_extra_body_args"] = {
                module + ".entity": digest(entity),
                module + ".entities.llama_cpp": digest("local/llama_cpp.py"),
            }
        domains[domain] = {"methods": methods}
        if domain == "local_openai":
            domains[domain]["parameter_policy"] = "local_openai_v1"
    result = {
        "ha_reference": "2026.10.2",
        "chat_log_sha256": digest("core/chat_log.py"),
        "local_reference_commit": evidence["local_reference_commit"],
        "domains": domains,
    }
    target = ROOT / "custom_components/assist_router/prompt_contracts.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Generated audited source allowlist (no provider source installed).")


if __name__ == "__main__":
    main()
