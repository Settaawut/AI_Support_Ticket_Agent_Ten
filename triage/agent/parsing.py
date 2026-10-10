"""Parse and validate the model's final answer against the `LLMTriageOutput` contract."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from triage.models import LLMTriageOutput
from triage.models.schema import to_strict_json_schema

RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "triage_result",
        "strict": True,
        "schema": to_strict_json_schema(LLMTriageOutput),
    },
}

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


class OutputValidationError(ValueError):
    """The model's final message is not a valid `LLMTriageOutput`."""


def parse_output(content: str | None) -> LLMTriageOutput:
    if not content or not content.strip():
        raise OutputValidationError("Final message was empty; a JSON object is required.")
    try:
        return LLMTriageOutput.model_validate_json(_CODE_FENCE.sub("", content.strip()))
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors(include_url=False)[:10]
        )
        raise OutputValidationError(problems) from exc


def repair_instruction(error: OutputValidationError) -> str:
    return (
        "Your last answer did not match the required JSON schema. Problems: "
        f"{error}. Reply again with ONLY the corrected JSON object."
    )
