"""get_customer_history: account, plan and recent billing events (mocked)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from triage.data import load_json
from triage.tools.base import Tool, ToolError

# Data minimisation: the model never needs direct identifiers to triage.
_PII_FIELDS = {"name", "email"}


class GetCustomerHistoryArgs(BaseModel):
    customer_id: str = Field(description="The customer id from the ticket, e.g. 'cus_1001'.")


def get_customer_history(args: GetCustomerHistoryArgs) -> dict[str, Any]:
    record = load_json("customers.json").get(args.customer_id)
    if record is None:
        raise ToolError(
            f"No customer found with id '{args.customer_id}'. Continue the triage without "
            "customer history; retrying will not help."
        )
    return {"customer_id": args.customer_id} | {
        k: v for k, v in record.items() if k not in _PII_FIELDS
    }


CUSTOMER_HISTORY_TOOL = Tool(
    name="get_customer_history",
    description=(
        "Look up a customer's account: plan, subscription status, tenure, seats, region, app "
        "version, prior support tickets and recent billing events (charges, failures, holds). "
        "Call this for every ticket before deciding urgency or action."
    ),
    args_model=GetCustomerHistoryArgs,
    handler=get_customer_history,
)
