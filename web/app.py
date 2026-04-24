# =============================================================================
# web/app.py — Interface Web (FastAPI + HTMX + Jinja2)
# =============================================================================
# Expõe o Orchestrator via HTTP com UI minimalista dark-mode.
# O Focus Guard roda em background thread via lifespan.
#
# Iniciar:  python -m web.app
#           uvicorn web.app:app --reload --port 8000

import asyncio
import jinja2 as _jinja2
import json
import os
import re
import sys
import threading
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agents import calendar_sync, focus_guard, notion_sync, orchestrator
from agents.persona_manager import get_persona, list_personas, set_active_persona
from config import LOG_FILE
from core import memory

BASE_DIR = Path(__file__).parent
MAX_CHAT_TURNS = 12
CHAT_SESSION_COOKIE = "multiagentes_chat_sid"
PERSONA_COOKIE = "multiagentes_persona"
CHAT_HISTORY_TTL_SECONDS = int(os.getenv("CHAT_HISTORY_TTL_SECONDS", "86400"))
_chat_sessions: dict[str, list[dict]] = {}
_chat_sessions_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Lifespan: inicia/para Focus Guard junto com o servidor
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        memory.init_db()
    except Exception as e:
        print(f"[WARN] Redis indisponível no startup: {e}")
        print("[WARN] App iniciando sem Redis — configure REDIS_URL no Railway.")
    if not focus_guard.is_running():
        focus_guard.start_guard()
    yield
    focus_guard.stop_guard()


