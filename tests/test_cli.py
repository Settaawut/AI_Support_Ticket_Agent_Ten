import json
from pathlib import Path

import pytest

from triage.cli import main


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # logs/ is written relative to cwd


def test_offline_run_all_renders_every_sample(capsys):
    assert main(["run", "--all", "--offline", "--verbose"]) == 0
    out = capsys.readouterr().out
    for ticket_id in ("T-1001", "T-1002", "T-1003"):
        assert ticket_id in out
    assert "Trace" in out


def test_json_output_is_machine_readable(capsys):
    assert main(["run", "--offline", "--json"]) == 0
    results = json.loads(capsys.readouterr().out)
    assert [r["action"] for r in results] == [
        "escalate_to_human",
        "escalate_to_human",
        "route_to_specialist",
    ]


def test_single_ticket_file(tmp_path, capsys):
    ticket = {
        "id": "T-X",
        "customer": {"id": "cus_x", "plan": "free", "region": "US", "tenure_months": 1},
        "messages": [{"age": "now", "text": "How do I reset my password?"}],
    }
    path = tmp_path / "ticket.json"
    path.write_text(json.dumps(ticket), encoding="utf-8")
    assert main(["run", "--ticket", str(path), "--offline", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["ticket_id"] == "T-X"


def test_invalid_ticket_file_is_a_usage_error(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text('{"id": "no customer"}', encoding="utf-8")
    assert main(["run", "--ticket", str(path), "--offline"]) == 2
    assert "Could not load tickets" in capsys.readouterr().err


def test_missing_api_key_is_explained(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert main(["run", "--all"]) == 2
    assert "--offline" in capsys.readouterr().err


def test_logs_are_written_as_jsonl(tmp_path):
    main(["run", "--offline", "--json"])
    lines = (tmp_path / "logs" / "triage.jsonl").read_text(encoding="utf-8").splitlines()
    assert any(json.loads(line)["msg"] == "tool_call" for line in lines)


def test_wrong_ai_demo_is_corrected_by_guardrails(capsys):
    """eval/wrong_ai_demo.json: scripted models answer T-1001/T-1002 dangerously wrong."""
    demo = Path(__file__).resolve().parent.parent / "eval" / "wrong_ai_demo.json"
    assert main(["run", "--ticket", str(demo), "--offline", "--json"]) == 0
    t1, t2 = json.loads(capsys.readouterr().out)
    assert (t1["urgency"], t1["action"], t1["target_team"]) == (
        "high",
        "escalate_to_human",
        "billing",
    )
    assert "refund" not in t1["draft_response"].lower()
    assert (t2["urgency"], t2["action"], t2["target_team"], t2["language"]) == (
        "critical",
        "escalate_to_human",
        "incident_response",
        "th",
    )
    assert t1["guardrail_overrides"] and t2["guardrail_overrides"]
