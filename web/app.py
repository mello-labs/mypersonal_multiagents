# =============================================================================
# web/app.py — Interface Web (FastAPI + HTMX + Jinja2)
# =============================================================================
# Expõe o Orchestrator via HTTP com UI minimalista dark-mode.
# O Focus Guard roda em background thread via lifespan.
#
# Iniciar:  python -m web.app
#           uvicorn web.app:app --reload --port 8000

import asyncio
import sys
import threading
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import BackgroundTasks, FastAPI, Form, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agents import calendar_sync, focus_guard, notion_sync, orchestrator
from config import LOG_FILE
from core import memory

BASE_DIR = Path(__file__).parent
MAX_CHAT_TURNS = 12
CHAT_SESSION_COOKIE = "multiagentes_chat_sid"
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
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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


def _summary_ctx() -> dict:
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
    return {"summary": summary}


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


def _get_chat_session_id(request: Request) -> tuple[str, bool]:
    current = request.cookies.get(CHAT_SESSION_COOKIE)
    if current:
        return current, False
    return uuid.uuid4().hex, True


def _get_chat_history(session_id: str) -> list[dict]:
    with _chat_sessions_lock:
        history = _chat_sessions.get(session_id, [])
        return list(history)


def _store_chat_turn(session_id: str, role: str, content: str) -> None:
    with _chat_sessions_lock:
        history = list(_chat_sessions.get(session_id, []))
        history.append({"role": role, "content": content})
        _chat_sessions[session_id] = history[-MAX_CHAT_TURNS:]


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
    except Exception as e:
        result["db"] = "unavailable"
        result["db_error"] = str(e)[:120]
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Rotas full-page
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    ctx = _summary_ctx()
    ctx["agenda"] = _safe(memory.get_today_agenda, [])
    ctx["tasks"] = _safe(memory.list_all_tasks, [])
    ctx["redis_warn"] = "" if ctx["summary"].get("redis_ok") else _REDIS_WARN
    ctx["page_name"] = "dashboard"
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/audit", response_class=HTMLResponse)
async def audit(request: Request):
    ctx = _audit_ctx()
    ctx["page_name"] = "audit"
    return templates.TemplateResponse(request, "audit.html", ctx)


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
            blocks = _safe(memory.get_today_agenda, [])
        return templates.TemplateResponse(
            request,
            "partials/agenda.html",
            {"blocks": blocks},
        )

    ctx = _agenda_history_ctx(start_date, end_date)
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
    history = _get_chat_history(session_id)
    context = {
        "chat_history": history[-6:],
        "system_summary": _safe(orchestrator.get_system_summary, {}),
    }
    try:
        response = await asyncio.to_thread(orchestrator.process, message, context)
    except Exception as e:
        response = f"⚠️ Erro: {e}"
    _store_chat_turn(session_id, "user", message)
    _store_chat_turn(session_id, "assistant", response)
    template_response = templates.TemplateResponse(
        request,
        "partials/chat_message.html",
        {"user_message": message, "bot_response": response},
    )
    if is_new_session:
        template_response.set_cookie(
            CHAT_SESSION_COOKIE,
            session_id,
            httponly=True,
            samesite="lax",
        )
    return template_response


@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    return templates.TemplateResponse(request, "partials/status.html", _summary_ctx())


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
async def tasks(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/tasks.html",
        {"tasks": _safe(memory.list_all_tasks, [])},
    )


@app.post("/task", response_class=HTMLResponse)
async def create_task(
    request: Request,
    title: str = Form(...),
    priority: str = Form("Média"),
    scheduled_time: str = Form(""),
):
    _safe(
        lambda: memory.create_task(
            title=title,
            priority=priority,
            scheduled_time=scheduled_time or None,
        ),
        None,
    )
    return templates.TemplateResponse(
        request,
        "partials/tasks.html",
        {"tasks": _safe(memory.list_all_tasks, [])},
    )


@app.post("/task/{task_id}/complete", response_class=HTMLResponse)
async def complete_task(request: Request, task_id: int):
    _safe(lambda: memory.update_task_status(task_id, "Concluído"), None)
    task = _safe(lambda: memory.get_task(task_id), None)
    if task:
        # Swap cirúrgico: retorna só a linha atualizada (preserva scroll)
        return templates.TemplateResponse(
            request, "partials/task_row.html", {"t": task}
        )
    return templates.TemplateResponse(
        request,
        "partials/tasks.html",
        {"tasks": _safe(memory.list_all_tasks, [])},
    )


@app.post("/sync", response_class=HTMLResponse)
async def sync(request: Request):
    """Sync com Notion — I/O bloqueante em thread pool; retorna imediatamente."""
    try:
        count = await asyncio.to_thread(notion_sync.sync_differential)
        sync_msg = f"{count} tarefa(s) sincronizada(s)."
    except Exception as e:
        sync_msg = f"⚠️ Sync falhou: {str(e)[:80]}"
    ctx = _summary_ctx()
    ctx["sync_msg"] = sync_msg
    return templates.TemplateResponse(request, "partials/status.html", ctx)


@app.post("/block/{block_id}/complete", response_class=HTMLResponse)
async def complete_block(request: Request, block_id: int):
    _safe(lambda: memory.mark_block_completed(block_id, True), None)
    block = _safe(lambda: memory.get_block(block_id), None)
    if block:
        return templates.TemplateResponse(
            request, "partials/block_row.html", {"b": block}
        )
    return templates.TemplateResponse(
        request,
        "partials/agenda.html",
        {"blocks": _safe(memory.get_today_agenda, [])},
    )


# ---------------------------------------------------------------------------
# Entry point direto
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    from config import WEB_HOST, WEB_PORT

    uvicorn.run("web.app:app", host=WEB_HOST, port=WEB_PORT, reload=True)
