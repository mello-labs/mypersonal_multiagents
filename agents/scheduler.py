# =============================================================================
# agents/scheduler.py — Agente de gerenciamento de horários e blocos de tempo
# =============================================================================
# Responsável por:
#   - Criar e gerenciar blocos de agenda no dia
#   - Priorizar tarefas por urgência/horário
#   - Sugerir reorganizações de agenda via LLM
#   - Sincronizar com o Notion Sync Agent

import json
import os
from datetime import date, datetime, time, timedelta
from typing import Optional


from core import memory, notifier
from core.openai_utils import chat_completions

AGENT_NAME = "scheduler"

# Prompt de sistema para o LLM do Scheduler
_SYSTEM_PROMPT_FALLBACK = """Você é o Scheduler Agent de um sistema de gestão pessoal.
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


def _get_system_prompt() -> str:
    return _SYSTEM_PROMPT_FALLBACK


# ---------------------------------------------------------------------------
# Lógica de agendamento local (sem LLM)
# ---------------------------------------------------------------------------


def get_today_schedule() -> list[dict]:
    """Retorna o cronograma de hoje do banco local, ordenado por horário."""
    return memory.get_today_agenda()


def _parse_slot_range(
    block_date: str, time_slot: str
) -> Optional[tuple[datetime, datetime]]:
    if "-" not in time_slot:
        return None
    try:
        start_str, end_str = [part.strip() for part in time_slot.split("-", 1)]
        start_dt = datetime.strptime(f"{block_date} {start_str}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{block_date} {end_str}", "%Y-%m-%d %H:%M")
        if end_dt <= start_dt:
            return None
        return start_dt, end_dt
    except ValueError:
        return None


def _format_slot(start_dt: datetime, duration_minutes: int) -> str:
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    return f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"


def _round_up_to_quarter(dt: datetime) -> datetime:
    base = dt.replace(second=0, microsecond=0)
    remainder = base.minute % 15
    if remainder == 0 and base.second == 0 and base.microsecond == 0:
        return base
    return base + timedelta(minutes=(15 - remainder))


def _find_same_task_future_block(
    blocks: list[dict],
    task_id: Optional[int],
    task_title: str,
    start_after: datetime,
    exclude_block_id: int,
) -> Optional[dict]:
    normalized_title = task_title.strip().lower()
    for block in blocks:
        if (
            block.get("id") == exclude_block_id
            or block.get("completed")
            or block.get("rescheduled")
        ):
            continue
        block_range = _parse_slot_range(
            block.get("block_date", date.today().isoformat()),
            block.get("time_slot", ""),
        )
        if not block_range:
            continue
        block_start, _ = block_range
        if block_start < start_after:
            continue
        same_task_id = task_id is not None and str(block.get("task_id")) == str(task_id)
        same_title = (block.get("task_title") or "").strip().lower() == normalized_title
        if same_task_id or same_title:
            return block
    return None


def _find_available_start(
    block_date: str,
    duration_minutes: int,
    blocks: list[dict],
    start_after: datetime,
    exclude_block_ids: set[int],
) -> datetime:
    day_start = datetime.combine(
        datetime.strptime(block_date, "%Y-%m-%d").date(), time(9, 0)
    )
    candidate = max(_round_up_to_quarter(start_after), day_start)

    intervals = []
    for block in blocks:
        if block.get("id") in exclude_block_ids:
            continue
        block_range = _parse_slot_range(
            block.get("block_date", block_date), block.get("time_slot", "")
        )
        if not block_range:
            continue
        start_dt, end_dt = block_range
        intervals.append((start_dt, end_dt))

    intervals.sort(key=lambda item: item[0])

    for start_dt, end_dt in intervals:
        if end_dt <= candidate:
            continue
        if candidate + timedelta(minutes=duration_minutes) <= start_dt:
            return candidate
        if candidate < end_dt:
            candidate = _round_up_to_quarter(end_dt)

    return candidate


def find_next_available_slot(
    duration_minutes: int,
    start_after: Optional[datetime] = None,
    max_days_ahead: int = 3,
) -> tuple[str, str]:
    reference = start_after or datetime.now()

    for offset in range(max_days_ahead + 1):
        target_date = (reference.date() + timedelta(days=offset)).isoformat()
        day_start = (
            reference
            if offset == 0
            else datetime.combine(reference.date() + timedelta(days=offset), time(9, 0))
        )
        blocks = memory.get_agenda_for_date(target_date)
        start_dt = _find_available_start(
            target_date,
            duration_minutes,
            blocks,
            day_start,
            exclude_block_ids=set(),
        )
        if start_dt.date().isoformat() == target_date:
            return target_date, _format_slot(start_dt, duration_minutes)

    fallback_date = reference.date().isoformat()
    return fallback_date, _format_slot(
        _round_up_to_quarter(reference), duration_minutes
    )


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


def auto_reschedule_block(
    block_id: int,
    reason: str = "Bloco atrasado detectado pelo Focus Guard.",
    reference_time: Optional[datetime] = None,
    max_reschedules: int = 3,
) -> dict:
    block = memory.get_block(block_id)
    if not block:
        return {"status": "missing", "reason": "Bloco não encontrado."}
    if block.get("completed"):
        return {"status": "skipped", "reason": "Bloco já concluído."}
    if block.get("rescheduled"):
        return {"status": "skipped", "reason": "Bloco já foi reagendado."}
    if int(block.get("reschedule_count") or 0) >= max_reschedules:
        return {"status": "skipped", "reason": "Limite de reagendamentos atingido."}

    block_date = block.get("block_date") or date.today().isoformat()
    block_range = _parse_slot_range(block_date, block.get("time_slot", ""))
    if not block_range:
        return {"status": "skipped", "reason": "Time slot inválido."}

    start_dt, end_dt = block_range
    _min_block = 25
    duration_minutes = max(int((end_dt - start_dt).total_seconds() / 60), _min_block)
    now_dt = reference_time or datetime.now()
    same_day_blocks = memory.get_agenda_for_date(block_date)

    existing = _find_same_task_future_block(
        same_day_blocks,
        block.get("task_id"),
        block.get("task_title", ""),
        start_after=now_dt,
        exclude_block_id=block_id,
    )
    if existing:
        memory.update_block(
            block_id,
            rescheduled=True,
            rescheduled_to_block_id=existing["id"],
        )
        return {
            "status": "linked",
            "original_block_id": block_id,
            "rescheduled_to_block_id": existing["id"],
            "new_time_slot": existing.get("time_slot"),
            "new_block_date": existing.get("block_date"),
            "reason": "Já existia um bloco futuro para esta tarefa.",
        }

    target_date, new_time_slot = find_next_available_slot(
        duration_minutes,
        start_after=max(now_dt, end_dt),
    )
    new_block_id = memory.create_agenda_block(
        block_date=target_date,
        time_slot=new_time_slot,
        task_title=block.get("task_title", "Sem título"),
        task_id=block.get("task_id"),
        notion_page_id=block.get("notion_page_id"),
        source_block_id=block.get("source_block_id") or block_id,
        created_by="auto_reschedule",
        reschedule_count=int(block.get("reschedule_count") or 0) + 1,
    )
    memory.update_block(
        block_id,
        rescheduled=True,
        rescheduled_to_block_id=new_block_id,
    )

    notifier.warning(
        f"Bloco {block_id} reagendado automaticamente para {target_date} {new_time_slot}.",
        AGENT_NAME,
    )
    return {
        "status": "created",
        "original_block_id": block_id,
        "rescheduled_to_block_id": new_block_id,
        "old_time_slot": block.get("time_slot"),
        "new_time_slot": new_time_slot,
        "new_block_date": target_date,
        "duration_minutes": duration_minutes,
        "reason": reason,
    }


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
            conflicts.append(f"Conflito em {start_time}: {', '.join(tasks)}")

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
        response = chat_completions(
            messages=[
                {"role": "system", "content": _get_system_prompt()},
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
            suggestion = suggest_agenda_with_llm(context=payload.get("context", ""))
            if payload.get("apply", False):
                ids = apply_llm_suggestion(suggestion)
                result = {"suggestion": suggestion, "applied_blocks": ids}
            else:
                result = {"suggestion": suggestion}

        elif action == "get_prioritized_tasks":
            tasks = get_prioritized_tasks()
            result = {"tasks": tasks, "count": len(tasks)}

        elif action == "auto_reschedule_block":
            result = auto_reschedule_block(
                block_id=payload["block_id"],
                reason=payload.get(
                    "reason", "Bloco atrasado detectado automaticamente."
                ),
            )

        else:
            raise ValueError(f"Ação desconhecida: '{action}'")

        memory.update_handoff_result(handoff_id, result, "success")
        return {"status": "success", "result": result}

    except Exception as exc:
        error_msg = str(exc)
        notifier.error(f"Erro no handoff '{action}': {error_msg}", AGENT_NAME)
        memory.update_handoff_result(handoff_id, {"error": error_msg}, "error")
        return {"status": "error", "result": {"error": error_msg}}
