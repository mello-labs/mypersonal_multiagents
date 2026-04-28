# =============================================================================
# agents/orchestrator.py — Agente orquestrador central
# =============================================================================
# Recebe input do usuário (texto livre), decide qual agente acionar,
# delega via handoffs e consolida as respostas em linguagem natural.
#
# Fluxo de handoff:
#   Usuário → Orchestrator → [Scheduler | FocusGuard | NotionSync | Validator]
#                                      ↓
#                          Resposta consolidada → Usuário
#
# O Orchestrator usa o GPT-4o-mini como "roteador inteligente": o LLM decide
# qual combinação de agentes acionar e em que ordem.

import json
import os
import re
import sys
from datetime import datetime
from typing import Optional

# Garante que o diretório raiz está no sys.path

# Importa os agentes especialistas
from agents import (  # noqa: E402
    calendar_sync,
    capture_agent,
    focus_guard,
    notion_sync,
    retrospective,
    scheduler,
    validator,
)
from agents.persona_manager import (  # noqa: E402
    get_direct_prompt,
    get_persona,
    get_synthesis_prompt,
    get_system_prompt,
    get_temperature,
)
from core import memory, notifier  # noqa: E402
from core.openai_utils import chat_completions  # noqa: E402

AGENT_NAME = "orchestrator"


# ---------------------------------------------------------------------------
# Descrição dos agentes disponíveis (para o LLM do Orchestrator)
# ---------------------------------------------------------------------------

AGENTS_REGISTRY = {
    "scheduler": {
        "description": "Gerencia blocos de tempo, agenda diária, priorização de tarefas.",
        "actions": [
            "get_today_schedule",
            "add_block",
            "complete_block",
            "suggest_agenda",
            "get_prioritized_tasks",
        ],
    },
    "focus_guard": {
        "description": "Monitora foco, gerencia sessões Pomodoro, emite alertas de desvio.",
        "actions": [
            "start_guard",
            "stop_guard",
            "force_check",
            "start_session",
            "end_session",
            "status",
            "get_alerts",
        ],
    },
    "notion_sync": {
        "description": "Cria/atualiza tarefas e agenda no Notion via API REST.",
        "actions": [
            "create_task",
            "update_status",
            "sync_from_notion",
            "get_today_agenda",
        ],
    },
    "validator": {
        "description": "Valida cruzando evidências se uma tarefa foi realmente concluída.",
        "actions": [
            "validate_task",
            "validate_all",
            "get_evidence",
        ],
    },
    "retrospective": {
        "description": "Gera relatório de retrospectiva semanal com métricas e insights.",
        "actions": ["run", "metrics_only"],
    },
    "calendar_sync": {
        "description": "Integra Google Calendar como capacidade opcional de agenda — importa eventos e exporta blocos quando ativado.",
        "actions": [
            "import_today",
            "fetch_today",
            "fetch_week",
            "export_block",
            "status",
        ],
    },
    "capture_agent": {
        "description": (
            "Segundo cérebro: recebe texto livre e roteia para o database correto "
            "do NEØ Command Center (Projetos / Tarefas / Decisões / Work Log / Integrations). "
            "Use quando o usuário mandar uma anotação, ideia, tarefa, decisão, "
            "relato do dia ou link sem especificar destino."
        ),
        "actions": [
            "capture",
            "classify",
            "capture_log",
            "capture_task",
            "capture_decision",
            "capture_project",
            "capture_integration",
        ],
    },
}


# Prompt do Orchestrator para roteamento de intenções
_ROUTING_PROMPT_FALLBACK = f"""Você é o Orchestrator de um sistema de gestão pessoal com múltiplos agentes.
Dado um input do usuário, determine:
1. Qual(is) agente(s) acionar
2. Qual ação executar em cada agente
3. Os parâmetros necessários para cada ação

Agentes disponíveis:
{json.dumps(AGENTS_REGISTRY, ensure_ascii=False, indent=2)}

Retorne um JSON com:
{{
  "intent": "descrição breve da intenção do usuário",
  "handoffs": [
    {{
      "agent": "nome_do_agente",
      "payload": {{
        "action": "nome_da_ação",
        ... outros parâmetros ...
      }}
    }}
  ],
  "requires_user_input": false,
  "clarification_question": null
}}

Regras importantes:
- Se precisar de mais informações, defina requires_user_input=true e clarification_question
- Para criar tarefas, sempre envie para notion_sync E scheduler
- Para marcar tarefa como concluída, sempre passe pelo validator ANTES de confirmar
- Para verificar agenda, combine scheduler + notion_sync
- Se o usuário perguntar sobre foco/progresso, acione o focus_guard
- Se o usuário perguntar sobre atraso, alertas, avisos, notificações ou status do sistema, consulte os agentes.
- Não responda diretamente sobre estado operacional se você não consultou dados reais.
- Quando múltiplos agentes são necessários, ordene-os pela lógica de execução
- Se nenhum agente for necessário, retorne handoffs vazio e responda diretamente
"""


