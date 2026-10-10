import json

import pytest

from triage.models import LLMTriageOutput
from triage.models.schema import to_strict_json_schema
from triage.tools import Tool, ToolRegistry, default_registry
from triage.tools.bm25 import BM25Index, tokenize
from triage.tools.customer_history import GetCustomerHistoryArgs


@pytest.fixture
def registry() -> ToolRegistry:
    return default_registry()


def _run(registry: ToolRegistry, name: str, **args):
    return registry.execute(name, json.dumps(args))


# --- registry / schemas -------------------------------------------------------------


def test_registry_exposes_required_tools_as_strict_schemas(registry):
    specs = registry.specs()
    assert {s["function"]["name"] for s in specs} >= {
        "get_customer_history",
        "search_knowledge_base",
        "check_system_status",
    }
    for spec in specs:
        params = spec["function"]["parameters"]
        assert spec["function"]["strict"] is True
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])


def test_output_schema_is_strict_and_self_contained():
    schema = to_strict_json_schema(LLMTriageOutput)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text
    intent = schema["properties"]["intents"]["items"]
    assert intent["additionalProperties"] is False
    assert "minimum" not in schema["properties"]["confidence"]


def test_duplicate_tool_names_rejected():
    tool = Tool("t", "d", GetCustomerHistoryArgs, lambda a: {})
    with pytest.raises(ValueError):
        ToolRegistry([tool, tool])


@pytest.mark.parametrize(
    ("name", "raw", "error_type"),
    [
        ("does_not_exist", "{}", "unknown_tool"),
        ("get_customer_history", "{not json", "invalid_json"),
        ("get_customer_history", '{"wrong": 1}', "invalid_arguments"),
        ("get_customer_history", '{"customer_id": "cus_404"}', "tool_error"),
        ("check_system_status", '{"region": "mars"}', "invalid_arguments"),
    ],
)
def test_failures_become_structured_errors(registry, name, raw, error_type):
    outcome = registry.execute(name, raw)
    assert outcome.ok is False
    assert outcome.payload["error"]["type"] == error_type


def test_crashing_handler_is_contained():
    def boom(_):
        raise RuntimeError("db down")

    registry = ToolRegistry([Tool("flaky", "d", GetCustomerHistoryArgs, boom)])
    outcome = registry.execute("flaky", '{"customer_id": "x"}')
    assert outcome.payload["error"]["type"] == "internal_error"
    assert "db down" not in outcome.as_message_content()


# --- get_customer_history -----------------------------------------------------------


def test_customer_history_shows_three_holds_and_no_activation(registry):
    data = _run(registry, "get_customer_history", customer_id="cus_1001").payload
    assert data["subscription_status"] == "free"
    upgrades = [e for e in data["billing_events"] if e["type"] == "upgrade_attempt"]
    assert len(upgrades) == 3


def test_customer_history_strips_direct_identifiers(registry):
    data = _run(registry, "get_customer_history", customer_id="cus_1001").payload
    assert "email" not in data and "name" not in data


# --- check_system_status ------------------------------------------------------------


def test_status_conflict_detected_for_asia(registry):
    data = _run(registry, "check_system_status", region="asia").payload
    assert data["public_status_page"] == "operational"
    assert data["internal_incidents"][0]["id"] == "INC-2041"
    assert data["status_conflict"] is True


def test_no_conflict_in_healthy_region(registry):
    data = _run(registry, "check_system_status", region="europe").payload
    assert data["status_conflict"] is False and data["internal_incidents"] == []


# --- search_knowledge_base / BM25 ---------------------------------------------------


@pytest.mark.parametrize(
    ("query", "language", "expected_top"),
    [
        ("duplicate pending charges refund", "en", "KB-BILL-002"),
        ("dark mode schedule", "en", "KB-UI-001"),
        ("system default does not follow mac dark mode", "en", "KB-UI-002"),
        ("ระบบเข้าไม่ได้ error 500", "th", "KB-STAT-002"),
        ("pro export features", "en", "KB-PLAN-001"),
    ],
)
def test_kb_ranking(registry, query, language, expected_top):
    results = _run(registry, "search_knowledge_base", query=query, language=language)
    assert results.payload["results"][0]["id"] == expected_top


def test_kb_reports_no_result_honestly(registry):
    payload = _run(registry, "search_knowledge_base", query="pizza recipe", language="en").payload
    assert payload["results"] == []
    assert "Do not invent" in payload["message"]


def test_kb_falls_back_to_other_languages(registry):
    payload = _run(
        registry, "search_knowledge_base", query="dark mode appearance", language="th"
    ).payload
    assert payload["language_fallback"] is True
    assert payload["results"][0]["id"].startswith("KB-UI")


def test_tokenizer_handles_thai_without_spaces():
    tokens = tokenize("ระบบล่ม error 500")
    assert "error" in tokens and "500" in tokens
    assert "ระ" in tokens and "ล่" in tokens  # Thai character bigrams


def test_bm25_prefers_more_specific_match():
    index = BM25Index(["billing refund policy", "billing", "dark mode theme"])
    hits = index.search("billing refund", top_k=3)
    assert [h.index for h in hits][:2] == [0, 1]
