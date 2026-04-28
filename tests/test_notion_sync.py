"""
test_notion_sync.py — Testes do agente notion_sync com requests mockado.
Não faz chamadas reais à Notion API.
"""

from unittest.mock import MagicMock, patch

import pytest


def _mock_response(status_code: int, json_data: dict, text: str = "") -> MagicMock:
    """Helper para criar um mock de requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.ok = 200 <= status_code < 300
    mock.json.return_value = json_data
    mock.text = text or str(json_data)
    return mock


# =============================================================================
# adapters.notion.request — retry e erros
# =============================================================================


class TestRequest:
    def test_request_sucesso(self):
        from adapters.notion import request

        ok = _mock_response(200, {"object": "list", "results": []})
        with patch("requests.request", return_value=ok):
            result = request("POST", "databases/abc/query", {})
        assert result == {"object": "list", "results": []}

    def test_request_erro_404_levanta_runtime_error(self):
        from adapters.notion import request

        not_found = _mock_response(404, {}, "object_not_found")
        with patch("requests.request", return_value=not_found):
            with pytest.raises(RuntimeError, match="404"):
                request("POST", "databases/abc/query", {})

    def test_request_retry_em_429(self):
        """Deve tentar de novo em rate limit e ter sucesso na segunda tentativa."""
        from adapters.notion import request

        rate_limited = _mock_response(429, {}, "Too Many Requests")
        ok = _mock_response(200, {"results": []})

        # Primeira chamada → 429, segunda → 200
        with patch("requests.request", side_effect=[rate_limited, ok]):
            # tenacity faz wait_exponential, precisamos zerar o sleep
            with patch("tenacity.nap.time.sleep"):
                result = request("POST", "databases/abc/query", {})

        assert result == {"results": []}

    def test_request_retry_esgotado_levanta_erro(self):
        """Após 4 tentativas com 429, deve levantar NotionRateLimitError."""
        from adapters.notion import NotionRateLimitError, request

        rate_limited = _mock_response(429, {}, "Too Many Requests")

        with patch("requests.request", return_value=rate_limited):
            with patch("tenacity.nap.time.sleep"):
                with pytest.raises(NotionRateLimitError):
                    request("POST", "databases/abc/query", {})


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
                        "Nome": {"title": [{"plain_text": "Minha tarefa"}]},
                        "Status": {"select": {"name": "Em progresso"}},
                        "Prioridade": {"select": {"name": "Alta"}},
                        "Horário previsto": {"rich_text": [{"plain_text": "09:00"}]},
                        "Horário real": {"rich_text": []},
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

    def test_fetch_parseia_horario_previsto_como_date_com_hora(self):
        """Notion devolve 'Horário previsto' como property date com datetime ISO."""
        from agents.notion_sync import fetch_notion_tasks

        notion_response = {
            "results": [
                {
                    "id": "page-date-1",
                    "properties": {
                        "Nome": {"title": [{"plain_text": "Tarefa com data"}]},
                        "Status": {"select": {"name": "A fazer"}},
                        "Prioridade": {"select": {"name": "Alta"}},
                        "Horário previsto": {
                            "type": "date",
                            "date": {"start": "2026-04-07T14:30:00.000-03:00"},
                        },
                        "Horário real": {"type": "rich_text", "rich_text": []},
                    },
                }
            ]
        }

        ok = _mock_response(200, notion_response)
        with patch("requests.request", return_value=ok):
            tasks = fetch_notion_tasks()

        assert tasks[0]["scheduled_time"] == "2026-04-07 14:30"

    def test_fetch_parseia_horario_previsto_como_date_sem_hora(self):
        """Notion devolve 'Horário previsto' como date sem hora (só dia)."""
        from agents.notion_sync import fetch_notion_tasks

        notion_response = {
            "results": [
                {
                    "id": "page-date-2",
                    "properties": {
                        "Nome": {"title": [{"plain_text": "Só data"}]},
                        "Status": {"select": {"name": "A fazer"}},
                        "Prioridade": {"select": {"name": "Média"}},
                        "Horário previsto": {
                            "type": "date",
                            "date": {"start": "2026-04-07"},
                        },
                        "Horário real": {"type": "rich_text", "rich_text": []},
                    },
                }
            ]
        }

        ok = _mock_response(200, notion_response)
        with patch("requests.request", return_value=ok):
            tasks = fetch_notion_tasks()

        assert tasks[0]["scheduled_time"] == "2026-04-07"

    def test_fetch_date_vazio_retorna_string_vazia(self):
        """Property 'date' existe mas com valor None não deve explodir."""
        from agents.notion_sync import fetch_notion_tasks

        notion_response = {
            "results": [
                {
                    "id": "page-date-3",
                    "properties": {
                        "Nome": {"title": [{"plain_text": "Sem horário"}]},
                        "Status": {"select": {"name": "A fazer"}},
                        "Prioridade": {"select": {"name": "Baixa"}},
                        "Horário previsto": {"type": "date", "date": None},
                        "Horário real": {"type": "rich_text", "rich_text": []},
                    },
                }
            ]
        }

        ok = _mock_response(200, notion_response)
        with patch("requests.request", return_value=ok):
            tasks = fetch_notion_tasks()

        assert tasks[0]["scheduled_time"] == ""


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
        assert (
            payload["properties"]["Nome"]["title"][0]["text"]["content"]
            == "Nova tarefa"
        )
        assert payload["properties"]["Status"]["select"]["name"] == "A fazer"
        assert payload["properties"]["Prioridade"]["select"]["name"] == "Alta"

    def test_create_task_sem_notion_configurado_retorna_vazio(self):
        from agents import notion_sync

        with patch.object(notion_sync, "NOTION_TOKEN", ""):
            page_id = notion_sync.create_notion_task("Tarefa sem token")

        assert page_id == ""

    def test_create_task_envia_horario_previsto_como_date(self):
        """'Horário previsto' deve ser enviado como property date, não rich_text."""
        from agents import notion_sync

        ok = _mock_response(200, {"id": "new-page-date"})
        with patch("requests.request", return_value=ok) as mock_req:
            notion_sync.create_notion_task(
                title="Com horário",
                scheduled_time="2026-04-07 14:30",
            )

        payload = mock_req.call_args[1]["json"]
        hp = payload["properties"]["Horário previsto"]
        assert "date" in hp, "deve ser property do tipo date, não rich_text"
        assert hp["date"]["start"].startswith("2026-04-07T14:30")

    def test_create_task_aceita_hhmm_puro_como_hoje(self):
        """Passar só 'HH:MM' deve virar data de hoje + hora."""
        from datetime import date

        from agents import notion_sync

        ok = _mock_response(200, {"id": "new-page-hhmm"})
        with patch("requests.request", return_value=ok) as mock_req:
            notion_sync.create_notion_task(
                title="Só hora",
                scheduled_time="09:00",
            )

        payload = mock_req.call_args[1]["json"]
        hp = payload["properties"]["Horário previsto"]
        assert hp["date"]["start"].startswith(f"{date.today().isoformat()}T09:00")


class TestNormalizeTimeSlot:
    def test_hhmm_puro(self):
        from agents.notion_sync import _normalize_time_slot

        assert _normalize_time_slot("09:00") == "09:00-10:00"

    def test_hhmm_range(self):
        from agents.notion_sync import _normalize_time_slot

        assert _normalize_time_slot("09:00-10:30") == "09:00-10:30"

    def test_datetime_completo_nao_confunde_com_dash_da_data(self):
        """'2026-04-07 09:00' não pode virar '2026-04' quebrado."""
        from agents.notion_sync import _normalize_time_slot

        assert _normalize_time_slot("2026-04-07 09:00") == "09:00-10:00"

    def test_iso_datetime(self):
        from agents.notion_sync import _normalize_time_slot

        assert _normalize_time_slot("2026-04-07T09:00:00") == "09:00-10:00"

    def test_string_sem_horario_retorna_original(self):
        from agents.notion_sync import _normalize_time_slot

        assert _normalize_time_slot("manhã") == "manhã"


class TestAgendaSync:
    def test_sync_tasks_to_local_atualiza_tarefa_existente(self, mem):
        from agents import notion_sync

        task_id = mem.create_task(
            "Troia antiga",
            priority="Baixa",
            scheduled_time="09:00",
            notion_page_id="page-123",
        )

        with patch.object(
            notion_sync,
            "fetch_notion_tasks",
            return_value=[
                {
                    "notion_page_id": "page-123",
                    "title": "Troia",
                    "status": "Em progresso",
                    "priority": "Alta",
                    "scheduled_time": "11h",
                    "actual_time": "",
                }
            ],
        ):
            count = notion_sync.sync_tasks_to_local()

        task = mem.get_task(task_id)
        assert count == 0
        assert task["title"] == "Troia"
        assert task["status"] == "Em progresso"
        assert task["priority"] == "Alta"
        assert task["scheduled_time"] == "11h"

    def test_maybe_create_agenda_block_cria_bloco_local(self, mem):
        from agents import notion_sync

        notion_sync._maybe_create_agenda_block(
            7,
            {
                "title": "Planejamento",
                "status": "A fazer",
                "scheduled_time": "09:00",
                "notion_page_id": "page-123",
            },
        )

        blocos = mem.get_today_agenda()
        assert len(blocos) == 1
        assert blocos[0]["task_title"] == "Planejamento"
        assert blocos[0]["task_id"] == 7
        assert blocos[0]["notion_page_id"] == "page-123"
        assert blocos[0]["time_slot"] == "09:00-10:00"

    def test_maybe_create_agenda_block_respeita_data_futura(self, mem):
        """Tarefa com data+hora futura deve criar bloco NA DATA REAL, não hoje."""
        from agents import notion_sync

        notion_sync._maybe_create_agenda_block(
            8,
            {
                "title": "Reunião amanhã",
                "status": "A fazer",
                "scheduled_time": "2026-04-08 14:00",
                "notion_page_id": "page-fut",
            },
        )

        # Não deve criar nada hoje
        blocos_hoje = mem.get_today_agenda()
        assert all(b.get("task_id") != 8 for b in blocos_hoje)

        # Deve criar bloco na data alvo
        blocos_amanha = mem.get_agenda_for_date("2026-04-08")
        assert len(blocos_amanha) == 1
        assert blocos_amanha[0]["task_id"] == 8
        assert blocos_amanha[0]["time_slot"] == "14:00-15:00"
        assert blocos_amanha[0]["block_date"] == "2026-04-08"

    def test_maybe_create_agenda_block_pula_quando_so_data(self, mem):
        """Tarefa com APENAS data (sem hora) NÃO deve criar bloco automático."""
        from agents import notion_sync

        notion_sync._maybe_create_agenda_block(
            9,
            {
                "title": "Coisa pra fazer",
                "status": "A fazer",
                "scheduled_time": "2026-04-08",
                "notion_page_id": "page-no-hour",
            },
        )

        # Nenhum bloco deve nascer — nem hoje, nem na data
        assert mem.get_today_agenda() == []
        assert mem.get_agenda_for_date("2026-04-08") == []

    def test_maybe_create_agenda_block_aceita_iso_datetime(self, mem):
        """ISO datetime do Notion (com timezone) também deve funcionar."""
        from agents import notion_sync

        notion_sync._maybe_create_agenda_block(
            10,
            {
                "title": "Sprint planning",
                "status": "A fazer",
                "scheduled_time": "2026-04-08 09:30",
                "notion_page_id": "page-iso",
            },
        )

        blocos = mem.get_agenda_for_date("2026-04-08")
        assert len(blocos) == 1
        assert blocos[0]["time_slot"] == "09:30-10:30"
        assert blocos[0]["task_id"] == 10

    def test_maybe_create_agenda_block_nao_duplica_em_data_futura(self, mem):
        """Rodar duas vezes não deve criar bloco duplicado."""
        from agents import notion_sync

        payload = {
            "title": "X",
            "status": "A fazer",
            "scheduled_time": "2026-04-08 10:00",
            "notion_page_id": "page-dup",
        }
        notion_sync._maybe_create_agenda_block(11, payload)
        notion_sync._maybe_create_agenda_block(11, payload)

        blocos = mem.get_agenda_for_date("2026-04-08")
        assert len(blocos) == 1

    def test_sync_agenda_range_to_local_importa_blocos(self, mem):
        from agents import notion_sync

        with patch.object(
            notion_sync,
            "fetch_agenda_range_from_notion",
            return_value=[
                {
                    "notion_page_id": "agenda-1",
                    "date": "2026-03-20",
                    "time_slot": "09:00-10:00",
                    "task_title": "Review",
                    "completed": False,
                    "raw_block": "09:00-10:00 — Review",
                }
            ],
        ):
            count = notion_sync.sync_agenda_range_to_local("2026-03-20", "2026-03-20")

        assert count == 1
        blocos = mem.get_agenda_for_date("2026-03-20")
        assert len(blocos) == 1
        assert blocos[0]["task_title"] == "Review"
