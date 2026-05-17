# =============================================================================
# web/views.py — Helpers de apresentação para os templates web
# =============================================================================
# Funções puras de formatação, construção de contextos e parsing.
# Sem dependência de FastAPI (Request, Form, etc.).
# Importadas por web/app.py.

from __future__ import annotations

import json
import re
from collections import deque
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from agents import focus_guard, orchestrator
from config import LOG_FILE
from core import memory

_HHMM_RE = re.compile(r"(\d{1,2}):(\d{2})")
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


# ---------------------------------------------------------------------------
# Slot / time helpers
# ---------------------------------------------------------------------------


def parse_slot_range(block_date: str | None, time_slot: str | None):
    """Converte 'YYYY-MM-DD' + '09:00-10:00' em datetimes comparáveis."""
    if not block_date or not time_slot or "-" not in time_slot:
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


def format_slot_label(
    block_date: str | None, time_slot: str | None, today: date
) -> str:
    """Formata label de um bloco de agenda para exibição nas listas de tarefas."""
    tomorrow = today + timedelta(days=1)

    try:
        block_day = datetime.strptime(block_date, "%Y-%m-%d").date() if block_date else None
    except ValueError:
        block_day = None

    if block_day:
        if block_day == today:
            day_label = "Hoje"
        elif block_day == tomorrow:
            day_label = "Amanhã"
        elif block_day < today:
            day_label = f"{block_day.strftime('%d/%m')} (vencida)"
        else:
            day_label = block_day.strftime("%d/%m")
    else:
        day_label = ""

    if time_slot:
        return f"{day_label} · {time_slot}" if day_label else time_slot

    return day_label if day_label else ""


def format_scheduled_time(scheduled_time: str | None, today: date) -> str:
    """
    Formata scheduled_time de forma legível para o front.
    Exemplos:
      "2026-04-07 14:00" → "Hoje · 14:00"
      "2026-04-08"       → "Para amanhã"
      "2026-04-10"       → "Para 10/04"
      "09:00"            → "Hoje · 09:00"
    Retorna "" se vazio.
    """
    raw = (scheduled_time or "").strip()
    if not raw:
        return ""

    date_match = _DATE_RE.search(raw)
    hhmm_match = _HHMM_RE.search(raw)

    block_date = None
    if date_match:
        try:
            block_date = datetime.strptime(date_match.group(0), "%Y-%m-%d").date()
        except ValueError:
            pass

    hhmm_str = ""
    if hhmm_match:
        h, m = hhmm_match.groups()
        try:
            hhmm_str = f"{int(h):02d}:{m}"
        except ValueError:
            pass

    if block_date:
        tomorrow = today + timedelta(days=1)
        if block_date == today:
            day_label = "Hoje"
        elif block_date == tomorrow:
            day_label = "Amanhã"
        elif block_date < today:
            day_label = f"{block_date.strftime('%d/%m')} (vencida)"
        else:
            day_label = block_date.strftime("%d/%m")

        if hhmm_str:
            return f"{day_label} · {hhmm_str}"
        return f"Para {day_label}"

    if hhmm_str:
        return f"Hoje · {hhmm_str}"

    return raw


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------


def _safe(fn, fallback):
    """Executa fn(); retorna fallback se qualquer exceção ocorrer."""
    try:
        return fn()
    except Exception:
        return fallback