# Prompt base para síntese — será composto com a persona ativa
_SYNTHESIS_BASE = """Você é o Orchestrator de um sistema de gestão pessoal.
Baseado nos resultados dos agentes especialistas, forneça uma resposta clara,
concisa e útil ao usuário.

Nunca invente tarefas, alertas, horários ou estados do sistema. Só mencione itens que
apareçam explicitamente nos resultados recebidos. Se faltar dado, diga que não foi possível
confirmar.
Não mencione detalhes técnicos internos (IDs de banco, payloads JSON, etc.)."""

_DIRECT_BASE = """Você é um assistente de gestão pessoal.
Nunca afirme estado do sistema, tarefas, alertas ou agenda sem dados explícitos no contexto.
Se a pergunta depender do estado do sistema e ele não estiver disponível, diga que precisa verificar."""

# Mantém compatibilidade — usados como fallback
SYNTHESIS_PROMPT = _SYNTHESIS_BASE
DIRECT_RESPONSE_PROMPT = _DIRECT_BASE


def _get_routing_prompt() -> str:
    return _ROUTING_PROMPT_FALLBACK


def _build_synthesis_prompt(persona_id: Optional[str] = None) -> str:
    """Compõe o prompt de síntese com a persona ativa."""
    base_prompt = _SYNTHESIS_BASE
    persona_override = get_synthesis_prompt(persona_id)
    if persona_override:
        return f"{base_prompt}\n\nEstilo de resposta:\n{persona_override}"
    return base_prompt


def _build_direct_prompt(persona_id: Optional[str] = None) -> str:
    """Compõe o prompt de resposta direta com a persona ativa."""
    base_prompt = _DIRECT_BASE
    persona_override = get_direct_prompt(persona_id)
    if persona_override:
        return f"{base_prompt}\n\nEstilo de resposta:\n{persona_override}"
    return base_prompt


