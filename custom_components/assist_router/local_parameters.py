"""Read-only allowlist for the audited Local OpenAI extra-body assembly.

Never renders templates or rewrites configuration. Raw options remain fingerprinted.
"""

import ast
import io
import tokenize
from collections.abc import Mapping

INVALID = object()


def constant_value(value):
    """Recognize small literals and constant-only Jinja outputs, never execute them.

    HA preserves static string literals including quotes. Lowercase JSON false in a
    static dictionary is NOT a Python literal and remains a string in HA.
    """
    if not isinstance(value, str) or len(value) > 2048:
        return INVALID
    stripped = value.strip()
    jinja = stripped.startswith("{{") and stripped.endswith("}}")
    expression = stripped[2:-2].strip() if jinja else value

    def literal(node):
        if isinstance(node, ast.Constant) and type(node.value) in (str, bool):
            return node.value
        if jinja and isinstance(node, ast.Name) and node.id == "false":
            return False
        if isinstance(node, ast.Dict):
            result = {}
            for key, item in zip(node.keys, node.values, strict=True):
                name = literal(key)
                if not isinstance(name, str) or name in result:
                    raise ValueError
                result[name] = literal(item)
            return result
        raise ValueError

    try:
        if jinja:
            previous = None
            for token in tokenize.generate_tokens(io.StringIO(expression).readline):
                if token.type == tokenize.COMMENT:
                    return INVALID
                if token.type == tokenize.STRING:
                    # Python-only prefixes/triple quotes and differing escape
                    # semantics are outside our proven Jinja literal subset.
                    if (
                        token.string[0] not in "\"'"
                        or token.string.startswith(('"""', "'''"))
                        or "\\" in token.string
                        or previous == tokenize.STRING
                    ):
                        return INVALID
                previous = token.type
        tree = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 16:
            return INVALID
        result = literal(tree.body)
    except (ValueError, SyntaxError, TypeError, RecursionError, tokenize.TokenError):
        return INVALID if jinja else value
    return value if not jinja and isinstance(result, str) else result


def _pairs(options, section, field):
    container = options.get(section, {})
    if not isinstance(container, Mapping) or set(container) - {field}:
        raise ValueError
    rows = container.get(field, [])
    if not isinstance(rows, (list, tuple)):
        raise ValueError
    result = {}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"Key", "Value"}:
            raise ValueError
        key, value = row["Key"], row["Value"]
        if key == "" and value == "":
            continue  # Local OpenAI ignores empty UI rows too; still fingerprinted.
        if not isinstance(key, str) or not key or key != key.strip() or key in result:
            raise ValueError
        result[key] = constant_value(value)
    return result


def local_parameters_safe(options, *, llama_cpp, legacy_templates=False):
    """Allow only reasoning_effort=none and explicit, effective thinking=False.

    In the audited llama.cpp mixin the native bool option overwrites this one
    template kwarg. Require native False/default, so an explicit False is not
    silently turned into True. Unknown keys, dynamic values and duplicates fail.
    """
    try:
        body = _pairs(options, "request_body_opts", "request_body_parameters")
        template = _pairs(options, "chat_template_opts", "chat_template_kwargs")
        if set(body) - {"reasoning_effort", "chat_template_kwargs"}:
            return False
        if "reasoning_effort" in body and body["reasoning_effort"] != "none":
            return False
        nested = body.get("chat_template_kwargs", {})
        if not isinstance(nested, dict) or set(nested) - {"enable_thinking"}:
            return False
        if "chat_template_kwargs" in body and (not nested or legacy_templates):
            return False
        if set(template) - {"enable_thinking"}:
            return False
        if "enable_thinking" in template and "enable_thinking" in nested:
            return False  # Ambiguous: top-level body would overwrite the other path.
        flags = [*template.values(), *nested.values()]
        if flags:
            native = options.get("llamacpp_config", {})
            if not llama_cpp or not isinstance(native, Mapping):
                return False
            if native.get("llamacpp_enable_thinking", False) is not False:
                return False
            # Static lowercase 'false' is a string in HA, but the audited mixin
            # unconditionally replaces it with the native False boolean.
            if any(value is not False and value != "false" for value in flags):
                return False
        return True
    except (ValueError, TypeError):
        return False
