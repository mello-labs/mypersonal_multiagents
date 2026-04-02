from datetime import timedelta

import fakeredis
from fastapi.testclient import TestClient

import web.app as web_app
from web.app import app


def test_chat_reaproveita_historico_da_sessao(mem, monkeypatch):
    captured_contexts = []

    def fake_process(message, context=None):
        captured_contexts.append(context or {})
        return f"eco:{message}"

    monkeypatch.setattr(web_app.orchestrator, "process", fake_process)
    monkeypatch.setattr(web_app.focus_guard, "start_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "stop_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "is_running", lambda: False)

    web_app.memory._redis_client = fakeredis.FakeRedis(decode_responses=True)

    with TestClient(app) as client:
        first = client.post("/chat", data={"message": "primeira pergunta"})
        second = client.post("/chat", data={"message": "segunda pergunta"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert captured_contexts[0]["chat_history"] == []
    assert captured_contexts[1]["chat_history"] == [
        {"role": "user", "content": "primeira pergunta"},
        {"role": "assistant", "content": "eco:primeira pergunta"},
    ]


def test_audit_page_exibe_eventos_alertas_handoffs_e_logs(mem, monkeypatch, tmp_path):
    monkeypatch.setattr(web_app.focus_guard, "start_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "stop_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "is_running", lambda: False)

    log_file = tmp_path / "agent_system.log"
    log_file.write_text("linha 1\nlinha 2 do log\n", encoding="utf-8")
    monkeypatch.setattr(web_app, "LOG_FILE", str(log_file))

    fake = fakeredis.FakeRedis(decode_responses=True)
    web_app.memory._redis_client = fake
    web_app.memory.create_alert("deviation_moderate", "Atraso detectado")
    web_app.memory.create_audit_event(
        event_type="auto_reschedule",
        title="Bloco reagendado",
        details="09:00-10:00 → 11:00-12:00",
        agent="focus_guard",
    )
    web_app.memory.log_handoff("orchestrator", "scheduler", "get_today_schedule")

    with TestClient(app) as client:
        response = client.get("/audit")

    assert response.status_code == 200
    assert "Bloco reagendado" in response.text
    assert "Atraso detectado" in response.text
    assert "orchestrator → scheduler" in response.text
    assert "linha 2 do log" in response.text


def test_agenda_page_exibe_intervalo(mem, monkeypatch):
    monkeypatch.setattr(web_app.focus_guard, "start_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "stop_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "is_running", lambda: False)

    fake = fakeredis.FakeRedis(decode_responses=True)
    web_app.memory._redis_client = fake
    web_app.memory.create_agenda_block("2026-03-20", "09:00-10:00", "Histórico passado")
    web_app.memory.create_agenda_block("2026-03-22", "10:00-11:00", "Histórico futuro")

    with TestClient(app) as client:
        response = client.get(
            "/agenda",
            params={"start_date": "2026-03-20", "end_date": "2026-03-22"},
        )

    assert response.status_code == 200
    assert "Agenda Navegável" in response.text
    assert "Histórico passado" in response.text
    assert "Histórico futuro" in response.text


def test_agenda_history_redirect_preserva_intervalo(mem, monkeypatch):
    monkeypatch.setattr(web_app.focus_guard, "start_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "stop_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "is_running", lambda: False)

    with TestClient(app) as client:
        response = client.get(
            "/agenda/history",
            params={"start_date": "2026-03-20", "end_date": "2026-03-22"},
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "/agenda?start_date=2026-03-20&end_date=2026-03-22"
    )


def test_agenda_import_notion_usa_intervalo(mem, monkeypatch):
    monkeypatch.setattr(web_app.focus_guard, "start_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "stop_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "is_running", lambda: False)
    monkeypatch.setattr(
        web_app.notion_sync,
        "sync_agenda_range_to_local",
        lambda start_date, end_date: 3,
    )

    fake = fakeredis.FakeRedis(decode_responses=True)
    web_app.memory._redis_client = fake

    with TestClient(app) as client:
        response = client.post(
            "/agenda/import",
            data={
                "source": "notion",
                "start_date": "2026-03-20",
                "end_date": "2026-03-22",
            },
        )

    assert response.status_code == 200
    assert "3 bloco(s) importado(s) de notion" in response.text


def test_agenda_partial_htmx_retorna_blocos_do_intervalo(mem, monkeypatch):
    monkeypatch.setattr(web_app.focus_guard, "start_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "stop_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "is_running", lambda: False)

    fake = fakeredis.FakeRedis(decode_responses=True)
    web_app.memory._redis_client = fake
    web_app.memory.create_agenda_block("2026-03-20", "09:00-10:00", "Bloco A")
    web_app.memory.create_agenda_block("2026-03-22", "10:00-11:00", "Bloco B")

    with TestClient(app) as client:
        response = client.get(
            "/agenda",
            params={"start_date": "2026-03-20", "end_date": "2026-03-22"},
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert "Bloco A" in response.text
    assert "Bloco B" in response.text
    assert "Agenda Navegável" not in response.text


def test_dashboard_marca_tarefa_atrasada_como_pendente(mem, monkeypatch):
    monkeypatch.setattr(web_app.focus_guard, "start_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "stop_guard", lambda: None)
    monkeypatch.setattr(web_app.focus_guard, "is_running", lambda: True)

    fake = fakeredis.FakeRedis(decode_responses=True)
    web_app.memory._redis_client = fake

    task_id = web_app.memory.create_task(
        "Troia",
        priority="Alta",
        scheduled_time="11h",
    )
    web_app.memory.update_task_status(task_id, "Em progresso")
    web_app.memory.create_agenda_block(
        (web_app.date.today() - timedelta(days=1)).isoformat(),
        "00:00-00:30",
        "Troia",
        task_id=task_id,
    )

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Troia" in response.text
    assert "Pendente" in response.text
    assert "Bloco vencido" in response.text
