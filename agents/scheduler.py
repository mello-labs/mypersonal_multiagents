# =============================================================================
# agents/scheduler.py — Agente de gerenciamento de horários e blocos de tempo
# =============================================================================
# Responsável por:
#   - Criar e gerenciar blocos de agenda no dia
#   - Priorizar tarefas por urgência/horário
#   - Sugerir reorganizações de agenda via LLM
#   - Sincronizar com o Notion Sync Agent

import json
import sys
import os
from datetime import datetime, date, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL
from core import memory, notifier

AGENT_NAME = "scheduler"
_client = OpenAI(api_key=OPENAI_API_KEY)

# Prompt de sistema para o LLM do Scheduler
SYSTEM_PROMPT = """Você é o Scheduler Agent de um sistema de gestão pessoal.
Sua função é gerenciar blocos de tempo e priorizar tarefas.

Ao receber uma lista de tarefas, você deve:
1. Ordenar por prioridade (Alta > Média > Baixa) e urgência de horário
2. Sugerir blocos de tempo realistas (mínimo 25 minutos por tarefa)
3. Incluir pausas entre blocos longos (≥90 min → sugerir pausa de 15 min)
4. Alertar sobre conflitos de horário ou agenda sobrecarregada
5. Respeitar os horários já agendados

Responda sempre em JSON estruturado com o campo "schedule" (lista de blocos)
e "warnings" (lista de avisos). Exemplo de bloco:
{
  "time_slot": "09:00-10:00",
  "task_title": "Revisar PRs",
  "priority": "Alta",
  "notes": "Começar pelo PR #42"
}
"""


# ---------------------------------------------------------------------------
# Lógica de agendamento local (sem LLM)
# ---------------------------------------------------------------------------

def get_today_schedule() -> list[dict]:
    """Retorna o cronograma de hoje do banco local, ordenado por horário."""
    return memory.get_today_agenda()


def add_schedule_block(
    time_slot: str,
    task_title: str,
    task_id: Optional[int] = None,
    block_date: Optional[str] = None,
) -> int:
    """
    Adiciona um bloco de agenda no banco local.

    Args:
        time_slot:   Ex: "09:00-10:00"
        task_title:  Nome da tarefa
        task_id:     ID local da tarefa (opcional)
        block_date:  Data no formato YYYY-MM-DD (padrão: hoje)

    Returns:
        ID do bloco criado.
    """
    target_date = block_date or date.today().isoformat()
    block_id = memory.create_agenda_block(
        block_date=target_date,
        time_slot=time_slot,
        task_title=task_title,
        task_id=task_id,
    )
    notifier.success(
        f"Bloco adicionado: {target_date} {time_slot} → '{task_title}'", AGENT_NAME
    )
    return block_id


def complete_block(block_id: int) -> None:
    """Marca um bloco de agenda como concluído."""
    memory.mark_block_completed(block_id, True)
    notifier.success(f"Bloco {block_id} marcado como concluído.", AGENT_NAME)


def get_prioritized_tasks() -> list[dict]:
    """
    Retorna tarefas pendentes/em progresso ordenadas por:
    1. Prioridade (Alta > Média > Baixa)
    2. Horário agendado (mais cedo primeiro)
    """
    priority_order = {"Alta": 0, "Média": 1, "Baixa": 2}

    pending = memory.get_tasks_by_status("A fazer")
    in_progress = memory.get_tasks_by_status("Em progresso")
    all_tasks = in_progress + pending

    def sort_key(t: dict):
        p = priority_order.get(t.get("priority", "Média"), 1)
        sched = t.get("scheduled_time") or "99:99"
        return (p, sched)

    return sorted(all_tasks, key=sort_key)


def detect_schedule_conflicts() -> list[str]:
    """
    Detecta conflitos básicos na agenda de hoje:
    - Blocos com mesmo horário de início
    - Tarefas sem bloco associado (órfãs)
    """
    blocks = get_today_schedule()
    conflicts = []

    # Checar duplicidade de time_slot
    seen_slots: dict[str, list] = {}
    for b in blocks:
        slot = b.get("time_slot", "")
        start = slot.split("-")[0].strip() if "-" in slot else slot
        seen_slots.setdefault(start, []).append(b.get("task_title", "?"))

    for start_time, tasks in seen_slots.items():
        if len(tasks) > 1:
            conflicts.append(
                f"Conflito em {start_time}: {', '.join(tasks)}"
            )

    return conflicts


def calculate_schedule_load(blocks: Optional[list] = None) -> dict:
    """
    Calcula a carga total da agenda:
    - Total de blocos
    - Minutos agendados
    - Percentual de conclusão
    """
    if blocks is None:
        blocks = get_today_schedule()

    total = len(blocks)
    done = sum(1 for b in blocks if b.get("completed"))

    # Calcula minutos agendados somando duração dos blocos
    total_minutes = 0
    for b in blocks:
        slot = b.get("time_slot", "")
        if "-" in slot:
            try:
                parts = slot.split("-")
                start = datetime.strptime(parts[0].strip(), "%H:%M")
                end = datetime.strptime(parts[1].strip(), "%H:%M")
                total_minutes += int((end - start).total_seconds() / 60)
            except ValueError:
                pass

    pct = round((done / total) * 100) if total > 0 else 0

    return {
        "total_blocks": total,
        "completed_blocks": done,
        "pending_blocks": total - done,
        "total_minutes": total_minutes,
        "completion_percent": pct,
    }


