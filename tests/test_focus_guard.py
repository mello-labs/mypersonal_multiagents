import datetime

from agents import focus_guard


def test_focus_guard_reagenda_bloco_atrasado_e_audita(mem, monkeypatch):
    today = datetime.date.today().isoformat()
    overdue_id = mem.create_agenda_block(today, "00:00-00:30", "Troia", task_id=7)

    monkeypatch.setattr(
        focus_guard,
        "analyze_with_llm",
        lambda progress: {
            "on_track": False,
            "deviation_level": "moderate",
            "message": "Há atraso operacional.",
            "recommendation": "Reposicione a execução imediatamente.",
        },
    )
    monkeypatch.setattr(
        focus_guard._scheduler,
        "find_next_available_slot",
        lambda duration_minutes, start_after=None, max_days_ahead=3: (
            today,
            "13:00-13:30",
        ),
    )
    monkeypatch.setattr(
        focus_guard.notifier, "focus_alert", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(focus_guard.notifier, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(focus_guard.notifier, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(focus_guard.notifier, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(focus_guard.notifier, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(focus_guard.notifier, "separator", lambda *args, **kwargs: None)

    focus_guard._run_focus_check()

    blocks = mem.get_agenda_for_date(today, include_rescheduled=True)
    assert len(blocks) == 2

    original = mem.get_block(overdue_id)
    new_block = next(block for block in blocks if block["id"] != overdue_id)

    assert original["rescheduled"] == 1
    assert original["rescheduled_to_block_id"] == new_block["id"]
    assert new_block["time_slot"] == "13:00-13:30"
    assert new_block["created_by"] == "auto_reschedule"

    alertas = mem.list_alerts()
    assert len(alertas) == 1
    assert alertas[0]["alert_type"] == "deviation_moderate"

    eventos = mem.list_audit_events()
    tipos = [evento["event_type"] for evento in eventos]
    assert "focus_check" in tipos
    assert "auto_reschedule" in tipos
    assert "alert_created" in tipos


def test_focus_guard_usa_escalation_level_60min(mem, monkeypatch):
    """Sessão ativa com 61 minutos deve acionar o nível de 30 min (primeiro nível elegível)."""
    session_id = mem.start_focus_session(7, "Troia", 25)
    started_at = (
        datetime.datetime.now() - datetime.timedelta(minutes=61)
    ).isoformat()
    mem._redis_client.hset(
        f"session:{session_id}", mapping={"started_at": started_at}
    )

    monkeypatch.setattr(
        focus_guard,
        "analyze_with_llm",
        lambda progress: {
            "on_track": True,
            "deviation_level": "none",
            "message": "Tudo sob controle.",
            "recommendation": "",
        },
    )

    mac_calls = []
    monkeypatch.setattr(
        focus_guard.notifier,
        "mac_push",
        lambda title, message, sound=False: mac_calls.append((title, message, sound)),
    )
    monkeypatch.setattr(
        focus_guard.notifier, "focus_alert", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(focus_guard.notifier, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(focus_guard.notifier, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(focus_guard.notifier, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(focus_guard.notifier, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(focus_guard.notifier, "separator", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "agents.life_guard.run_all_checks",
        lambda: {"routines": [], "hydration": False, "finances": []}
    )

    focus_guard._run_focus_check()

    # A sessão de 61 minutos deve acionar exatamente 1 nível de escalação (o primeiro elegível)
    assert len(mac_calls) == 1
    _, message, _ = mac_calls[0]
    assert "Troia" in message
