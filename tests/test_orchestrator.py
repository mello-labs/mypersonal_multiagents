from types import SimpleNamespace

import agents.orchestrator as orchestrator


def test_route_intent_usa_fluxo_deterministico_para_atrasos(mem, monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError(
            "LLM não deveria ser chamado para consulta de atraso/alerta"
        )

    monkeypatch.setattr(orchestrator, "chat_completions", fail_if_called)

    routing = orchestrator.route_intent(
        "vejo que não fui avisado do último atraso de tarefa"
    )

    assert routing["intent"] == "verificar atrasos, alertas e foco atual"
    assert [item["agent"] for item in routing["handoffs"]] == [
        "focus_guard",
        "focus_guard",
        "scheduler",
    ]
    assert routing["handoffs"][0]["payload"]["action"] == "force_check"
    assert routing["handoffs"][1]["payload"]["action"] == "get_alerts"


def test_route_intent_considera_historico_no_follow_up(mem, monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("Histórico deveria bastar para o roteamento heurístico")

    monkeypatch.setattr(orchestrator, "chat_completions", fail_if_called)

    routing = orchestrator.route_intent(
        "sim como está dentro do meu sistema me ajude indicando o que fazer",
        context={
            "chat_history": [
                {
                    "role": "user",
                    "content": "vejo que não fui avisado do último atraso de tarefa",
                }
            ]
        },
    )

    assert routing["intent"] == "verificar atrasos, alertas e foco atual"
    assert routing["handoffs"][0]["payload"]["action"] == "force_check"


def test_sintese_factual_para_foco_nao_usa_llm(mem, monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("Resposta factual deveria evitar síntese via LLM")

    monkeypatch.setattr(orchestrator, "chat_completions", fail_if_called)

    handoff_results = [
        {
            "agent": "focus_guard",
            "action": "force_check",
            "status": "success",
            "result": {
                "progress": {
                    "load": {"overdue": 1},
                    "overdue_blocks": [
                        {"time_slot": "11:00-12:00", "task_title": "Troia"}
                    ],
                },
                "analysis": {
                    "recommendation": "Revise a agenda e retome a próxima tarefa pendente."
                },
            },
        },
        {
            "agent": "focus_guard",
            "action": "get_alerts",
            "status": "success",
            "result": {
                "alerts": [{"message": "Você atrasou 1 bloco."}],
                "count": 1,
            },
        },
        {
            "agent": "scheduler",
            "action": "get_prioritized_tasks",
            "status": "success",
            "result": {
                "tasks": [
                    {"title": "Troia", "priority": "Alta", "status": "Em progresso"}
                ],
                "count": 1,
            },
        },
    ]

    response = orchestrator.synthesize_response(
        "como está meu sistema?",
        "verificar atrasos, alertas e foco atual",
        handoff_results,
    )

    assert "Encontrei 1 bloco(s) atrasado(s) no sistema." in response
    assert "11:00-12:00 | Troia" in response
    assert "Há 1 alerta(s) pendente(s)." in response
    assert "Prioridade operacional agora: 'Troia' [Alta, Em progresso]." in response


def test_route_intent_capacidade_runtime_sem_llm(mem, monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("LLM nao deveria ser chamado para capability route")

    monkeypatch.setattr(orchestrator, "chat_completions", fail_if_called)

    routing = orchestrator.route_intent(
        "Voce esta no codigo deployado na Railway, o que e capaz de fazer?"
    )

    assert routing["intent"] == "capabilities_runtime"
    assert routing["handoffs"] == []


def test_process_retorna_capacidades_do_runtime(mem, monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("Nao deveria chamar LLM para capabilities_runtime")

    monkeypatch.setattr(orchestrator, "chat_completions", fail_if_called)

    response = orchestrator.process(
        "Voce esta no codigo deployado na Railway, o que e capaz de fazer?",
        context={
            "system_summary": {
                "tasks": {"total": 5},
                "agenda_today": {"completed": 2, "total_blocks": 4},
                "alerts": {"pending": 1},
            }
        },
    )

    assert "runtime deployado" in response.lower()
    assert "tarefas 5" in response.lower()
    assert "agenda 2/4" in response.lower()
    assert "alertas 1" in response.lower()


def test_direct_response_evita_eco_do_input(mem, monkeypatch):
    parrot = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="e ai NEO"))]
    )

    monkeypatch.setattr(orchestrator, "chat_completions", lambda **kwargs: parrot)

    response = orchestrator._direct_response("e ai NEO")

    assert "status do sistema" in response.lower()
    assert "capacidade do deploy" in response.lower()
