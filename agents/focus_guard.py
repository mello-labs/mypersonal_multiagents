# =============================================================================
# agents/focus_guard.py — Agente guardião do foco
# =============================================================================
# Roda em background thread e periodicamente:
#   1. Verifica se há uma sessão de foco ativa
#   2. Compara o que foi planejado vs. o que foi feito
#   3. Emite alertas/cobranças no terminal
#   4. Registra desvios no banco de dados
#
# O loop principal usa a lib `schedule` para disparos periódicos.
# A thread roda como daemon e é parada por um Event.

import json
import os
import sys
import threading
import time
from datetime import date, datetime
from typing import Optional

import schedule

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import notion_sync as _notion_sync
from agents import scheduler as _scheduler
from config import (
    FOCUS_CHECK_INTERVAL_MINUTES,
    NOTION_SYNC_INTERVAL_MINUTES,
)
from core import memory, notifier, sanity_client
from core.openai_utils import chat_completions

AGENT_NAME = "focus_guard"

# Níveis de escalada por tempo de sessão
ESCALATION_LEVELS = [
    {
        "minutes": 30,
        "channel": "mac",
        "sound": False,
        "msg": "30 min em {task}. Planejado: {planned}min.",
    },
    {
        "minutes": 60,
        "channel": "mac",
        "sound": True,
        "msg": "1 hora em {task}. Hora de checar.",
    },
    {
        "minutes": 120,
        "channel": "mac+alexa",
        "sound": True,
        "msg": "2 horas em {task}. Para agora.",
    },
    {
        "minutes": 240,
        "channel": "mac+alexa",
        "sound": True,
        "msg": "4 horas. Sai do computador por 10 minutos.",
    },
]

# Estado interno do Focus Guard
_state_key = "focus_guard_state"
_stop_event = threading.Event()
_guard_thread: Optional[threading.Thread] = None


# Prompt para análise de desvio via LLM
_DEVIATION_PROMPT_FALLBACK = """Você é o Focus Guard, um agente que monitora o progresso de tarefas pessoais.
Analise os dados fornecidos e determine:
1. Se o usuário está dentro do plano (on-track) ou desviou
2. Se houve desvio, qual a gravidade (leve/moderado/grave)
3. Uma mensagem de cobrança/encorajamento adequada (seja direto, mas empático)

Retorne JSON com:
{
  "on_track": true/false,
  "deviation_level": "none" | "light" | "moderate" | "severe",
  "message": "sua mensagem aqui",
  "recommendation": "ação recomendada"
}
"""


def _get_deviation_prompt() -> str:
    return sanity_client.get_prompt(
        "focus_guard", "deviation", _DEVIATION_PROMPT_FALLBACK
    )


def _get_runtime_environment() -> str:
    return "local" if sys.platform == "darwin" else "server"


def _get_intervention_levels() -> list[dict]:
    scripts = sanity_client.get_intervention_scripts(AGENT_NAME)
    current_env = _get_runtime_environment()
    levels = []
    for script in scripts:
        scope = script.get("environment_scope", "all")
        if scope not in {"all", current_env}:
            continue
        levels.append(
            {
                "minutes": script.get("trigger_minutes"),
                "channel": script.get("channel", "log_only"),
                "sound": script.get("sound", False),
                "msg": script.get("message", ""),
                "title": script.get("title", "NEO Focus Guard"),
            }
        )

    levels = [level for level in levels if isinstance(level.get("minutes"), int)]
    return levels or ESCALATION_LEVELS


# ---------------------------------------------------------------------------
# Análise de progresso
# ---------------------------------------------------------------------------


