"""Single place where tools are registered and executed.

To add a tool: create `triage/tools/<name>.py` exposing a `Tool`, then add it to
`default_registry()` below. Nothing else in the pipeline changes.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from triage.tools.base import Tool, ToolError
from triage.tools.customer_history import CUSTOMER_HISTORY_TOOL
from triage.tools.knowledge_base import KNOWLEDGE_BASE_TOOL
from triage.tools.system_status import SYSTEM_STATUS_TOOL

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolOutcome:
    name: str
    ok: bool
    payload: dict[str, Any]

    def as_message_content(self) -> str:
        return json.dumps(self.payload, ensure_ascii=False)


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool[Any]]) -> None:
        self._tools: dict[str, Tool[Any]] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[dict[str, Any]]:
        return [tool.openai_spec() for tool in self._tools.values()]

    def execute(self, name: str, raw_arguments: str) -> ToolOutcome:
        """Run a tool by name. Never raises: every failure becomes a structured error."""
        tool = self._tools.get(name)
        if tool is None:
            return _error(name, "unknown_tool", f"No tool named '{name}'. Available: {self.names}")
        try:
            args = json.loads(raw_arguments or "{}")
            return ToolOutcome(name, ok=True, payload=tool.run(args))
        except json.JSONDecodeError as exc:
            return _error(name, "invalid_json", f"Arguments are not valid JSON: {exc}")
        except ValidationError as exc:
            return _error(name, "invalid_arguments", str(exc.errors(include_url=False)))
        except ToolError as exc:
            return _error(name, "tool_error", str(exc))
        except Exception:  # a broken tool must not take the agent down
            logger.exception("tool crashed", extra={"tool": name})
            return _error(name, "internal_error", "The tool failed unexpectedly. Do not retry.")


def _error(name: str, kind: str, message: str) -> ToolOutcome:
    return ToolOutcome(name, ok=False, payload={"error": {"type": kind, "message": message}})


def default_registry() -> ToolRegistry:
    return ToolRegistry([CUSTOMER_HISTORY_TOOL, KNOWLEDGE_BASE_TOOL, SYSTEM_STATUS_TOOL])
