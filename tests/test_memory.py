"""
test_memory.py — Testes das operações CRUD do core/memory.py.
Usa banco SQLite em arquivo temporário (sem afetar memory.db de produção).
"""

from datetime import date

# =============================================================================
# TASKS
# =============================================================================


class TestTasks:
    def test_create_task_retorna_id(self, mem):
        task_id = mem.create_task("Estudar Python", priority="Alta")
        assert isinstance(task_id, int)
        assert task_id > 0

    def test_get_task_retorna_dados_corretos(self, mem):
        task_id = mem.create_task(
            "Reunião semanal", priority="Média", scheduled_time="09:00"
        )
        task = mem.get_task(task_id)

        assert task is not None
        assert task["title"] == "Reunião semanal"
        assert task["priority"] == "Média"
        assert task["status"] == "A fazer"
        assert task["scheduled_time"] == "09:00"

    def test_get_task_inexistente_retorna_none(self, mem):
        assert mem.get_task(9999) is None

    def test_update_task_status(self, mem):
        task_id = mem.create_task("Deploy produção")
        mem.update_task_status(task_id, "Em progresso")

        task = mem.get_task(task_id)
        assert task["status"] == "Em progresso"

    def test_update_task_status_com_horario_real(self, mem):
        task_id = mem.create_task("Code review")
        mem.update_task_status(task_id, "Concluído", actual_time="14:30")

        task = mem.get_task(task_id)
        assert task["status"] == "Concluído"
        assert task["actual_time"] == "14:30"

    def test_update_task_campos_gerais(self, mem):
        task_id = mem.create_task("Tarefa original", priority="Baixa")
        mem.update_task(
            task_id,
            title="Tarefa atualizada",
            priority="Alta",
            scheduled_time="11:00",
            notion_page_id="page-42",
        )

        task = mem.get_task(task_id)
        assert task["title"] == "Tarefa atualizada"
        assert task["priority"] == "Alta"
        assert task["scheduled_time"] == "11:00"
        assert task["notion_page_id"] == "page-42"

    def test_update_task_remove_indice_notion_antigo(self, mem):
        task_id = mem.create_task("Sync com Notion", notion_page_id="page-1")

        mem.update_task(task_id, notion_page_id="page-2")

        task = mem.get_task(task_id)
        assert task["notion_page_id"] == "page-2"
        assert mem._r().get("tasks:notion:page-1") is None
        assert mem._r().get("tasks:notion:page-2") == str(task_id)

    def test_list_all_tasks(self, mem):
        mem.create_task("Tarefa A")
        mem.create_task("Tarefa B")
        mem.create_task("Tarefa C")

        tasks = mem.list_all_tasks()
        assert len(tasks) == 3

    def test_get_tasks_by_status(self, mem):
        t1 = mem.create_task("Tarefa pendente 1")
        t2 = mem.create_task("Tarefa pendente 2")
        t3 = mem.create_task("Tarefa concluída")
        mem.update_task_status(t3, "Concluído")

        pendentes = mem.get_tasks_by_status("A fazer")
        assert len(pendentes) == 2

        concluidas = mem.get_tasks_by_status("Concluído")
        assert len(concluidas) == 1

    def test_update_task_notion_id(self, mem):
        task_id = mem.create_task("Sync com Notion")
        mem.update_task_notion_id(task_id, "abc-123-notion-page")

        task = mem.get_task(task_id)
        assert task["notion_page_id"] == "abc-123-notion-page"

    def test_create_task_com_notion_page_id(self, mem):
        task_id = mem.create_task(
            "Importada do Notion",
            notion_page_id="notion-xyz-456",
        )
        task = mem.get_task(task_id)
        assert task["notion_page_id"] == "notion-xyz-456"


# =============================================================================
# AGENDA BLOCKS
# =============================================================================


class TestAgendaBlocks:
    def test_create_agenda_block(self, mem):
        block_id = mem.create_agenda_block(
            block_date="2026-03-26",
            time_slot="09:00-10:00",
            task_title="Deep work",
        )
        assert isinstance(block_id, int)
        assert block_id > 0

    def test_get_today_agenda_retorna_apenas_hoje(self, mem):
        today = date.today().isoformat()
        mem.create_agenda_block(today, "09:00-10:00", "Tarefa hoje")
        mem.create_agenda_block("2026-01-01", "09:00-10:00", "Tarefa passado")

        blocos = mem.get_today_agenda()
        assert len(blocos) == 1
        assert blocos[0]["task_title"] == "Tarefa hoje"

    def test_mark_block_completed(self, mem):
        today = date.today().isoformat()
        block_id = mem.create_agenda_block(today, "10:00-11:00", "Reunião")

        mem.mark_block_completed(block_id, completed=True)
        blocos = mem.get_today_agenda()
        assert blocos[0]["completed"] == 1

    def test_mark_block_uncompleted(self, mem):
        today = date.today().isoformat()
        block_id = mem.create_agenda_block(today, "10:00-11:00", "Reunião")
        mem.mark_block_completed(block_id, True)
        mem.mark_block_completed(block_id, False)

        blocos = mem.get_today_agenda()
        assert blocos[0]["completed"] == 0

    def test_update_block_e_get_block(self, mem):
        today = date.today().isoformat()
        block_id = mem.create_agenda_block(today, "10:00-11:00", "Replanejar sprint")

        mem.update_block(block_id, rescheduled=True, rescheduled_to_block_id=99)
        bloco = mem.get_block(block_id)

        assert bloco["rescheduled"] == 1
        assert bloco["rescheduled_to_block_id"] == 99