app = FastAPI(title="Multiagentes", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


_jinja2_env = _jinja2.Environment(
    loader=_jinja2.FileSystemLoader(str(BASE_DIR / "templates")),
    autoescape=True,
    auto_reload=False,  # workaround: Python 3.14 + Jinja2 3.1.x LRU cache bug
)
templates = Jinja2Templates(env=_jinja2_env)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(str(BASE_DIR / "static" / "favicon.ico"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REDIS_WARN = "Redis indisponível — configure REDIS_URL no Railway."
_NOTION_WARN = "Notion não configurado — defina NOTION_API_KEY e NOTION_DATABASE_ID."


def _safe(fn, fallback):
    """Executa fn(); retorna fallback se qualquer exceção ocorrer."""
    try:
        return fn()
    except Exception:
        return fallback


async def _safe_async(coro, fallback):
    """Aguarda coro; retorna fallback em caso de erro."""
    try:
        return await coro
    except Exception:
        return fallback


def _get_persona_id(request: Request) -> str:
    """Lê o ID da persona ativa do cookie."""
    return request.cookies.get(PERSONA_COOKIE, "coordinator")


def _persona_ctx(request: Request) -> dict:
    """Contexto de persona para os templates."""
    persona_id = _get_persona_id(request)
    active = get_persona(persona_id)
    return {
        "personas": list_personas(),
        "active_persona": active,
        "active_persona_id": persona_id,
    }


def _parse_slot_range(block_date: str | None, time_slot: str | None):
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


def _format_slot_label(
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

    # Bloco date-only (sem horário)
    return day_label if day_label else ""


_HHMM_RE = re.compile(r"(\d{1,2}):(\d{2})")
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _format_scheduled_time(scheduled_time: str | None, today: date) -> str:
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


def _build_task_views(include_completed: bool = True) -> tuple[list[dict], dict]:
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
            slot_range = _parse_slot_range(
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
            meta = f"Bloco vencido · {_format_slot_label(overdue_block.get('block_date'), overdue_block.get('time_slot'), today)}"
        elif original_status == "Em progresso":
            display_status = "Em progresso"
            status_class = "badge-def"
            meta = (
                _format_slot_label(
                    next_block.get("block_date"),
                    next_block.get("time_slot"),
                    today,
                )
                if next_block
                else (
                    _format_scheduled_time(task.get("scheduled_time"), today)
                    or "Sem bloco associado"
                )
            )
        else:
            display_status = "A fazer"
            status_class = "badge-def"
            meta = (
                _format_slot_label(
                    next_block.get("block_date"),
                    next_block.get("time_slot"),
                    today,
                )
                if next_block
                else (
                    _format_scheduled_time(task.get("scheduled_time"), today)
                    or "Sem horário definido"
                )
            )

        # True quando a meta é um horário/data agendado (azul),
        # False quando é um aviso operacional (branco/laranja)
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


def _build_agenda_blocks(include_rescheduled: bool = False) -> list[dict]:
    now = datetime.now()
    today = now.date()
    blocks = _safe(
        lambda: memory.get_today_agenda(include_rescheduled=include_rescheduled),
        [],
    )
    block_views = []
    for block in blocks:
        view = dict(block)
        slot_range = _parse_slot_range(view.get("block_date"), view.get("time_slot"))
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


def _summary_ctx(request: Request = None, include_completed: bool = False) -> dict:
    """Contexto de resumo do sistema — nunca lança exceção."""
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
    _, task_overview = _build_task_views(include_completed=include_completed)
    ctx = {"summary": summary, "task_overview": task_overview}
    if request:
        ctx.update(_persona_ctx(request))
    return ctx


def _tail_logs(limit: int = 120) -> list[str]:
    log_path = Path(LOG_FILE)
    if not log_path.exists():
        return []
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        return list(deque(handle, maxlen=limit))


def _audit_ctx() -> dict:
    return {
        "summary": _summary_ctx()["summary"],
        "audit_events": _safe(lambda: memory.list_audit_events(60), []),
        "alerts": _safe(lambda: memory.list_alerts(30), []),
        "handoffs": _safe(lambda: memory.list_recent_handoffs(30), []),
        "log_lines": _tail_logs(120),
    }


def _normalize_range(start_date: str | None, end_date: str | None) -> tuple[str, str]:
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


def _agenda_history_ctx(start_date: str | None, end_date: str | None) -> dict:
    normalized_start, normalized_end = _normalize_range(start_date, end_date)
    blocks = _safe(
        lambda: memory.list_agenda_between(
            normalized_start,
            normalized_end,
            include_rescheduled=True,
        ),
        [],
    )
    return {
        "summary": _summary_ctx()["summary"],
        "blocks": blocks,
        "start_date": normalized_start,
        "end_date": normalized_end,
    }


def _is_https(request: Request) -> bool:
    """Detecta HTTPS via proxy header (Railway/Vercel) ou scheme direto."""
    proto = request.headers.get("x-forwarded-proto", "")
    return proto == "https" or request.url.scheme == "https"


def _get_chat_session_id(request: Request) -> tuple[str, bool]:
    current = request.cookies.get(CHAT_SESSION_COOKIE)
    if current:
        return current, False
    return uuid.uuid4().hex, True


def _chat_history_key(session_id: str) -> str:
    return f"chat:history:{session_id}"


def _get_chat_history(session_id: str) -> list[dict]:
    # Fonte primária: Redis (persistente entre restarts/deploys)
    try:
        r = memory.get_redis()
        raw_items = r.lrange(_chat_history_key(session_id), 0, -1)
        if raw_items:
            parsed_history = []
            for item in raw_items:
                try:
                    parsed = json.loads(item)
                    role = parsed.get("role")
                    content = parsed.get("content")
                    if role and content is not None:
                        parsed_history.append({"role": role, "content": content})
                except Exception:
                    continue
            if parsed_history:
                with _chat_sessions_lock:
                    _chat_sessions[session_id] = parsed_history[-MAX_CHAT_TURNS:]
                return parsed_history[-MAX_CHAT_TURNS:]
    except Exception:
        pass

    # Fallback: memória local do processo
    with _chat_sessions_lock:
        history = _chat_sessions.get(session_id, [])
        return list(history)


def _store_chat_turn(session_id: str, role: str, content: str) -> None:
    turn = {"role": role, "content": content}

    # Sempre mantém fallback local
    with _chat_sessions_lock:
        history = list(_chat_sessions.get(session_id, []))
        history.append(turn)
        _chat_sessions[session_id] = history[-MAX_CHAT_TURNS:]

    # Persistência principal em Redis com TTL
    try:
        r = memory.get_redis()
        key = _chat_history_key(session_id)
        r.rpush(key, json.dumps(turn, ensure_ascii=False))
        r.ltrim(key, -MAX_CHAT_TURNS, -1)
        r.expire(key, CHAT_HISTORY_TTL_SECONDS)
    except Exception:
        # Se Redis falhar, o fallback local garante continuidade da conversa
        pass


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Lightweight health check — sempre retorna 200 se o processo está vivo."""
    result: dict = {"status": "ok"}
    try:
        tasks_count = len(memory.list_all_tasks())
        result["db"] = "ok"
        result["tasks"] = tasks_count
    except Exception:
        result["db"] = "unavailable"
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Rotas full-page
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    ctx = _summary_ctx(request)
    tasks, task_overview = _build_task_views(include_completed=False)
    agenda_blocks = _build_agenda_blocks()
    ctx["agenda"] = agenda_blocks
    ctx["blocks"] = ctx["agenda"]  # alias for partials/agenda.html
    ctx["tasks"] = tasks
    ctx["task_overview"] = task_overview
    ctx["redis_warn"] = "" if ctx["summary"].get("redis_ok") else _REDIS_WARN
    ctx["page_name"] = "dashboard"
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/audit", response_class=HTMLResponse)
async def audit(request: Request):
    ctx = _audit_ctx()
    ctx.update(_persona_ctx(request))
    ctx["page_name"] = "audit"
    return templates.TemplateResponse(request, "audit.html", ctx)


@app.post("/alert/{alert_id}/dismiss", response_class=HTMLResponse)
async def dismiss_alert(alert_id: int):
    """Descarta um alerta individual — remove de alerts:pending."""
    _safe(lambda: memory.acknowledge_alert(alert_id), None)
    return HTMLResponse("")  # HTMX remove o elemento com hx-swap="outerHTML"


@app.post("/alerts/dismiss-all", response_class=HTMLResponse)
async def dismiss_all_alerts():
    """Descarta todos os alertas pendentes de uma vez."""
    pending = _safe(lambda: memory.get_pending_alerts(), []) or []
    for alert in pending:
        _safe(lambda a=alert: memory.acknowledge_alert(a["id"]), None)
    return HTMLResponse('<div class="empty">Sem alertas pendentes</div>')


@app.get("/agenda", response_class=HTMLResponse)
async def agenda(
    request: Request,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
):
    if request.headers.get("HX-Request") == "true":
        if start_date or end_date:
            normalized_start, normalized_end = _normalize_range(start_date, end_date)
            blocks = _safe(
                lambda: memory.list_agenda_between(
                    normalized_start,
                    normalized_end,
                    include_rescheduled=True,
                ),
                [],
            )
        else:
            blocks = _build_agenda_blocks()
        return templates.TemplateResponse(
            request,
            "partials/agenda.html",
            {"blocks": blocks},
        )

    ctx = _agenda_history_ctx(start_date, end_date)
    ctx.update(_persona_ctx(request))
    ctx["page_name"] = "agenda"
    return templates.TemplateResponse(request, "agenda.html", ctx)


@app.get("/agenda/history", response_class=HTMLResponse)
async def agenda_history_redirect(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
):
    query_parts = []
    if start_date:
        query_parts.append(f"start_date={start_date}")
    if end_date:
        query_parts.append(f"end_date={end_date}")
    query = f"?{'&'.join(query_parts)}" if query_parts else ""
    return RedirectResponse(url=f"/agenda{query}", status_code=307)


# ---------------------------------------------------------------------------
# Partials HTMX
# ---------------------------------------------------------------------------


@app.post("/chat", response_class=HTMLResponse)
async def chat(request: Request, message: str = Form(...)):
    """Chat com o Orchestrator — I/O bloqueante movido para thread pool."""
    session_id, is_new_session = _get_chat_session_id(request)
    persona_id = _get_persona_id(request)
    history = _get_chat_history(session_id)
    context = {
        "chat_history": history[-6:],
        "system_summary": _safe(orchestrator.get_system_summary, {}),
    }
    try:
        response = await asyncio.to_thread(
            orchestrator.process, message, context, persona_id
        )
    except Exception as e:
        response = f"⚠️ Erro: {e}"
    _store_chat_turn(session_id, "user", message)
    _store_chat_turn(session_id, "assistant", response)
    active_persona = get_persona(persona_id)
    template_response = templates.TemplateResponse(
        request,
        "partials/chat_message.html",
        {
            "user_message": message,
            "bot_response": response,
            "active_persona": active_persona,
        },
    )
    if is_new_session:
        template_response.set_cookie(
            CHAT_SESSION_COOKIE,
            session_id,
            httponly=True,
            samesite="lax",
            secure=_is_https(request),
            max_age=CHAT_HISTORY_TTL_SECONDS,
        )
    return template_response


@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/status.html",
        _summary_ctx(request, include_completed=False),
    )


@app.post("/agenda/import", response_class=HTMLResponse)
@app.post("/agenda/history/import", response_class=HTMLResponse)
async def import_agenda_history(
    request: Request,
    source: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
):
    normalized_start, normalized_end = _normalize_range(start_date, end_date)
    if source == "notion":
        imported = await asyncio.to_thread(
            notion_sync.sync_agenda_range_to_local,
            normalized_start,
            normalized_end,
        )
    elif source == "calendar":
        imported = await asyncio.to_thread(
            calendar_sync.import_events_range_as_blocks,
            normalized_start,
            normalized_end,
        )
    else:
        imported = 0

    ctx = _agenda_history_ctx(normalized_start, normalized_end)
    ctx["page_name"] = "agenda"
    ctx["import_msg"] = (
        f"{imported} bloco(s) importado(s) de {source} entre {normalized_start} e {normalized_end}."
    )
    return templates.TemplateResponse(request, "agenda.html", ctx)


@app.get("/tasks", response_class=HTMLResponse)
async def tasks(request: Request, include_completed: bool = Query(default=False)):
    tasks_view, _ = _build_task_views(include_completed=include_completed)
    return templates.TemplateResponse(
        request,
        "partials/tasks.html",
        {"tasks": tasks_view},
    )


@app.get("/tasks-page", response_class=HTMLResponse)
async def tasks_page(request: Request):
    ctx = _summary_ctx(request)
    ctx["tasks"], ctx["task_overview"] = _build_task_views()
    ctx["page_name"] = "tasks"
    return templates.TemplateResponse(request, "tasks_page.html", ctx)


@app.get("/chat-page", response_class=HTMLResponse)
async def chat_page(request: Request):
    ctx = _summary_ctx(request)
    ctx["page_name"] = "chat"
    return templates.TemplateResponse(request, "chat_page.html", ctx)


_VALID_PRIORITIES = {"Alta", "Média", "Baixa"}


@app.post("/task", response_class=HTMLResponse)
async def create_task(
    request: Request,
    title: str = Form(...),
    priority: str = Form("Média"),
    scheduled_time: str = Form(""),
):
    safe_priority = priority if priority in _VALID_PRIORITIES else "Média"
    _safe(
        lambda: memory.create_task(
            title=title,
            priority=safe_priority,
            scheduled_time=scheduled_time or None,
        ),
        None,
    )
    return templates.TemplateResponse(
        request,
        "partials/tasks.html",
        {"tasks": _build_task_views(include_completed=False)[0]},
    )


@app.post("/task/{task_id}/complete", response_class=HTMLResponse)
async def complete_task(request: Request, task_id: int):
    _safe(lambda: memory.update_task_status(task_id, "Concluído"), None)
    task = _safe(lambda: memory.get_task(task_id), None)
    if task:
        task_view = next(
            (item for item in _build_task_views()[0] if item["id"] == task_id),
            task,
        )
        # Swap cirúrgico: retorna só a linha atualizada (preserva scroll)
        return templates.TemplateResponse(
            request, "partials/task_row.html", {"t": task_view}
        )
    return templates.TemplateResponse(
        request,
        "partials/tasks.html",
        {"tasks": _build_task_views(include_completed=False)[0]},
    )


@app.post("/sync", response_class=HTMLResponse)
async def sync(request: Request):
    """Full sync com Notion — tarefas + agenda (±7 dias).
    I/O bloqueante em thread pool."""
    today = date.today()
    start = (today - timedelta(days=1)).isoformat()
    end = (today + timedelta(days=7)).isoformat()
    try:
        task_count = await asyncio.to_thread(notion_sync.sync_tasks_to_local)
        agenda_count = await asyncio.to_thread(
            notion_sync.sync_agenda_range_to_local, start, end
        )
        sync_msg = f"✓ {task_count} tarefa(s) · {agenda_count} agenda(s)"
    except Exception as e:
        sync_msg = f"Sync falhou: {str(e)[:80]}"
    return HTMLResponse(
        f'<span style="color:var(--t2)">{sync_msg}</span>'
    )


@app.post("/block/{block_id}/complete", response_class=HTMLResponse)
async def complete_block(request: Request, block_id: int):
    _safe(lambda: memory.mark_block_completed(block_id, True), None)
    block = _safe(lambda: memory.get_block(block_id), None)
    if block:
        block_view = next(
            (
                item
                for item in _build_agenda_blocks(include_rescheduled=True)
                if item["id"] == block_id
            ),
            block,
        )
        return templates.TemplateResponse(
            request, "partials/block_row.html", {"b": block_view}
        )
    return templates.TemplateResponse(
        request,
        "partials/agenda.html",
        {"blocks": _build_agenda_blocks()},
    )


# ---------------------------------------------------------------------------
# Persona selector
# ---------------------------------------------------------------------------


@app.get("/personas", response_class=JSONResponse)
async def personas_list():
    """Retorna lista de personas disponíveis."""
    return JSONResponse(list_personas())


@app.post("/persona/{persona_id}", response_class=HTMLResponse)
async def switch_persona(request: Request, persona_id: str):
    """Troca a persona ativa — salva no cookie e retorna o seletor atualizado."""
    set_active_persona(persona_id)
    active = get_persona(persona_id)
    all_personas = list_personas()

    # Retorna o dropdown atualizado via HTMX
    options = "".join(
        f'<option value="{p["id"]}"{"selected" if p["id"] == persona_id else ""}>'
        f"{p['icon']} {p['short_name']}</option>"
        for p in all_personas
    )
    html = (
        f'<select name="persona" '
        f'hx-post="/persona/{{this.value}}" '
        f'hx-trigger="change" '
        f'hx-target="#persona-selector" '
        f'hx-swap="innerHTML" '
        f'class="persona-select">'
        f"{options}</select>"
        f'<span class="persona-label">{active.get("icon", "●")} {active.get("short_name", "")}</span>'
    )

    response = HTMLResponse(html)
    response.set_cookie(
        PERSONA_COOKIE,
        persona_id,
        httponly=True,
        samesite="lax",
        secure=_is_https(request),
        max_age=60 * 60 * 24 * 365,
    )
    return response


# ---------------------------------------------------------------------------
# Ecosystem
# ---------------------------------------------------------------------------


def _ecosystem_ctx(data: dict) -> dict:
    """Converte dados do health_check em contexto para o template."""
    import datetime as _dt

    summary = data.get("summary", {})
    github = data.get("github", {})
    railway = data.get("railway", {})
    onchain = data.get("onchain", {})

    # Railway services list
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
    # sort: fail first, then warn, then ok; P0 before P1
    order = {"fail": 0, "warn": 1, "ok": 2, "dim": 3}
    railway_services.sort(key=lambda s: (order.get(s["status"], 9), s["priority"]))

    # GitHub orgs list
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

    # NEOFLW
    neoflw = onchain.get("NEOFLW", {"status": "dim"})

    # Actions
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


def _load_ecosystem_data() -> dict:
    """Carrega health check do Redis ou retorna estrutura vazia."""
    try:
        raw = memory.get_state("ecosystem:health_check:latest")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            import json

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


@app.get("/ecosystem-page", response_class=HTMLResponse)
async def ecosystem_page(request: Request):
    """Página do Ecosystem Monitor."""
    data = _load_ecosystem_data()
    ctx = _ecosystem_ctx(data)
    sum_ctx = _summary_ctx()
    ctx.update(
        {
            "request": request,
            "page_name": "ecosystem",
            "summary": sum_ctx["summary"],
            "task_overview": sum_ctx["task_overview"],
            **_persona_ctx(request),
        }
    )
    return templates.TemplateResponse(request, "ecosystem_page.html", ctx)


@app.get("/ecosystem", response_class=HTMLResponse)
async def ecosystem_partial(request: Request):
    """HTMX partial — refresh automático do conteúdo do ecosystem."""
    data = _load_ecosystem_data()
    ctx = _ecosystem_ctx(data)
    sum_ctx = _summary_ctx()
    ctx.update(
        {
            "page_name": "ecosystem",
            "summary": sum_ctx["summary"],
            "task_overview": sum_ctx["task_overview"],
            **_persona_ctx(request),
        }
    )
    return templates.TemplateResponse(request, "ecosystem_page.html", ctx)


@app.post("/ecosystem/run", response_class=HTMLResponse)
async def ecosystem_run(request: Request):
    """Dispara health check e retorna resultado atualizado."""
    import asyncio

    from agents import ecosystem_monitor

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, ecosystem_monitor.health_check)

    data = _load_ecosystem_data()
    ctx = _ecosystem_ctx(data)
    sum_ctx = _summary_ctx()
    ctx.update(
        {
            "page_name": "ecosystem",
            "summary": sum_ctx["summary"],
            "task_overview": sum_ctx["task_overview"],
            **_persona_ctx(request),
        }
    )
    return templates.TemplateResponse(request, "ecosystem_page.html", ctx)


# ---------------------------------------------------------------------------
# Entry point direto
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    from config import WEB_HOST, WEB_PORT

    uvicorn.run("web.app:app", host=WEB_HOST, port=WEB_PORT, reload=True)
