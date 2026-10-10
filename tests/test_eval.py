from eval.metrics import CaseResult, summarise
from eval.run_eval import evaluate, load_dataset
from triage.agent.service import TriageService
from triage.llm import scripted_factory


def case(tid: str, expected_action: str, action: str, urgency: str = "low") -> CaseResult:
    return CaseResult(tid, "", ["low"], expected_action, urgency, action)


def test_metrics_count_missed_and_unnecessary_escalations():
    summary = summarise(
        [
            case("a", "escalate_to_human", "escalate_to_human"),
            case("b", "escalate_to_human", "route_to_specialist"),  # missed
            case("c", "auto_respond", "escalate_to_human"),  # unnecessary
            case("d", "auto_respond", "auto_respond", urgency="high"),
        ]
    )
    assert summary.escalation_recall == 0.5
    assert summary.escalation_precision == 0.5
    assert summary.missed_escalations == ["b"]
    assert summary.unnecessary_escalations == ["c"]
    assert summary.action_accuracy == 0.5
    assert summary.urgency_accuracy == 0.75


def test_metrics_handle_no_escalations():
    summary = summarise([case("a", "auto_respond", "auto_respond")])
    assert summary.escalation_recall == 1.0 and summary.escalation_precision == 1.0


def test_offline_eval_has_no_missed_escalations():
    rows = load_dataset()
    cases = evaluate(TriageService(scripted_factory()), rows)
    summary = summarise(cases)
    assert summary.total == len(rows) >= 11
    assert summary.missed_escalations == []
    by_id = {c.ticket_id: c for c in cases}
    assert by_id["E-05"].guardrails_fired  # security under-escalation corrected
    assert by_id["E-09"].action == "auto_respond"  # grounded how-to stays automated
