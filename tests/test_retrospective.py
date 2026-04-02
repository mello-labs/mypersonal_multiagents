def test_markdown_to_notion_blocks_parses_lines():
    from agents import retrospective

    text = "\n".join(
        [
            "# Título",
            "## Subtítulo",
            "- Item 1",
            "**Destaque**",
            "Texto com *itálico* e `code`.",
        ]
    )

    blocks = retrospective._markdown_to_notion_blocks(text)

    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Título"
    assert blocks[1]["type"] == "heading_2"
    assert blocks[2]["type"] == "bulleted_list_item"
    assert blocks[3]["paragraph"]["rich_text"][0]["annotations"]["bold"] is True
    assert (
        blocks[4]["paragraph"]["rich_text"][0]["text"]["content"]
        == "Texto com itálico e code."
    )


def test_generate_report_fallback(monkeypatch):
    from agents import retrospective

    data = {
        "period": {"start": "2026-03-20", "end": "2026-03-27"},
        "metrics": {
            "total_focus_minutes": 120,
            "total_focus_hours": 2.0,
            "sessions_completed": 3,
            "sessions_abandoned": 1,
            "tasks_completed": 4,
            "completion_rate_pct": 50.0,
        },
        "completed_tasks": [],
        "focus_sessions": [],
    }

    def _raise(*args, **kwargs):
        raise RuntimeError("falha no LLM")

    monkeypatch.setattr(retrospective, "chat_completions", _raise)
    monkeypatch.setattr(retrospective.notifier, "error", lambda *args, **kwargs: None)

    report = retrospective.generate_report(data)

    assert "Relatório gerado sem LLM" in report
    assert "Retrospectiva 2026-03-20" in report
