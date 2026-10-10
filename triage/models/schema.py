"""Turn a Pydantic model into an OpenAI *strict* JSON schema.

Strict mode requires: every object has `additionalProperties: false`, every property is
listed in `required`, and some validation keywords are not accepted. Pydantic remains the
real validator, so constraints we strip here (e.g. `minimum`) are still enforced locally.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_UNSUPPORTED_KEYS = {
    "default",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "format",
}


def to_strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})
    result: dict[str, Any] = _strictify(_inline_refs(schema, defs))
    return result


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            target = defs[node["$ref"].split("/")[-1]]
            siblings = {k: v for k, v in node.items() if k != "$ref"}
            return _inline_refs({**target, **siblings}, defs)
        return {k: _inline_refs(v, defs) for k, v in node.items()}
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    return node


def _strictify(node: Any) -> Any:
    if isinstance(node, list):
        return [_strictify(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {k: _strictify(v) for k, v in node.items() if k not in _UNSUPPORTED_KEYS}
    if out.get("type") == "object" and "properties" in out:
        out["additionalProperties"] = False
        out["required"] = list(out["properties"])
    return out