# ---------------------------------------------------------------------------
# Sugestão de agenda via LLM
# ---------------------------------------------------------------------------

def suggest_agenda_with_llm(
    tasks: Optional[list[dict]] = None,
    context: str = "",
) -> dict:
    """
    Usa o GPT-4o para sugerir uma agenda otimizada para o dia.

    Args:
        tasks:    Lista de tarefas (pega as pendentes se None)
        context:  Contexto adicional (ex: "só tenho 3h disponíveis hoje")

    Returns:
        Dict com "schedule" (lista de blocos sugeridos) e "warnings".
    """
    if tasks is None:
        tasks = get_prioritized_tasks()

    if not tasks:
        return {"schedule": [], "warnings": ["Nenhuma tarefa pendente encontrada."]}

    # Formata tarefas para o prompt
    tasks_str = json.dumps(
        [
            {
                "title": t.get("title"),
                "priority": t.get("priority"),
                "scheduled_time": t.get("scheduled_time", ""),
                "status": t.get("status"),
            }
            for t in tasks
        ],
        ensure_ascii=False,
        indent=2,
    )

    current_time = datetime.now().strftime("%H:%M")
    user_message = f"""
Hora atual: {current_time}
Data: {date.today().isoformat()}

Tarefas a agendar:
{tasks_str}

{f"Contexto adicional: {context}" if context else ""}

Por favor, crie uma agenda otimizada para hoje. Retorne JSON puro (sem markdown).
"""

    try:
        response = _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        notifier.success("Agenda sugerida pelo LLM gerada com sucesso.", AGENT_NAME)
        return result
    except Exception as e:
        notifier.error(f"Erro ao gerar sugestão de agenda: {e}", AGENT_NAME)
        return {"schedule": [], "warnings": [str(e)]}


def apply_llm_suggestion(suggestion: dict, auto_sync_notion: bool = False) -> list[int]:
    """
    Aplica a sugestão de agenda do LLM ao banco local.
    Retorna lista de IDs de blocos criados.
    """
    created_ids = []
    schedule = suggestion.get("schedule", [])

    for block in schedule:
        time_slot = block.get("time_slot", "")
        task_title = block.get("task_title", "")
        if not time_slot or not task_title:
            continue

        # Tenta encontrar tarefa local correspondente pelo título
        all_tasks = memory.list_all_tasks()
        matched_task = next(
            (t for t in all_tasks if t["title"].lower() == task_title.lower()), None
        )
        task_id = matched_task["id"] if matched_task else None

        block_id = add_schedule_block(
            time_slot=time_slot,
            task_title=task_title,
            task_id=task_id,
        )
        created_ids.append(block_id)

    warnings = suggestion.get("warnings", [])
    for w in warnings:
        notifier.warning(w, AGENT_NAME)

    notifier.success(f"{len(created_ids)} bloco(s) de agenda criados.", AGENT_NAME)
    return created_ids


# ---------------------------------------------------------------------------
# Handoff entry point — chamado pelo Orchestrator
# ---------------------------------------------------------------------------

def handle_handoff(payload: dict) -> dict:
    """
    Ponto de entrada para handoffs do Orchestrator.
    Retorna dict com 'status' e 'result'.
    """
    action = payload.get("action", "")
    notifier.agent_event(f"Recebendo handoff: action='{action}'", AGENT_NAME)

    handoff_id = memory.log_handoff("orchestrator", AGENT_NAME, action, payload)

    try:
        result: dict = {}

        if action == "get_today_schedule":
            blocks = get_today_schedule()
            load = calculate_schedule_load(blocks)
            conflicts = detect_schedule_conflicts()
            result = {
                "blocks": blocks,
                "load": load,
                "conflicts": conflicts,
            }

        elif action == "add_block":
            block_id = add_schedule_block(
                time_slot=payload["time_slot"],
                task_title=payload["task_title"],
                task_id=payload.get("task_id"),
                block_date=payload.get("block_date"),
            )
            result = {"block_id": block_id, "message": "Bloco adicionado."}

        elif action == "complete_block":
            complete_block(payload["block_id"])
            result = {"message": "Bloco marcado como concluído."}

        elif action == "suggest_agenda":
            suggestion = suggest_agenda_with_llm(
                context=payload.get("context", "")
            )
            if payload.get("apply", False):
                ids = apply_llm_suggestion(suggestion)
                result = {"suggestion": suggestion, "applied_blocks": ids}
            else:
                result = {"suggestion": suggestion}

        elif action == "get_prioritized_tasks":
            tasks = get_prioritized_tasks()
            result = {"tasks": tasks, "count": len(tasks)}

        else:
            raise ValueError(f"Ação desconhecida: '{action}'")

        memory.update_handoff_result(handoff_id, result, "success")
        return {"status": "success", "result": result}

    except Exception as exc:
        error_msg = str(exc)
        notifier.error(f"Erro no handoff '{action}': {error_msg}", AGENT_NAME)
        memory.update_handoff_result(handoff_id, {"error": error_msg}, "error")
        return {"status": "error", "result": {"error": error_msg}}
