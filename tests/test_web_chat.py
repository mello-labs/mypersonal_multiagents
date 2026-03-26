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
