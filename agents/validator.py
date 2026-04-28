# =============================================================================
# agents/validator.py — Agente de validação cruzada entre agentes
# =============================================================================
# Responsável por:
#   - Confirmar se uma tarefa foi REALMENTE concluída (não apenas marcada)
#   - Cruzar dados do banco local com o Notion
#   - Pedir confirmação ao usuário quando necessário
#   - Emitir veredicto final (validated / rejected / pending_confirmation)
#
# Este agente atua como "auditor" — é chamado antes de marcar definitivamente
# uma tarefa como concluída.

import json
from datetime import datetime

from agents import notion_sync as _notion_sync
from core import memory, notifier
from core.openai_utils import chat_completions

AGENT_NAME = "validator"

# Prompt do Validator para análise de conclusão via LLM
_VALIDATOR_PROMPT_FALLBACK = """Você é o Validator Agent de um sistema de gestão pessoal.
Sua função é determinar se uma tarefa foi genuinamente concluída.

Avalie os dados fornecidos e retorne um veredicto em JSON:
{
  "verdict": "validated" | "rejected" | "pending_confirmation",
  "confidence": 0.0 a 1.0,
  "reasons": ["motivo 1", "motivo 2"],
  "questions": ["pergunta para o usuário se precisar de confirmação"],
  "recommendation": "ação recomendada"
}

Critérios para "validated":
  - Tarefa marcada como concluída no banco local E no Notion
  - Horário real de conclusão registrado
  - Sessão de foco correspondente encerrada como 'completed'
  - Conteúdo da tarefa compatível com o esperado

Critérios para "rejected":
  - Marcada como concluída mas sem horário real
  - Dados inconsistentes entre local e Notion
  - Sessão de foco abandonada ou nunca iniciada

Critérios para "pending_confirmation":
  - Dados parcialmente consistentes — precisa de confirmação do usuário
  - Tarefa marcada manualmente sem sessão de foco associada
"""


def _get_validator_prompt() -> str:
    return _VALIDATOR_PROMPT_FALLBACK


# ---------------------------------------------------------------------------
# Coleta de evidências de conclusão
# ---------------------------------------------------------------------------


def gather_evidence(task_id: int) -> dict:
    """
    Coleta todas as evidências disponíveis sobre conclusão de uma tarefa.
    Cruza dados do banco local, sessões de foco e estado do Notion.
    """
    task = memory.get_task(task_id)
    if not task:
        return {"error": f"Tarefa {task_id} não encontrada no banco local."}

    focus_sessions = memory.get_focus_sessions_for_task(task_id)
    agenda_blocks = memory.get_agenda_blocks_for_task(task_id)

    # Informações do Notion (se disponível)
    notion_data = None
    if task.get("notion_page_id"):
        try:
            notion_tasks = _notion_sync.fetch_notion_tasks()
            notion_data = next(
                (
                    nt
                    for nt in notion_tasks
                    if nt["notion_page_id"] == task["notion_page_id"]
                ),
                None,
            )
        except Exception as e:
            notion_data = {"error": str(e)}

    return {
        "task": task,
        "focus_sessions": focus_sessions,
        "agenda_blocks": agenda_blocks,
        "notion_data": notion_data,
        "evidence_collected_at": datetime.now().isoformat(),
    }


def check_data_consistency(evidence: dict) -> dict:
    """
    Verifica consistência dos dados sem LLM.
    Retorna flags de consistência.
    """
    task = evidence.get("task", {})
    sessions = evidence.get("focus_sessions", [])
    blocks = evidence.get("agenda_blocks", [])
    notion = evidence.get("notion_data")

    flags = {
        "local_status_is_done": task.get("status") == "Concluído",
        "has_actual_time": bool(task.get("actual_time")),
        "has_completed_session": any(s.get("status") == "completed" for s in sessions),
        "has_any_session": len(sessions) > 0,
        "block_completed": any(b.get("completed") for b in blocks),
        "notion_synced": notion is not None and "error" not in str(notion),
        "notion_status_matches": (
            notion is not None and notion.get("status") == task.get("status")
            if notion and "error" not in str(notion)
            else None
        ),
    }

    # Score de consistência (0-100)
    score = 0
    if flags["local_status_is_done"]:
        score += 30
    if flags["has_actual_time"]:
        score += 20
    if flags["has_completed_session"]:
        score += 25
    if flags["block_completed"]:
        score += 15
    if flags["notion_status_matches"]:
        score += 10

    flags["consistency_score"] = score
    return flags


