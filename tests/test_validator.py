import pytest


def test_check_data_consistency_scores_all_flags():
    from agents import validator

    evidence = {
        "task": {"status": "Concluído", "actual_time": "10:00"},
        "focus_sessions": [{"status": "completed"}],
        "agenda_blocks": [{"completed": True}],
        "notion_data": {"status": "Concluído"},
    }

    flags = validator.check_data_consistency(evidence)

    assert flags["consistency_score"] == 100
    assert flags["notion_status_matches"] is True


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (75, "validated"),
        (50, "pending_confirmation"),
        (10, "rejected"),
    ],
)
def test_validate_with_llm_fallback(monkeypatch, score, expected):
    from agents import validator

    def _raise(*args, **kwargs):
        raise RuntimeError("llm indisponivel")

    monkeypatch.setattr(validator, "chat_completions", _raise)
    monkeypatch.setattr(validator.notifier, "error", lambda *args, **kwargs: None)

    verdict = validator.validate_with_llm(
        evidence={"task": {"title": "Tarefa"}},
        flags={"consistency_score": score},
    )

    assert verdict["verdict"] == expected
    assert "recommendation" in verdict
