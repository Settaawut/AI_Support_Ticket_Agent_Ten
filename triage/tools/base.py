"""The Tool abstraction: name + description + typed args + handler, nothing else.

The JSON schema shown to the model is generated from `args_model`, so the schema and the
validation logic can never drift apart.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from triage.models.schema import to_strict_json_schema

ArgsT = TypeVar("ArgsT", bound=BaseModel)


class ToolError(Exception):
    """An expected, explainable failure (e.g. 'customer not found').

    Returned to the model as a structured error so it can recover; never crashes the loop.
    """


@dataclass(frozen=True)
class Tool(Generic[ArgsT]):
    name: str
    description: str
    args_model: type[ArgsT]
    handler: Callable[[ArgsT], dict[str, Any]]

    def openai_spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": to_strict_json_schema(self.args_model),
                "strict": True,
            },
        }

    def run(self, raw_args: dict[str, Any]) -> dict[str, Any]:
        """Validate raw arguments, then call the handler. May raise ValidationError/ToolError."""
        return self.handler(self.args_model.model_validate(raw_args))