def build_task_views(include_completed: bool = True) -> tuple[list[dict], dict]:
    """Cria uma leitura temporal das tarefas para o frontend."""
    now = datetime.now()
    today = now.date()
    priority_rank = {"Alta": 0, "Média": 1, "Media": 1, "Baixa": 2}
    tasks = _safe(memory.list_all_tasks, [])
    task_ids = [task["id"] for task in tasks]
    blocks_by_task = _safe(
        lambda: memory.get_agenda_blocks_for_tasks(task_ids),
        {task_id: [] for task_id in task_ids},
    )
    task_views = []

    for task in tasks:
        view = dict(task)
        blocks = blocks_by_task.get(task["id"], [])
        open_blocks = [
            block
            for block in blocks
            if not block.get("completed") and not block.get("rescheduled")
        ]

        overdue_blocks = []
        for block in open_blocks:
            slot_range = parse_slot_range(
                block.get("block_date"), block.get("time_slot")
            )
            if slot_range:
                _, end_dt = slot_range
                if end_dt < now:
                    overdue_blocks.append(block)
                continue
            if (block.get("block_date") or "") < today.isoformat():
                overdue_blocks.append(block)

        open_blocks.sort(
            key=lambda block: (
                block.get("block_date") or "9999-99-99",
                block.get("time_slot") or "99:99-99:99",
            )
        )
        overdue_blocks.sort(
            key=lambda block: (
                block.get("block_date") or "9999-99-99",
                block.get("time_slot") or "99:99-99:99",
            )
        )

        next_block = open_blocks[0] if open_blocks else None
        overdue_block = overdue_blocks[0] if overdue_blocks else None
        original_status = task.get("status") or "A fazer"

        if original_status == "Concluído":
            display_status = "Concluído"
            status_class = "badge-ok"
            meta = (
                f"Concluída às {task.get('actual_time')}"
                if task.get("actual_time")
                else "Concluída"
            )
        elif overdue_block:
            display_status = "Pendente"
            status_class = "badge-warn"
            meta = f"Bloco vencido · {format_slot_label(overdue_block.get('block_date'), overdue_block.get('time_slot'), today)}"
        elif original_status == "Em progresso":
            display_status = "Em progresso"
            status_class = "badge-def"
            meta = (
                format_slot_label(
                    next_block.get("block_date"),
                    next_block.get("time_slot"),
                    today,
                )
                if next_block
                else (
                    format_scheduled_time(task.get("scheduled_time"), today)
                    or "Sem bloco associado"
                )
            )
        else:
            display_status = "A fazer"
            status_class = "badge-def"
            meta = (
                format_slot_label(
                    next_block.get("block_date"),
                    next_block.get("time_slot"),
                    today,
                )
                if next_block
                else (
                    format_scheduled_time(task.get("scheduled_time"), today)
                    or "Sem horário definido"
                )
            )

        meta_is_schedule = (
            not overdue_block
            and original_status not in ("Concluído",)
            and bool(meta)
            and not meta.startswith("Bloco vencido")
            and not meta.startswith("Sem")
        )
        view.update(
            {
                "display_status": display_status,
                "display_status_class": status_class,
                "display_meta": meta,
                "display_meta_is_date": meta_is_schedule,
                "is_overdue": bool(overdue_block),
            }
        )
        task_views.append(view)

    if not include_completed:
        task_views = [
            task for task in task_views if task["display_status"] != "Concluído"
        ]

    status_rank = {"Pendente": 0, "Em progresso": 1, "A fazer": 2, "Concluído": 3}
    task_views.sort(
        key=lambda task: (
            status_rank.get(task.get("display_status", "A fazer"), 4),
            priority_rank.get(task.get("priority", "Média"), 1),
            task.get("scheduled_time") or "99:99",
            -(task.get("id") or 0),
        )
    )

    overview = {
        "pending_count": sum(
            1
            for task in task_views
            if task["display_status"] in {"Pendente", "A fazer"}
        ),
        "overdue_count": sum(
            1 for task in task_views if task["display_status"] == "Pendente"
        ),
        "in_progress_count": sum(
            1 for task in task_views if task["display_status"] == "Em progresso"
        ),
        "done_count": sum(
            1 for task in task_views if task["display_status"] == "Concluído"
        ),
    }
    return task_views, overview


def build_agenda_blocks(include_rescheduled: bool = False) -> list[dict]:
    now = datetime.now()
    today = now.date()
    blocks = _safe(
        lambda: memory.get_today_agenda(include_rescheduled=include_rescheduled),
        [],
    )
    block_views = []
    for block in blocks:
        view = dict(block)
        slot_range = parse_slot_range(view.get("block_date"), view.get("time_slot"))
        is_overdue = False
        if not view.get("completed") and not view.get("rescheduled"):
            if slot_range:
                _, end_dt = slot_range
                is_overdue = end_dt < now
            elif (view.get("block_date") or "") < today.isoformat():
                is_overdue = True

        if view.get("completed"):
            state_label = "Concluído"
            state_class = "badge-ok"
        elif view.get("rescheduled"):
            state_label = "Reagendado"
            state_class = "badge-warn"
        elif is_overdue:
            state_label = "Pendente"
            state_class = "badge-warn"
        else:
            state_label = "Aberto"
            state_class = "badge-def"

        view.update(
            {
                "display_state_label": state_label,
                "display_state_class": state_class,
                "is_overdue": is_overdue,
            }
        )
        block_views.append(view)
    return block_views


def build_summary_ctx(include_completed: bool = False) -> dict:
    """Contexto de resumo do sistema — nunca lança exceção. Sem Request."""
    summary = _safe(
        orchestrator.get_system_summary,
        {
            "tasks": {"a_fazer": 0, "em_progresso": 0, "concluido": 0},
            "focus": {"guard_running": focus_guard.is_running(), "on_track": True},
            "agenda_today": {"total_blocks": 0, "completed": 0},
            "alerts": {"pending": 0},
            "redis_ok": False,
        },
    )
    _, task_overview = build_task_views(include_completed=include_completed)
    return {"summary": summary, "task_overview": task_overview}


