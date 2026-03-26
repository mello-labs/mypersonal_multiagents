"""
test_notion_sync.py — Testes do agente notion_sync com requests mockado.
Não faz chamadas reais à Notion API.
"""
import pytest
from unittest.mock import patch, MagicMock


def _mock_response(status_code: int, json_data: dict, text: str = "") -> MagicMock:
    """Helper para criar um mock de requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.ok = (200 <= status_code < 300)
    mock.json.return_value = json_data
    mock.text = text or str(json_data)
    return mock


# =============================================================================
# _request — retry e erros
# =============================================================================

class TestRequest:
    def test_request_sucesso(self):
        from agents.notion_sync import _request

        ok = _mock_response(200, {"object": "list", "results": []})
        with patch("requests.request", return_value=ok):
            result = _request("POST", "databases/abc/query", {})
        assert result == {"object": "list", "results": []}

    def test_request_erro_404_levanta_runtime_error(self):
        from agents.notion_sync import _request

        not_found = _mock_response(404, {}, "object_not_found")
        with patch("requests.request", return_value=not_found):
            with pytest.raises(RuntimeError, match="404"):
                _request("POST", "databases/abc/query", {})

    def test_request_retry_em_429(self):
        """Deve tentar de novo em rate limit e ter sucesso na segunda tentativa."""
        from agents.notion_sync import _request

        rate_limited = _mock_response(429, {}, "Too Many Requests")
        ok = _mock_response(200, {"results": []})

        # Primeira chamada → 429, segunda → 200
        with patch("requests.request", side_effect=[rate_limited, ok]):
            # tenacity faz wait_exponential, precisamos zerar o sleep
            with patch("tenacity.nap.time.sleep"):
                result = _request("POST", "databases/abc/query", {})

        assert result == {"results": []}

    def test_request_retry_esgotado_levanta_erro(self):
        """Após 4 tentativas com 429, deve levantar _NotionRateLimitError."""
        from agents.notion_sync import _request, _NotionRateLimitError

        rate_limited = _mock_response(429, {}, "Too Many Requests")

        with patch("requests.request", return_value=rate_limited):
            with patch("tenacity.nap.time.sleep"):
                with pytest.raises(_NotionRateLimitError):
                    _request("POST", "databases/abc/query", {})


# =============================================================================
# fetch_notion_tasks — parsing da resposta
# =============================================================================

class TestFetchNotionTasks:
    def test_fetch_retorna_lista_vazia(self):
        from agents.notion_sync import fetch_notion_tasks

        empty = _mock_response(200, {"results": []})
        with patch("requests.request", return_value=empty):
            tasks = fetch_notion_tasks()
        assert tasks == []

    def test_fetch_parseia_tarefa_corretamente(self):
        from agents.notion_sync import fetch_notion_tasks

        notion_response = {
            "results": [
                {
                    "id": "page-id-abc",
                    "properties": {
                        "Nome": {
                            "title": [{"plain_text": "Minha tarefa"}]
                        },
                        "Status": {
                            "select": {"name": "Em progresso"}
                        },
                        "Prioridade": {
                            "select": {"name": "Alta"}
                        },
                        "Horário previsto": {
                            "rich_text": [{"plain_text": "09:00"}]
                        },
                        "Horário real": {
                            "rich_text": []
                        },
                    },
                }
            ]
        }

        ok = _mock_response(200, notion_response)
        with patch("requests.request", return_value=ok):
            tasks = fetch_notion_tasks()

        assert len(tasks) == 1
        assert tasks[0]["title"] == "Minha tarefa"
        assert tasks[0]["status"] == "Em progresso"
        assert tasks[0]["priority"] == "Alta"
        assert tasks[0]["scheduled_time"] == "09:00"
        assert tasks[0]["notion_page_id"] == "page-id-abc"


# =============================================================================
# create_notion_task — payload enviado
# =============================================================================

class TestCreateNotionTask:
    def test_create_task_envia_payload_correto(self):
        from agents import notion_sync

        ok = _mock_response(200, {"id": "new-page-123"})

        with patch("requests.request", return_value=ok) as mock_req:
            page_id = notion_sync.create_notion_task(
                title="Nova tarefa",
                status="A fazer",
                priority="Alta",
                scheduled_time="10:00",
            )

        assert page_id == "new-page-123"

        # Verifica que a chamada foi POST para /pages
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1].endswith("/pages")

        payload = call_args[1]["json"]
        assert payload["properties"]["Nome"]["title"][0]["text"]["content"] == "Nova tarefa"
        assert payload["properties"]["Status"]["select"]["name"] == "A fazer"
        assert payload["properties"]["Prioridade"]["select"]["name"] == "Alta"

    def test_create_task_sem_notion_configurado_retorna_vazio(self):
        from agents import notion_sync

        with patch.object(notion_sync, "NOTION_TOKEN", ""):
            page_id = notion_sync.create_notion_task("Tarefa sem token")

        assert page_id == ""
