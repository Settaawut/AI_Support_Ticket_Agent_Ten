import json
import logging

from triage.observability.logging import JsonFormatter, configure_logging, mask_pii
from triage.observability.trace import Trace


def test_mask_pii_hides_emails_and_card_numbers():
    text = "Contact jordan.lee@example.com, card 4242 4242 4242 4242 or 5555555555554444."
    masked = mask_pii(text)
    assert "jordan.lee" not in masked and "[email]" in masked
    assert "[card ****4242]" in masked and "[card ****4444]" in masked


def test_json_formatter_includes_extras_and_masks():
    record = logging.makeLogRecord(
        {"name": "triage.trace", "msg": "tool_call", "levelno": 20, "levelname": "INFO"}
    )
    record.ticket_id = "T-1"
    record.arguments = '{"email": "a@b.co"}'
    line = json.loads(JsonFormatter().format(record))
    assert line["ticket_id"] == "T-1" and "a@b.co" not in line["arguments"]


def test_configure_logging_writes_jsonl(tmp_path):
    log_file = tmp_path / "out.jsonl"
    configure_logging("INFO", log_file)
    Trace("T-1", "gpt-4o-mini").record_llm_call(100, 20, 5)
    logger = logging.getLogger("triage")
    for handler in logger.handlers:
        handler.close()
    logger.handlers = []
    entry = json.loads(log_file.read_text().splitlines()[-1])
    assert entry["ticket_id"] == "T-1" and entry["prompt_tokens"] == 100


def test_cost_estimate_uses_price_table():
    trace = Trace("T-1", "gpt-4o-mini")
    trace.record_llm_call(1_000_000, 1_000_000, 1)
    usage = trace.usage({"gpt-4o-mini": (0.15, 0.60)})
    assert usage.estimated_cost_usd == 0.75 and usage.llm_calls == 1