# =============================================================================
# FOCUS SESSIONS
# =============================================================================


class TestFocusSessions:
    def test_start_focus_session(self, mem):
        task_id = mem.create_task("Tarefa foco")
        session_id = mem.start_focus_session(task_id, "Tarefa foco", planned_minutes=25)
        assert isinstance(session_id, int)

    def test_get_active_focus_session(self, mem):
        task_id = mem.create_task("Tarefa foco")
        mem.start_focus_session(task_id, "Tarefa foco", planned_minutes=25)

        active = mem.get_active_focus_session()
        assert active is not None
        assert active["task_title"] == "Tarefa foco"
        assert active["status"] == "active"

    def test_end_focus_session(self, mem):
        task_id = mem.create_task("Tarefa foco")
        session_id = mem.start_focus_session(task_id, "Tarefa foco")

        mem.end_focus_session(session_id, status="completed")
        active = mem.get_active_focus_session()
        assert active is None

    def test_get_active_session_sem_sessao_ativa(self, mem):
        assert mem.get_active_focus_session() is None


# =============================================================================
# SYSTEM STATE
# =============================================================================


class TestSystemState:
    def test_set_e_get_state(self, mem):
        mem.set_state("chave_teste", {"valor": 42, "ativo": True})
        resultado = mem.get_state("chave_teste")

        assert resultado == {"valor": 42, "ativo": True}

    def test_get_state_inexistente_retorna_default(self, mem):
        resultado = mem.get_state("nao_existe", default="fallback")
        assert resultado == "fallback"

    def test_set_state_upsert(self, mem):
        mem.set_state("config", "v1")
        mem.set_state("config", "v2")

        assert mem.get_state("config") == "v2"


# =============================================================================
# ALERTS
# =============================================================================


class TestAlerts:
    def test_create_e_get_pending_alerts(self, mem):
        mem.create_alert("deviation_moderate", "Você atrasou 2 blocos.")
        alertas = mem.get_pending_alerts()

        assert len(alertas) == 1
        assert alertas[0]["alert_type"] == "deviation_moderate"
        assert alertas[0]["acknowledged"] == 0

    def test_acknowledge_alert(self, mem):
        alert_id = mem.create_alert("focus_check", "Check-in automático.")
        mem.acknowledge_alert(alert_id)

        pendentes = mem.get_pending_alerts()
        assert len(pendentes) == 0

    def test_list_alerts_retorna_historico_com_ack(self, mem):
        alert_id = mem.create_alert("focus_check", "Check-in automático.")
        mem.acknowledge_alert(alert_id)

        alertas = mem.list_alerts()
        assert len(alertas) == 1
        assert alertas[0]["acknowledged"] == 1


# =============================================================================
# AUDIT EVENTS
# =============================================================================


class TestAuditEvents:
    def test_create_e_list_audit_events(self, mem):
        mem.create_audit_event(
            event_type="auto_reschedule",
            title="Bloco reagendado",
            details="09:00-10:00 → 11:00-12:00",
            level="warning",
            agent="focus_guard",
        )

        eventos = mem.list_audit_events()
        assert len(eventos) == 1
        assert eventos[0]["event_type"] == "auto_reschedule"
        assert eventos[0]["agent"] == "focus_guard"


# =============================================================================
# AGENT HANDOFFS
# =============================================================================


class TestHandoffs:
    def test_log_handoff(self, mem):
        handoff_id = mem.log_handoff(
            source_agent="orchestrator",
            target_agent="notion_sync",
            action="sync_from_notion",
            payload={"page": 1},
        )
        assert isinstance(handoff_id, int)

    def test_update_handoff_result(self, mem):
        handoff_id = mem.log_handoff("orchestrator", "scheduler", "get_schedule")
        mem.update_handoff_result(handoff_id, {"blocks": []}, status="success")
        # Sem exceção = sucesso

    def test_list_recent_handoffs(self, mem):
        mem.log_handoff("orchestrator", "scheduler", "get_schedule")
        handoffs = mem.list_recent_handoffs()
        assert len(handoffs) == 1