def analyze_progress() -> dict:
    """
    Compara agenda planejada vs. realidade atual.
    Retorna análise estruturada do progresso.
    """
    today_blocks = memory.get_today_agenda()
    active_session = memory.get_active_focus_session()
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")

    # Blocos que já deveriam ter passado (time_slot de início ≤ agora)
    overdue_blocks = []
    current_block = None
    upcoming_blocks = []

    for block in today_blocks:
        slot = block.get("time_slot", "")
        if "-" in slot:
            # Bloco com horário definido — lógica temporal exata
            try:
                start_str = slot.split("-")[0].strip()
                end_str = slot.split("-")[1].strip()
                start_t = datetime.strptime(
                    f"{date.today()} {start_str}", "%Y-%m-%d %H:%M"
                )
                end_t = datetime.strptime(f"{date.today()} {end_str}", "%Y-%m-%d %H:%M")

                if end_t < now and not block.get("completed"):
                    overdue_blocks.append(block)
                elif start_t <= now <= end_t:
                    current_block = block
                elif start_t > now:
                    upcoming_blocks.append(block)
            except ValueError:
                pass
        else:
            # Bloco date-only (sem horário) — pendente enquanto não concluído
            if not block.get("completed"):
                upcoming_blocks.append(block)

    load = {
        "total": len(today_blocks),
        "completed": sum(1 for b in today_blocks if b.get("completed")),
        "overdue": len(overdue_blocks),
        "current": current_block,
        "upcoming": len(upcoming_blocks),
    }

    # Calcula on-track básico (sem LLM)
    on_track = len(overdue_blocks) == 0

    return {
        "timestamp": now.isoformat(),
        "current_time": current_time_str,
        "on_track": on_track,
        "load": load,
        "overdue_blocks": overdue_blocks,
        "current_block": current_block,
        "upcoming_blocks_count": len(upcoming_blocks),
        "active_focus_session": active_session,
    }


