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
# O Orchestrator usa o GPT-4o como "roteador inteligente": o LLM decide
# qual combinação de agentes acionar e em que ordem.

import json
import sys
import os
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL
from core import memory, notifier

# Importa os agentes especialistas
from agents import scheduler, focus_guard, notion_sync, validator, retrospective, calendar_sync

AGENT_NAME = "orchestrator"
_client = OpenAI(api_key=OPENAI_API_KEY)


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
        "description": "Sincroniza agenda com Google Calendar — importa eventos e exporta blocos.",
        "actions": ["import_today", "fetch_today", "fetch_week", "export_block", "status"],
    },
}


# Prompt do Orchestrator para roteamento de intenções
ROUTING_PROMPT = f"""Você é o Orchestrator de um sistema de gestão pessoal com múltiplos agentes.
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
- Quando múltiplos agentes são necessários, ordene-os pela lógica de execução
- Se nenhum agente for necessário, retorne handoffs vazio e responda diretamente
"""


# Prompt para síntese da resposta final
SYNTHESIS_PROMPT = """Você é o Orchestrator de um sistema de gestão pessoal.
Baseado nos resultados dos agentes especialistas, forneça uma resposta clara,
concisa e útil ao usuário em português brasileiro.

Seja direto e prático. Se houver alertas importantes (tarefas atrasadas, desvios de foco),
destaque-os. Use emojis moderadamente para melhorar a legibilidade.
Não mencione detalhes técnicos internos (IDs de banco, payloads JSON, etc.).
"""


# ---------------------------------------------------------------------------
# Roteamento de intenção via LLM
# ---------------------------------------------------------------------------

def route_intent(user_input: str, context: Optional[dict] = None) -> dict:
    """
    Analisa o input do usuário e decide quais agentes acionar.

    Returns:
        Dict com 'intent', 'handoffs', 'requires_user_input', 'clarification_question'
    """
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
        {"role": "system", "content": ROUTING_PROMPT},
        {
            "role": "user",
            "content": f"""Contexto do sistema:
{json.dumps(system_context, ensure_ascii=False, indent=2, default=str)}

Input do usuário: "{user_input}"

Retorne o JSON de roteamento.""",
        },
    ]

    try:
        response = _client.chat.completions.create(
            model=OPENAI_MODEL,
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
    "scheduler":    scheduler.handle_handoff,
    "focus_guard":  focus_guard.handle_handoff,
    "notion_sync":  notion_sync.handle_handoff,
    "validator":    validator.handle_handoff,
    "retrospective": retrospective.handle_handoff,
    "calendar_sync": calendar_sync.handle_handoff,
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
            results.append({
                "agent": agent_name,
                "action": payload.get("action", "?"),
                "status": "error",
                "result": {"error": f"Agente '{agent_name}' não registrado."},
            })
            continue

        notifier.agent_event(
            f"Delegando para {agent_name}.{payload.get('action', '?')}...", AGENT_NAME
        )

        # Injeta contexto acumulado (resultados anteriores podem ser necessários)
        if accumulated_context:
            payload["_context"] = accumulated_context

        response = handler(payload)
        results.append({
            "agent": agent_name,
            "action": payload.get("action", "?"),
            "status": response.get("status", "unknown"),
            "result": response.get("result", {}),
        })

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
) -> str:
    """
    Usa o GPT-4o para sintetizar os resultados dos agentes em resposta natural.
    """
    results_str = json.dumps(handoff_results, ensure_ascii=False, indent=2, default=str)

    messages = [
        {"role": "system", "content": SYNTHESIS_PROMPT},
        {
            "role": "user",
            "content": f"""Input original do usuário: "{user_input}"
Intenção detectada: {intent}

Resultados dos agentes especialistas:
{results_str}

Forneça uma resposta útil e clara ao usuário.""",
        },
    ]

    try:
        response = _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        notifier.error(f"Erro na síntese: {e}", AGENT_NAME)
        # Fallback: lista resultados diretamente
        lines = [f"Resultado das ações executadas:"]
        for r in handoff_results:
            status_emoji = "✅" if r["status"] == "success" else "❌"
            lines.append(f"{status_emoji} {r['agent']}.{r['action']}: {r['status']}")
            if r["status"] == "error":
                lines.append(f"   Erro: {r['result'].get('error', '?')}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline principal do Orchestrator
# ---------------------------------------------------------------------------

def process(user_input: str, context: Optional[dict] = None) -> str:
    """
    Pipeline completo: input → roteamento → execução → síntese → resposta.

    Args:
        user_input: Comando/pergunta do usuário em linguagem natural.
        context:    Contexto extra opcional (ex: conversa anterior).

    Returns:
        Resposta final em texto para exibir ao usuário.
    """
    notifier.separator(f"ORCHESTRATOR")
    notifier.agent_event(f"Input recebido: \"{user_input[:80]}{'...' if len(user_input) > 80 else ''}\"", AGENT_NAME)

    # 1. Rotear intenção
    routing = route_intent(user_input, context)

    # 2. Verificar se precisa de mais informações
    if routing.get("requires_user_input"):
        question = routing.get("clarification_question", "Pode detalhar sua solicitação?")
        notifier.warning(f"Preciso de mais informações: {question}", AGENT_NAME)
        return f"❓ {question}"

    # 3. Executar handoffs
    handoffs = routing.get("handoffs", [])
    if not handoffs:
        notifier.info("Nenhum agente necessário — respondendo diretamente.", AGENT_NAME)
        # Resposta direta sem agentes especialistas
        return _direct_response(user_input)

    results = execute_handoffs(handoffs)

    # 4. Sintetizar resposta
    response = synthesize_response(
        user_input=user_input,
        intent=routing.get("intent", ""),
        handoff_results=results,
    )

    notifier.separator()
    return response


def _direct_response(user_input: str) -> str:
    """Resposta direta do Orchestrator para perguntas simples sem agentes."""
    try:
        response = _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Você é um assistente de gestão pessoal. Responda de forma concisa e útil em português.",
                },
                {"role": "user", "content": user_input},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
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