def _context_history_text(context: Optional[dict]) -> str:
    if not context:
        return ""

    history = context.get("chat_history", [])
    if not isinstance(history, list):
        return ""

    lines = []
    for item in history[-6:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        label = "Usuário" if role == "user" else "Assistente"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _build_rule_based_route(
    user_input: str, context: Optional[dict] = None
) -> Optional[dict]:
    history_text = _context_history_text(context)
    combined = f"{history_text}\nUsuário: {user_input}".lower()

    mentions_delay = bool(re.search(r"\batras\w*", combined))
    mentions_alert = any(
        term in combined
        for term in (
            "alerta",
            "alertas",
            "aviso",
            "avisado",
            "notificação",
            "notificações",
        )
    )
    mentions_focus = any(
        term in combined for term in ("foco", "desvio", "on track", "fora do plano")
    )
    asks_status = any(
        term in combined
        for term in (
            "como está",
            "qual é o status",
            "status atual",
            "situação",
            "meu sistema",
        )
    )
    asks_next_step = any(
        term in combined
        for term in ("o que fazer", "como devo agir", "me ajude", "indique o que fazer")
    )
    asks_capability = any(
        term in combined
        for term in (
            "o que voce consegue",
            "o que você consegue",
            "o que pode fazer",
            "o que voce pode fazer",
            "capaz de fazer",
            "seus limites",
            "suas capacidades",
            "node infiltrado",
            "nó infiltrado",
        )
    )
    mentions_deploy = any(
        term in combined
        for term in (
            "railway",
            "deploy",
            "deployado",
            "produção",
            "producao",
            "codigo deployado",
            "código deployado",
        )
    )

    if asks_capability and (mentions_deploy or "sistema" in combined):
        return {
            "intent": "capabilities_runtime",
            "handoffs": [],
            "requires_user_input": False,
            "clarification_question": None,
        }

    if (
        mentions_delay
        or (mentions_alert and (asks_status or asks_next_step))
        or (mentions_focus and asks_status)
    ):
        return {
            "intent": "verificar atrasos, alertas e foco atual",
            "handoffs": [
                {"agent": "focus_guard", "payload": {"action": "force_check"}},
                {"agent": "focus_guard", "payload": {"action": "get_alerts"}},
                {"agent": "scheduler", "payload": {"action": "get_prioritized_tasks"}},
            ],
            "requires_user_input": False,
            "clarification_question": None,
        }

    if asks_status and any(
        term in combined for term in ("agenda", "tarefas", "tarefa", "foco", "sistema")
    ):
        return {
            "intent": "status operacional do sistema",
            "handoffs": [
                {"agent": "focus_guard", "payload": {"action": "status"}},
                {"agent": "focus_guard", "payload": {"action": "get_alerts"}},
                {"agent": "scheduler", "payload": {"action": "get_today_schedule"}},
                {"agent": "scheduler", "payload": {"action": "get_prioritized_tasks"}},
            ],
            "requires_user_input": False,
            "clarification_question": None,
        }

    # Fallback determinístico: texto livre sem intent reconhecida → capture_agent.
    # Evita que anotações, ideias e relatos caiam no fluxo LLM sem destino.
    _CAPTURE_SKIP = (
        "python",
        "error",
        "erro",
        "bug",
        "traceback",
        "exception",
        "como ",
        "qual ",
        "quais ",
        "quando ",
        "por que",
        "explica",
        "ajuda",
        "help",
    )
    if not any(skip in combined for skip in _CAPTURE_SKIP) and len(user_input.split()) >= 3:
        return {
            "intent": "capturar anotação livre",
            "handoffs": [
                {"agent": "capture_agent", "payload": {"action": "capture", "text": user_input}}
            ],
            "requires_user_input": False,
            "clarification_question": None,
        }

    return None


def _result_for(handoff_results: list[dict], agent: str, action: str) -> dict:
    for item in handoff_results:
        if item.get("agent") == agent and item.get("action") == action:
            return item.get("result", {}) or {}
    return {}


def _format_focus_response(handoff_results: list[dict]) -> Optional[str]:
    force_check = _result_for(handoff_results, "focus_guard", "force_check")
    focus_status = _result_for(handoff_results, "focus_guard", "status")
    alerts_result = _result_for(handoff_results, "focus_guard", "get_alerts")
    tasks_result = _result_for(handoff_results, "scheduler", "get_prioritized_tasks")
    schedule_result = _result_for(handoff_results, "scheduler", "get_today_schedule")

    if not any(
        (force_check, focus_status, alerts_result, tasks_result, schedule_result)
    ):
        return None

    alerts = alerts_result.get("alerts", [])
    prioritized_tasks = tasks_result.get("tasks", [])
    blocks = schedule_result.get("blocks", [])

    lines: list[str] = []

    if force_check:
        progress = force_check.get("progress", {})
        load = progress.get("load", {})
        overdue_blocks = progress.get("overdue_blocks", [])
        analysis = force_check.get("analysis", {})
        overdue_count = load.get("overdue", len(overdue_blocks))

        if overdue_count:
            lines.append(f"Encontrei {overdue_count} bloco(s) atrasado(s) no sistema.")
            for block in overdue_blocks[:3]:
                lines.append(
                    f"{block.get('time_slot', '?')} | {block.get('task_title', 'Sem título')}"
                )
        else:
            lines.append("Não encontrei bloco atrasado neste instante.")

        if alerts:
            latest = alerts[0]
            lines.append(f"Há {len(alerts)} alerta(s) pendente(s).")
            if latest.get("message"):
                lines.append(f"Último alerta: {latest['message']}")
        else:
            lines.append("Não há alertas pendentes registrados.")

        if analysis.get("recommendation"):
            lines.append(f"Ação recomendada: {analysis['recommendation']}")
        elif overdue_blocks:
            first = overdue_blocks[0]
            lines.append(
                f"Ação recomendada: retome '{first.get('task_title', 'a tarefa atrasada')}' agora ou reprograme esse bloco antes de puxar outra frente."
            )
    else:
        running = focus_status.get("running")
        on_track = focus_status.get("on_track")
        if running is not None:
            lines.append(
                f"Focus Guard: {'ativo' if running else 'desligado'} | "
                f"{'no plano' if on_track else 'com desvio'}"
            )
        if alerts:
            lines.append(f"Alertas pendentes: {len(alerts)}.")
        else:
            lines.append("Alertas pendentes: 0.")

        if blocks:
            completed = sum(1 for block in blocks if block.get("completed"))
            lines.append(
                f"Agenda de hoje: {completed}/{len(blocks)} blocos concluídos."
            )

    if prioritized_tasks:
        top = prioritized_tasks[0]
        label = top.get("title", "Sem título")
        priority = top.get("priority", "Média")
        status = top.get("status", "A fazer")
        lines.append(f"Prioridade operacional agora: '{label}' [{priority}, {status}].")

    return "\n".join(lines)


def _runtime_capabilities_response(context: Optional[dict] = None) -> str:
    """Resposta determinística para perguntas sobre capacidade do runtime."""
    summary = {}
    if context and isinstance(context.get("system_summary"), dict):
        summary = context["system_summary"]
    tasks = summary.get("tasks", {})
    agenda = summary.get("agenda_today", {})
    alerts = summary.get("alerts", {})

    return (
        "Sim. Aqui no chat voce fala com o runtime deployado desta aplicacao.\n"
        "Eu consigo operar o sistema pelos agentes: status de foco, alertas, agenda, tarefas, sync e validacoes.\n"
        f"Snapshot agora: tarefas {tasks.get('total', 0)} | agenda {agenda.get('completed', 0)}/{agenda.get('total_blocks', 0)} blocos | alertas {alerts.get('pending', 0)}.\n"
        "Limites reais: nao tenho shell do servidor por este chat, nao rodo git/comandos de infra e nao publico nada externo sem gate."
    )


def _is_parrot_reply(user_input: str, reply: str) -> bool:
    """Evita respostas que apenas repetem a mensagem do usuário."""
    norm_user = re.sub(r"\W+", "", user_input or "", flags=re.UNICODE).lower()
    norm_reply = re.sub(r"\W+", "", reply or "", flags=re.UNICODE).lower()
    if not norm_user or not norm_reply:
        return False
    return norm_reply == norm_user or norm_reply.startswith(norm_user)


# ---------------------------------------------------------------------------
# Roteamento de intenção via LLM
# ---------------------------------------------------------------------------


def route_intent(user_input: str, context: Optional[dict] = None) -> dict:
    """
    Analisa o input do usuário e decide quais agentes acionar.

    Returns:
        Dict com 'intent', 'handoffs', 'requires_user_input', 'clarification_question'
    """
    rule_based = _build_rule_based_route(user_input, context)
    if rule_based:
        notifier.agent_event(
            f"Intent heurística: '{rule_based.get('intent', '?')}' | "
            f"Handoffs: {[h['agent'] for h in rule_based.get('handoffs', [])]}",
            AGENT_NAME,
        )
        return rule_based

    # Contexto adicional para o LLM (estado atual do sistema)
    system_context = {
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "focus_guard_running": focus_guard.is_running(),
        "active_focus_session": memory.get_active_focus_session(),
        "pending_tasks_count": len(memory.get_tasks_by_status("A fazer")),
        "in_progress_tasks_count": len(memory.get_tasks_by_status("Em progresso")),
    }

    if context:
        system_context.update(context)

    messages = [
        {"role": "system", "content": _get_routing_prompt()},
        {
            "role": "user",
            "content": f"""Contexto do sistema:
{json.dumps(system_context, ensure_ascii=False, indent=2, default=str)}

Input do usuário: "{user_input}"

Retorne o JSON de roteamento.""",
        },
    ]

    try:
        response = chat_completions(
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        routing = json.loads(response.choices[0].message.content)
        notifier.agent_event(
            f"Intent: '{routing.get('intent', '?')}' | "
            f"Handoffs: {[h['agent'] for h in routing.get('handoffs', [])]}",
            AGENT_NAME,
        )
        return routing
    except Exception as e:
        notifier.error(f"Erro no roteamento: {e}", AGENT_NAME)
        return {
            "intent": "unknown",
            "handoffs": [],
            "requires_user_input": True,
            "clarification_question": "Não entendi sua solicitação. Pode reformular?",
        }


# ---------------------------------------------------------------------------
# Execução de handoffs
# ---------------------------------------------------------------------------

_AGENT_HANDLERS = {
    "scheduler": scheduler.handle_handoff,
    "focus_guard": focus_guard.handle_handoff,
    "notion_sync": notion_sync.handle_handoff,
    "validator": validator.handle_handoff,
    "retrospective": retrospective.handle_handoff,
    "calendar_sync": calendar_sync.handle_handoff,
    "capture_agent": capture_agent.handle_handoff,
}


def execute_handoffs(handoffs: list[dict]) -> list[dict]:
    """
    Executa a lista de handoffs em sequência.
    Cada handoff pode referenciar resultados de handoffs anteriores.

    Returns:
        Lista de resultados com agent, action, status, result.
    """
    results = []
    accumulated_context: dict = {}

    for handoff in handoffs:
        agent_name = handoff.get("agent", "")
        payload = handoff.get("payload", {})

        handler = _AGENT_HANDLERS.get(agent_name)
        if not handler:
            notifier.error(f"Agente '{agent_name}' não encontrado.", AGENT_NAME)
            results.append(
                {
                    "agent": agent_name,
                    "action": payload.get("action", "?"),
                    "status": "error",
                    "result": {"error": f"Agente '{agent_name}' não registrado."},
                }
            )
            continue

        notifier.agent_event(
            f"Delegando para {agent_name}.{payload.get('action', '?')}...", AGENT_NAME
        )

        # Injeta contexto acumulado (resultados anteriores podem ser necessários)
        if accumulated_context:
            payload["_context"] = accumulated_context

        response = handler(payload)
        results.append(
            {
                "agent": agent_name,
                "action": payload.get("action", "?"),
                "status": response.get("status", "unknown"),
                "result": response.get("result", {}),
            }
        )

        # Acumula contexto para handoffs subsequentes
        accumulated_context[agent_name] = response.get("result", {})

    return results


# ---------------------------------------------------------------------------
# Síntese da resposta final
# ---------------------------------------------------------------------------


def synthesize_response(
    user_input: str,
    intent: str,
    handoff_results: list[dict],
    context: Optional[dict] = None,
    persona_id: Optional[str] = None,
) -> str:
    """
    Usa o GPT-GPT-4o-mini para sintetizar os resultados dos agentes em resposta natural.
    """
    fast_path = _format_focus_response(handoff_results)
    if fast_path:
        return fast_path

    results_str = json.dumps(handoff_results, ensure_ascii=False, indent=2, default=str)
    history_text = _context_history_text(context)
    history_block = f"Histórico recente:\n{history_text}\n\n" if history_text else ""

    synthesis_prompt = _build_synthesis_prompt(persona_id)
    persona_system = get_system_prompt(persona_id)
    if persona_system:
        synthesis_prompt = f"{synthesis_prompt}\n\nPersonalidade:\n{persona_system}"

    messages = [
        {"role": "system", "content": synthesis_prompt},
        {
            "role": "user",
            "content": f"""{history_block}Input original do usuário: "{user_input}"
Intenção detectada: {intent}

Resultados dos agentes especialistas:
{results_str}

Forneça uma resposta útil e clara ao usuário.""",
        },
    ]

    try:
        response = chat_completions(
            messages=messages,
            temperature=get_temperature(persona_id, "synthesis"),
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        notifier.error(f"Erro na síntese: {e}", AGENT_NAME)
        # Fallback: lista resultados diretamente
        lines = ["Resultado das ações executadas:"]
        for r in handoff_results:
            status_emoji = "✅" if r["status"] == "success" else "❌"
            lines.append(f"{status_emoji} {r['agent']}.{r['action']}: {r['status']}")
            if r["status"] == "error":
                lines.append(f"   Erro: {r['result'].get('error', '?')}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline principal do Orchestrator
# ---------------------------------------------------------------------------


def process(
    user_input: str,
    context: Optional[dict] = None,
    persona_id: Optional[str] = None,
) -> str:
    """
    Pipeline completo: input → roteamento → execução → síntese → resposta.

    Args:
        user_input: Comando/pergunta do usuário em linguagem natural.
        context:    Contexto extra opcional (ex: conversa anterior).
        persona_id: ID da persona ativa (None = persona padrão).

    Returns:
        Resposta final em texto para exibir ao usuário.
    """
    notifier.separator("ORCHESTRATOR")
    persona = get_persona(persona_id)
    persona_label = persona.get("short_name", "default") if persona else "default"
    notifier.agent_event(
        f'[{persona_label}] Input: "{user_input[:80]}{"..." if len(user_input) > 80 else ""}"',
        AGENT_NAME,
    )

    # 1. Rotear intenção
    routing = route_intent(user_input, context)

    # 2. Verificar se precisa de mais informações
    if routing.get("requires_user_input"):
        question = routing.get(
            "clarification_question", "Pode detalhar sua solicitação?"
        )
        notifier.warning(f"Preciso de mais informações: {question}", AGENT_NAME)
        return f"❓ {question}"

    # 3. Executar handoffs
    handoffs = routing.get("handoffs", [])
    if not handoffs:
        if routing.get("intent") == "capabilities_runtime":
            return _runtime_capabilities_response(context)
        notifier.info("Nenhum agente necessário — respondendo diretamente.", AGENT_NAME)
        return _direct_response(user_input, context, persona_id)

    results = execute_handoffs(handoffs)

    # 4. Sintetizar resposta
    response = synthesize_response(
        user_input=user_input,
        intent=routing.get("intent", ""),
        handoff_results=results,
        context=context,
        persona_id=persona_id,
    )

    notifier.separator()
    return response


def _direct_response(
    user_input: str,
    context: Optional[dict] = None,
    persona_id: Optional[str] = None,
) -> str:
    """Resposta direta do Orchestrator para perguntas simples sem agentes."""
    history_text = _context_history_text(context)
    history_block = f"Histórico recente:\n{history_text}\n\n" if history_text else ""

    direct_prompt = _build_direct_prompt(persona_id)
    persona_system = get_system_prompt(persona_id)
    if persona_system:
        direct_prompt = f"{direct_prompt}\n\nPersonalidade:\n{persona_system}"

    try:
        response = chat_completions(
            messages=[
                {
                    "role": "system",
                    "content": direct_prompt,
                },
                {
                    "role": "user",
                    "content": f"{history_block}Pergunta atual: {user_input}",
                },
            ],
            temperature=get_temperature(persona_id, "direct"),
        )
        content = response.choices[0].message.content.strip()
        if _is_parrot_reply(user_input, content):
            return (
                "Entendi seu ponto. Se quiser, eu te respondo de forma objetiva em uma destas frentes: "
                "status do sistema, foco/alertas, agenda/tarefas ou capacidade do deploy."
            )
        return content
    except Exception as e:
        return f"Desculpe, ocorreu um erro: {e}"


# ---------------------------------------------------------------------------
# Comandos rápidos do Orchestrator (shortcuts)
# ---------------------------------------------------------------------------


def quick_status() -> str:
    """Gera um status rápido completo do sistema."""
    return process("Qual é o status atual da minha agenda e foco hoje?")


def quick_add_task(title: str, priority: str = "Média", time_slot: str = "") -> str:
    """Atalho para adicionar uma tarefa rapidamente."""
    msg = f"Adicionar tarefa: '{title}', prioridade {priority}"
    if time_slot:
        msg += f", horário {time_slot}"
    return process(msg)


def quick_complete_task(task_id: int) -> str:
    """Atalho para marcar uma tarefa como concluída (com validação)."""
    return process(f"Marcar tarefa {task_id} como concluída")


def quick_start_focus(task_id: int, task_title: str, minutes: int = 25) -> str:
    """Atalho para iniciar uma sessão de foco."""
    return process(
        f"Iniciar sessão de foco na tarefa {task_id} ({task_title}) por {minutes} minutos"
    )


def get_system_summary() -> dict:
    """Retorna um resumo completo do estado do sistema (sem LLM)."""
    all_tasks = memory.list_all_tasks()
    today_agenda = memory.get_today_agenda()
    active_session = memory.get_active_focus_session()
    pending_alerts = memory.get_pending_alerts()
    focus_state = memory.get_state("focus_guard_state", {})

    return {
        "tasks": {
            "total": len(all_tasks),
            "a_fazer": sum(1 for t in all_tasks if t["status"] == "A fazer"),
            "em_progresso": sum(1 for t in all_tasks if t["status"] == "Em progresso"),
            "concluido": sum(1 for t in all_tasks if t["status"] == "Concluído"),
        },
        "agenda_today": {
            "total_blocks": len(today_agenda),
            "completed": sum(1 for b in today_agenda if b.get("completed")),
        },
        "focus": {
            "guard_running": focus_guard.is_running(),
            "active_session": active_session,
            "last_check": focus_state.get("last_check"),
            "on_track": focus_state.get("on_track", True),
        },
        "alerts": {
            "pending": len(pending_alerts),
        },
    }