def analyze_with_llm(progress: dict) -> dict:
    """
    Usa o GPT-4o-mini para gerar análise e mensagem personalizada de cobrança.
    Retorna dict com on_track, deviation_level, message, recommendation.
    """
    progress_str = json.dumps(progress, ensure_ascii=False, indent=2, default=str)

    try:
        response = chat_completions(
            messages=[
                {"role": "system", "content": _get_deviation_prompt()},
                {"role": "user", "content": f"Dados de progresso:\n{progress_str}"},
            ],
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        notifier.error(f"Erro na análise LLM: {e}", AGENT_NAME)
        # Fallback: análise básica sem LLM
        if progress.get("on_track"):
            return {
                "on_track": True,
                "deviation_level": "none",
                "message": "Você está no caminho certo! Continue focado.",
                "recommendation": "Mantenha o ritmo atual.",
            }
        else:
            overdue = progress.get("load", {}).get("overdue", 0)
            return {
                "on_track": False,
                "deviation_level": "moderate" if overdue <= 2 else "severe",
                "message": f"Atenção! {overdue} bloco(s) da agenda não foram concluídos. Hora de volcar o foco!",
                "recommendation": "Revise a agenda e retome a próxima tarefa pendente.",
            }


# ---------------------------------------------------------------------------
# Escalada por tempo de sessão
# ---------------------------------------------------------------------------


def _check_escalation(
    session_minutes: int, task_title: str, planned_minutes: int
) -> None:
    """Dispara notificação no canal certo baseado no tempo de sessão."""
    today = datetime.now().date()
    for level in _get_intervention_levels():
        state_key = f"escalation:{today}:{task_title}:{level['minutes']}"
        if memory.get_state(state_key):
            continue
        if session_minutes >= level["minutes"]:
            msg = level["msg"].format(task=task_title, planned=planned_minutes)
            if "mac" in level["channel"]:
                notifier.mac_push(
                    level.get("title", "NEO Focus Guard"), msg, sound=level["sound"]
                )
            if "alexa" in level["channel"]:
                notifier.alexa_announce(msg)
            memory.set_state(state_key, "sent")
            break  # só um nível por check


# ---------------------------------------------------------------------------
# Loop de verificação periódica
# ---------------------------------------------------------------------------


def _auto_reschedule_overdue_blocks(progress: dict) -> list[dict]:
    actions = []
    overdue_blocks = progress.get("overdue_blocks", [])
    if not overdue_blocks:
        return actions

    for block in overdue_blocks:
        result = _scheduler.auto_reschedule_block(
            block_id=block["id"],
            reason="Bloco vencido detectado no check periódico do Focus Guard.",
        )
        status = result.get("status")
        if status not in {"created", "linked"}:
            continue

        details = f"{block.get('time_slot')} → {result.get('new_block_date')} {result.get('new_time_slot')}"
        if status == "linked":
            details = (
                f"{block.get('time_slot')} → bloco existente #{result.get('rescheduled_to_block_id')} "
                f"em {result.get('new_block_date')} {result.get('new_time_slot')}"
            )

        memory.create_audit_event(
            event_type="auto_reschedule",
            title=f"Bloco reagendado: {block.get('task_title', 'Sem título')}",
            details=details,
            level="warning",
            agent=AGENT_NAME,
            payload=result,
            related_id=str(block["id"]),
        )
        actions.append(result)

    return actions


def _run_focus_check(
    progress: Optional[dict] = None,
    analysis: Optional[dict] = None,
) -> dict:
    """Executado pelo scheduler a cada intervalo configurado.

    Aceita `progress` e `analysis` pré-computados para evitar chamadas LLM
    duplicadas quando invocado a partir de `force_check`.
    Retorna dict com progress e analysis para uso pelo chamador.
    """
    notifier.focus_alert("═══ CHECK-IN DO FOCUS GUARD ═══", AGENT_NAME)

    if progress is None:
        progress = analyze_progress()
    if analysis is None:
        analysis = analyze_with_llm(progress)
    rescheduled_actions = _auto_reschedule_overdue_blocks(progress)

    # Salva estado atual
    memory.set_state(
        _state_key,
        {
            "last_check": datetime.now().isoformat(),
            "on_track": analysis.get("on_track", True),
            "deviation_level": analysis.get("deviation_level", "none"),
        },
    )
    memory.create_audit_event(
        event_type="focus_check",
        title="Check periódico do Focus Guard",
        details=(
            f"on_track={analysis.get('on_track', True)} | "
            f"desvio={analysis.get('deviation_level', 'none')} | "
            f"atrasados={progress.get('load', {}).get('overdue', 0)} | "
            f"reagendados={len(rescheduled_actions)}"
        ),
        level="warning" if not analysis.get("on_track", True) else "info",
        agent=AGENT_NAME,
        payload={
            "progress": progress,
            "analysis": analysis,
            "rescheduled_actions": rescheduled_actions,
        },
    )

    # Exibe resumo
    load = progress.get("load", {})
    notifier.info(
        f"Agenda hoje: {load.get('completed', 0)}/{load.get('total', 0)} blocos concluídos "
        f"| {load.get('overdue', 0)} atrasado(s)",
        AGENT_NAME,
    )

    # Sessão de foco ativa
    active = progress.get("active_focus_session")
    if active:
        started = active.get("started_at", "")
        notifier.info(
            f"Sessão ativa: '{active.get('task_title')}' desde {started[:16]}",
            AGENT_NAME,
        )
        try:
            started_dt = datetime.fromisoformat(started)
            session_minutes = int((datetime.now() - started_dt).total_seconds() / 60)
            _check_escalation(
                session_minutes=session_minutes,
                task_title=active.get("task_title", "?"),
                planned_minutes=active.get("planned_minutes", 25),
            )
        except Exception:
            pass

    # Mensagem de análise
    deviation = analysis.get("deviation_level", "none")
    message = analysis.get("message", "")
    recommendation = analysis.get("recommendation", "")

    if deviation == "none":
        notifier.success(f"✅ {message}", AGENT_NAME)
    elif deviation == "light":
        notifier.warning(f"⚡ {message}", AGENT_NAME)
    elif deviation == "moderate":
        notifier.warning(f"🚨 {message}", AGENT_NAME)
        if recommendation:
            notifier.warning(f"   → {recommendation}", AGENT_NAME)
    else:  # severe
        notifier.error(f"🔥 {message}", AGENT_NAME)
        if recommendation:
            notifier.error(f"   → {recommendation}", AGENT_NAME)

    # Registra alerta no banco se houver desvio
    if not analysis.get("on_track", True):
        alert_type = f"deviation_{deviation}"
        full_msg = message
        if recommendation:
            full_msg += f" | Recomendação: {recommendation}"
        alert_id = memory.create_alert(alert_type, full_msg)
        memory.create_audit_event(
            event_type="alert_created",
            title=f"Alerta gerado: {alert_type}",
            details=full_msg,
            level="warning" if deviation != "severe" else "error",
            agent=AGENT_NAME,
            related_id=str(alert_id),
        )

    # Blocos atrasados
    overdue = progress.get("overdue_blocks", [])
    if overdue:
        notifier.warning("Blocos atrasados:", AGENT_NAME)
        for b in overdue:
            notifier.warning(
                f"  • {b.get('time_slot', '?')} — {b.get('task_title', '?')}",
                AGENT_NAME,
            )

    if rescheduled_actions:
        notifier.warning("Reagendamentos automáticos:", AGENT_NAME)
        for action in rescheduled_actions:
            notifier.warning(
                f"  • bloco {action.get('original_block_id')} → "
                f"{action.get('new_block_date')} {action.get('new_time_slot')}",
                AGENT_NAME,
            )

    # Life Guard — rotinas pessoais
    try:
        from agents import life_guard as _life_guard

        _life_guard.run_all_checks()
    except Exception as e:
        notifier.warning(f"Life Guard check ignorado: {e}", AGENT_NAME)

    notifier.separator()
    return {"progress": progress, "analysis": analysis}


def _run_differential_sync() -> None:
    """Callback do scheduler para sync diferencial periódico."""
    try:
        count = _notion_sync.sync_differential()
        if count:
            notifier.info(f"Auto-sync: {count} tarefa(s) sincronizada(s).", AGENT_NAME)
    except Exception as e:
        notifier.warning(f"Erro no auto-sync diferencial: {e}", AGENT_NAME)


_ecosystem_lock = threading.Lock()
_github_lock = threading.Lock()
_retrospective_lock = threading.Lock()


def _fire_and_forget(fn, lock: threading.Lock, name: str) -> None:
    """Dispara fn em thread daemon com lock anti-overlap."""
    if not lock.acquire(blocking=False):
        notifier.info(f"{name} ainda em execução — pulando rodada.", AGENT_NAME)
        return

    def _run():
        try:
            fn()
        except Exception as e:
            notifier.warning(f"Erro em {name}: {e}", AGENT_NAME)
        finally:
            lock.release()

    threading.Thread(target=_run, name=name, daemon=True).start()


def _run_ecosystem_check() -> None:
    def _do():
        from agents import ecosystem_monitor as _eco
        _eco.run()
    _fire_and_forget(_do, _ecosystem_lock, "ecosystem_monitor")


def _run_github_sync() -> None:
    from config import NOTION_TOKEN, GITHUB_TOKEN
    if not NOTION_TOKEN or not GITHUB_TOKEN:
        notifier.info("github_sync ignorado: NOTION_TOKEN ou GITHUB_TOKEN ausente.", AGENT_NAME)
        return

    def _do():
        from agents import github_projects as _gh
        _gh.sync_all_orgs(dry_run=False)
    _fire_and_forget(_do, _github_lock, "github_projects")


def _run_retrospective() -> None:
    def _do():
        from agents import retrospective as _retro
        _retro.run_retrospective(push_to_notion=True)
    _fire_and_forget(_do, _retrospective_lock, "retrospective")


def _background_loop() -> None:
    """Thread principal do Focus Guard — roda o scheduler.run_pending() em loop."""
    # Lê configuração do Sanity; cai nos valores de env/config.py se indisponível
    cfg = sanity_client.get_agent_config(AGENT_NAME) or {}
    if not cfg.get("enabled", True):
        notifier.warning(
            "Focus Guard desabilitado via Sanity (agent_config.enabled=false). Encerrando loop.",
            AGENT_NAME,
        )
        return
    interval = int(cfg.get("check_interval_minutes") or FOCUS_CHECK_INTERVAL_MINUTES)
    if interval != FOCUS_CHECK_INTERVAL_MINUTES:
        notifier.info(
            f"Intervalo de check lido do Sanity: {interval} min (env={FOCUS_CHECK_INTERVAL_MINUTES}).",
            AGENT_NAME,
        )

    # Configura o job periódico de check de foco
    schedule.every(interval).minutes.do(_run_focus_check)

    # Configura sync diferencial periódico
    schedule.every(NOTION_SYNC_INTERVAL_MINUTES).minutes.do(_run_differential_sync)

    # Ecosystem: health check a cada 60 min
    schedule.every(60).minutes.do(_run_ecosystem_check)

    # GitHub Projects: sync a cada 30 min (fire-and-forget, com guard de pré-requisitos)
    schedule.every(30).minutes.do(_run_github_sync)

    # Retrospective: semanalmente às 21h, toda segunda-feira
    schedule.every().monday.at("21:00").do(_run_retrospective)

    # Executa uma verificação imediata ao iniciar (protegida contra falha de Redis)
    try:
        _run_focus_check()
    except Exception as e:
        notifier.warning(
            f"Check inicial ignorado (Redis indisponível?): {e}", AGENT_NAME
        )

    while not _stop_event.is_set():
        try:
            schedule.run_pending()
        except Exception as e:
            notifier.warning(f"Erro no scheduler (ignorado): {e}", AGENT_NAME)
        time.sleep(30)  # Polling a cada 30 segundos

    notifier.info("Focus Guard encerrado.", AGENT_NAME)


# ---------------------------------------------------------------------------
# API pública — start/stop da thread de background
# ---------------------------------------------------------------------------


def start_guard() -> None:
    """Inicia o Focus Guard em background thread (daemon)."""
    global _guard_thread
    if _guard_thread and _guard_thread.is_alive():
        notifier.warning("Focus Guard já está rodando.", AGENT_NAME)
        return

    _stop_event.clear()
    _guard_thread = threading.Thread(
        target=_background_loop,
        name="FocusGuardThread",
        daemon=True,
    )
    _guard_thread.start()
    notifier.success(
        f"Focus Guard em background (check a cada {FOCUS_CHECK_INTERVAL_MINUTES} min).",
        AGENT_NAME,
    )


def stop_guard() -> None:
    """Para o Focus Guard."""
    _stop_event.set()
    schedule.clear()
    notifier.info("Focus Guard parado.", AGENT_NAME)


def is_running() -> bool:
    """Verifica se o Focus Guard está ativo."""
    return _guard_thread is not None and _guard_thread.is_alive()


def force_check() -> dict:
    """Força uma verificação imediata (chamável pelo Orchestrator).

    Computa progress e analysis uma única vez e repassa para _run_focus_check,
    evitando chamadas LLM duplicadas.
    """
    notifier.agent_event("Verificação forçada pelo Orchestrator.", AGENT_NAME)
    progress = analyze_progress()
    analysis = analyze_with_llm(progress)
    return _run_focus_check(progress=progress, analysis=analysis)


# ---------------------------------------------------------------------------
# Gestão de sessões de foco (Pomodoro-style)
# ---------------------------------------------------------------------------


def start_focus_session(task_id: int, task_title: str, minutes: int = 25) -> dict:
    """Inicia uma sessão de foco rastreada."""
    # Encerra sessão anterior se existir
    active = memory.get_active_focus_session()
    if active:
        memory.end_focus_session(active["id"], status="abandoned")
        notifier.warning(
            f"Sessão anterior '{active['task_title']}' encerrada (abandonada).",
            AGENT_NAME,
        )

    session_id = memory.start_focus_session(task_id, task_title, minutes)
    notifier.focus_alert(
        f"🎯 Sessão de foco iniciada: '{task_title}' ({minutes} minutos)", AGENT_NAME
    )
    memory.set_state("current_focus_task", {"task_id": task_id, "title": task_title})

    return {
        "session_id": session_id,
        "task_title": task_title,
        "planned_minutes": minutes,
    }


def end_focus_session(status: str = "completed", notes: str = "") -> dict:
    """Encerra a sessão de foco ativa."""
    active = memory.get_active_focus_session()
    if not active:
        notifier.warning("Nenhuma sessão de foco ativa.", AGENT_NAME)
        return {"message": "Nenhuma sessão ativa."}

    memory.end_focus_session(active["id"], status, notes or None)
    memory.set_state("current_focus_task", None)

    emoji = "✅" if status == "completed" else "⚠️"
    notifier.success(
        f"{emoji} Sessão encerrada: '{active['task_title']}' ({status})", AGENT_NAME
    )
    return {
        "session_id": active["id"],
        "status": status,
        "task_title": active["task_title"],
    }


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

        if action == "start_guard":
            start_guard()
            result = {"message": "Focus Guard iniciado.", "running": True}

        elif action == "stop_guard":
            stop_guard()
            result = {"message": "Focus Guard parado.", "running": False}

        elif action == "force_check":
            check = force_check()
            result = check

        elif action == "start_session":
            session = start_focus_session(
                task_id=payload["task_id"],
                task_title=payload["task_title"],
                minutes=payload.get("minutes", 25),
            )
            result = session

        elif action == "end_session":
            session = end_focus_session(
                status=payload.get("status", "completed"),
                notes=payload.get("notes", ""),
            )
            result = session

        elif action == "status":
            state = memory.get_state(_state_key, {})
            active = memory.get_active_focus_session()
            result = {
                "running": is_running(),
                "last_check": state.get("last_check"),
                "on_track": state.get("on_track", True),
                "deviation_level": state.get("deviation_level", "none"),
                "active_session": active,
            }

        elif action == "get_alerts":
            alerts = memory.get_pending_alerts()
            result = {"alerts": alerts, "count": len(alerts)}

        else:
            raise ValueError(f"Ação desconhecida: '{action}'")

        memory.update_handoff_result(handoff_id, result, "success")
        return {"status": "success", "result": result}

    except Exception as exc:
        error_msg = str(exc)
        notifier.error(f"Erro no handoff '{action}': {error_msg}", AGENT_NAME)
        memory.update_handoff_result(handoff_id, {"error": error_msg}, "error")
        return {"status": "error", "result": {"error": error_msg}}