def tail_logs(limit: int = 120) -> list[str]:
    log_path = Path(LOG_FILE)
    if not log_path.exists():
        return []
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        return list(deque(handle, maxlen=limit))


def build_audit_ctx() -> dict:
    return {
        "summary": build_summary_ctx()["summary"],
        "audit_events": _safe(lambda: memory.list_audit_events(60), []),
        "alerts": _safe(lambda: memory.list_alerts(30), []),
        "handoffs": _safe(lambda: memory.list_recent_handoffs(30), []),
        "log_lines": tail_logs(120),
    }


def normalize_range(start_date: str | None, end_date: str | None) -> tuple[str, str]:
    today = date.today()
    default_start = today - timedelta(days=7)
    default_end = today + timedelta(days=7)
    try:
        start_dt = (
            datetime.strptime(start_date, "%Y-%m-%d").date()
            if start_date
            else default_start
        )
        end_dt = (
            datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else default_end
        )
    except ValueError:
        return default_start.isoformat(), default_end.isoformat()

    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt
    return start_dt.isoformat(), end_dt.isoformat()


def build_agenda_history_ctx(start_date: str | None, end_date: str | None) -> dict:
    normalized_start, normalized_end = normalize_range(start_date, end_date)
    blocks = _safe(
        lambda: memory.list_agenda_between(
            normalized_start,
            normalized_end,
            include_rescheduled=True,
        ),
        [],
    )
    return {
        "summary": build_summary_ctx()["summary"],
        "blocks": blocks,
        "start_date": normalized_start,
        "end_date": normalized_end,
    }


# ---------------------------------------------------------------------------
# Ecosystem
# ---------------------------------------------------------------------------


def build_ecosystem_ctx(data: dict) -> dict:
    """Converte dados do health_check em contexto para o template."""
    import datetime as _dt

    summary = data.get("summary", {})
    github = data.get("github", {})
    railway = data.get("railway", {})
    onchain = data.get("onchain", {})

    railway_services = []
    for name, info in railway.items():
        railway_services.append(
            {
                "name": name,
                "status": info.get("status", "dim"),
                "http_code": info.get("http_code"),
                "response_ms": info.get("response_ms"),
                "error": info.get("error"),
                "priority": info.get("priority", "P2"),
            }
        )
    order = {"fail": 0, "warn": 1, "ok": 2, "dim": 3}
    railway_services.sort(key=lambda s: (order.get(s["status"], 9), s["priority"]))

    github_orgs = []
    for org, info in github.items():
        github_orgs.append(
            {
                "name": org,
                "status": info.get("status", "dim"),
                "active_24h": info.get("repos_active_24h", 0),
                "issues": info.get("open_issues", 0),
                "stale": info.get("repos_stale", []),
            }
        )

    neoflw = onchain.get("NEOFLW", {"status": "dim"})

    rw_fail = [s["name"] for s in railway_services if s["status"] == "fail"]
    rw_warn = [s["name"] for s in railway_services if s["status"] == "warn"]
    stale = summary.get("github", {}).get("repos_stale_priority", [])
    actions = []
    if rw_fail:
        actions.append(f"verificar serviço com falha: {', '.join(rw_fail)}")
    if rw_warn:
        actions.append(f"investigar: {', '.join(rw_warn)}")
    if stale:
        actions.append(
            f"repos estagnados: {', '.join(stale[:5])}{'...' if len(stale) > 5 else ''}"
        )
    if neoflw.get("alerts"):
        actions.append("monitorar NEOFLW — alertas ativos")

    rw_s = summary.get("railway", {})
    ts_raw = data.get("timestamp", "")
    try:
        ts = _dt.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        ts_str = ts.strftime("%H:%M")
    except Exception:
        ts_str = ts_raw[:16]

    return {
        "global_status": data.get("status", "unknown"),
        "timestamp": ts_str,
        "railway_ok": rw_s.get("services_ok", 0),
        "railway_total": rw_s.get("services_total", 0),
        "railway_warn": rw_s.get("services_warn", 0),
        "railway_fail": rw_s.get("services_fail", 0),
        "repos_active": summary.get("github", {}).get("repos_active_24h", 0),
        "railway_services": railway_services,
        "github_orgs": github_orgs,
        "neoflw": neoflw,
        "actions": actions,
    }


def load_ecosystem_data() -> dict:
    """Carrega health check do Redis ou retorna estrutura vazia."""
    try:
        raw = memory.get_state("ecosystem:health_check:latest")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            return json.loads(raw)
    except Exception:
        pass
    return {
        "status": "unknown",
        "summary": {},
        "github": {},
        "railway": {},
        "onchain": {},
        "timestamp": "",
    }