# ---------------------------------------------------------------------------
# Validação via LLM
# ---------------------------------------------------------------------------


def validate_with_llm(evidence: dict, flags: dict) -> dict:
    """
    Usa o GPT-4o-mini para analisar as evidências e emitir veredicto.
    """
    data = {
        "task": evidence.get("task"),
        "consistency_flags": flags,
        "sessions_summary": [
            {
                "status": s.get("status"),
                "planned_minutes": s.get("planned_minutes"),
                "actual_minutes": s.get("actual_minutes"),
            }
            for s in evidence.get("focus_sessions", [])
        ],
        "agenda_blocks_summary": [
            {"time_slot": b.get("time_slot"), "completed": b.get("completed")}
            for b in evidence.get("agenda_blocks", [])
        ],
        "notion_data": evidence.get("notion_data"),
    }

    prompt = f"""Evidências coletadas sobre a tarefa:
{json.dumps(data, ensure_ascii=False, indent=2, default=str)}

Emita seu veredicto em JSON puro (sem markdown).
"""

    try:
        response = chat_completions(
            messages=[
                {"role": "system", "content": _get_validator_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # Baixa temperatura: queremos análise determinística
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        notifier.error(f"Erro no LLM do Validator: {e}", AGENT_NAME)
        # Fallback baseado nos flags
        score = flags.get("consistency_score", 0)
        if score >= 70:
            return {
                "verdict": "validated",
                "confidence": score / 100,
                "reasons": ["Dados consistentes entre local, sessões e agenda."],
                "questions": [],
                "recommendation": "Tarefa pode ser confirmada como concluída.",
            }
        elif score >= 40:
            return {
                "verdict": "pending_confirmation",
                "confidence": score / 100,
                "reasons": ["Dados parcialmente consistentes."],
                "questions": ["Você confirma que a tarefa foi realmente concluída?"],
                "recommendation": "Solicite confirmação ao usuário.",
            }
        else:
            return {
                "verdict": "rejected",
                "confidence": (100 - score) / 100,
                "reasons": [
                    "Dados insuficientes ou inconsistentes para validar conclusão."
                ],
                "questions": [],
                "recommendation": "Verifique se a tarefa foi realmente concluída antes de marcá-la.",
            }


# ---------------------------------------------------------------------------
# Ação após validação
# ---------------------------------------------------------------------------


def apply_verdict(task_id: int, verdict: dict) -> dict:
    """
    Aplica o veredicto do Validator:
    - 'validated':              Confirma status no banco e Notion
    - 'rejected':               Reverte status para 'Em progresso'
    - 'pending_confirmation':   Aguarda input do usuário
    """
    v = verdict.get("verdict", "pending_confirmation")
    task = memory.get_task(task_id)

    if v == "validated":
        # Confirma como concluído com timestamp
        actual_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        memory.update_task_status(task_id, "Concluído", actual_time)

        # Atualiza Notion se vinculado
        if task and task.get("notion_page_id"):
            try:
                _notion_sync.update_notion_task_status(
                    task["notion_page_id"], "Concluído", actual_time
                )
            except Exception as e:
                notifier.warning(f"Não foi possível atualizar Notion: {e}", AGENT_NAME)

        notifier.success(
            f"✅ Tarefa '{task.get('title', task_id)}' VALIDADA como concluída!",
            AGENT_NAME,
        )

    elif v == "rejected":
        memory.update_task_status(task_id, "Em progresso")
        notifier.warning(
            f"❌ Tarefa '{task.get('title', task_id)}' REJEITADA — revertida para 'Em progresso'.",
            AGENT_NAME,
        )

    else:  # pending_confirmation
        questions = verdict.get("questions", [])
        notifier.warning(
            f"⏳ Tarefa '{task.get('title', task_id)}' aguarda CONFIRMAÇÃO.", AGENT_NAME
        )
        if questions:
            notifier.info("Perguntas para confirmação:", AGENT_NAME)
            for q in questions:
                notifier.info(f"  → {q}", AGENT_NAME)

    return {"applied": True, "verdict": v, "task_id": task_id}


def validate_task(task_id: int, force_confirm: bool = False) -> dict:
    """
    Pipeline completo de validação de uma tarefa.

    Args:
        task_id:       ID local da tarefa
        force_confirm: Se True, aceita pending_confirmation como validated

    Returns:
        Dict com evidence, flags, verdict, e resultado da aplicação.
    """
    notifier.agent_event(f"Iniciando validação da tarefa {task_id}...", AGENT_NAME)

    evidence = gather_evidence(task_id)
    if "error" in evidence:
        return {"status": "error", "message": evidence["error"]}

    flags = check_data_consistency(evidence)
    notifier.info(
        f"Score de consistência: {flags.get('consistency_score', 0)}/100", AGENT_NAME
    )

    verdict = validate_with_llm(evidence, flags)
    notifier.info(
        f"Veredicto LLM: {verdict.get('verdict')} "
        f"(confiança: {verdict.get('confidence', 0):.0%})",
        AGENT_NAME,
    )

    # Se force_confirm e pending → trata como validated
    if force_confirm and verdict.get("verdict") == "pending_confirmation":
        verdict["verdict"] = "validated"
        verdict["reasons"].append("Confirmação forçada pelo usuário.")

    applied = apply_verdict(task_id, verdict)

    return {
        "task_id": task_id,
        "evidence_summary": {
            "local_status": evidence["task"].get("status"),
            "sessions_count": len(evidence.get("focus_sessions", [])),
            "blocks_count": len(evidence.get("agenda_blocks", [])),
        },
        "flags": flags,
        "verdict": verdict,
        "applied": applied,
    }


def validate_all_completed() -> list[dict]:
    """Valida todas as tarefas marcadas como 'Concluído' no banco local."""
    completed = memory.get_tasks_by_status("Concluído")
    results = []
    for task in completed:
        result = validate_task(task["id"])
        results.append(result)
    notifier.success(f"{len(results)} tarefa(s) validada(s).", AGENT_NAME)
    return results


# ---------------------------------------------------------------------------
# Handoff entry point — chamado pelo Orchestrator
# ---------------------------------------------------------------------------


def handle_handoff(payload: dict) -> dict:
    """
    Ponto de entrada para handoffs do Orchestrator.
    """
    action = payload.get("action", "")
    notifier.agent_event(f"Recebendo handoff: action='{action}'", AGENT_NAME)

    handoff_id = memory.log_handoff("orchestrator", AGENT_NAME, action, payload)

    try:
        result: dict = {}

        if action == "validate_task":
            validation = validate_task(
                task_id=payload["task_id"],
                force_confirm=payload.get("force_confirm", False),
            )
            result = validation

        elif action == "validate_all":
            validations = validate_all_completed()
            result = {
                "validations": validations,
                "total": len(validations),
                "validated": sum(
                    1
                    for v in validations
                    if v.get("verdict", {}).get("verdict") == "validated"
                ),
            }

        elif action == "get_evidence":
            evidence = gather_evidence(payload["task_id"])
            flags = check_data_consistency(evidence)
            result = {"evidence": evidence, "flags": flags}

        else:
            raise ValueError(f"Ação desconhecida: '{action}'")

        memory.update_handoff_result(handoff_id, result, "success")
        return {"status": "success", "result": result}

    except Exception as exc:
        error_msg = str(exc)
        notifier.error(f"Erro no handoff '{action}': {error_msg}", AGENT_NAME)
        memory.update_handoff_result(handoff_id, {"error": error_msg}, "error")
        return {"status": "error", "result": {"error": error_msg}}
