"""check_system_status: public status page AND internal incident feed (mocked).

Returning both lets the agent notice when the public page is behind reality.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from triage.data import load_json
from triage.tools.base import Tool


class Region(StrEnum):
    ASIA = "asia"
    EUROPE = "europe"
    NORTH_AMERICA = "north_america"


class CheckSystemStatusArgs(BaseModel):
    region: Region = Field(
        description="Service region. Map countries to regions, e.g. Thailand/Japan -> 'asia', "
        "UK/Germany -> 'europe', US/Canada -> 'north_america'."
    )


def check_system_status(args: CheckSystemStatusArgs) -> dict[str, Any]:
    data = load_json("incidents.json")
    public = data["public_status_page"].get(args.region.value, "unknown")
    incidents = [i for i in data["internal_incidents"] if i["region"] == args.region.value]
    active = [i for i in incidents if i["status"] != "resolved"]
    return {
        "region": args.region.value,
        "public_status_page": public,
        "internal_incidents": active,
        "status_conflict": public == "operational" and bool(active),
        "disclosure_policy": (
            "You may tell the customer an issue in their region is being investigated. "
            "Never share internal incident ids, causes or fix times."
        ),
    }


SYSTEM_STATUS_TOOL = Tool(
    name="check_system_status",
    description=(
        "Check service health for a region. Returns the public status page state and the "
        "internal incident feed. Call this for any report of errors, downtime or access "
        "problems. The internal feed is the source of truth when the two disagree."
    ),
    args_model=CheckSystemStatusArgs,
    handler=check_system_status,
)
