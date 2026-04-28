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
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path


from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

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
app.add_middleware(GZipMiddleware, minimum_size=1000)
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

from web.views import (
    _safe,
    build_agenda_blocks as _build_agenda_blocks,
    build_agenda_history_ctx as _agenda_history_ctx,
    build_ecosystem_ctx as _ecosystem_ctx,
    build_summary_ctx,
    build_task_views as _build_task_views,
    load_ecosystem_data as _load_ecosystem_data,
    normalize_range as _normalize_range,
)


def _tail_logs(limit: int = 120) -> list[str]:
    """Lê as últimas `limit` linhas de LOG_FILE (referencia o binding local de app.py)."""
    from collections import deque
    from pathlib import Path as _Path
    log_path = _Path(LOG_FILE)
    if not log_path.exists():
        return []
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        return list(deque(handle, maxlen=limit))


def _audit_ctx() -> dict:
    return {
        "summary": build_summary_ctx()["summary"],
        "audit_events": _safe(lambda: memory.list_audit_events(60), []),
        "alerts": _safe(lambda: memory.list_alerts(30), []),
        "handoffs": _safe(lambda: memory.list_recent_handoffs(30), []),
        "log_lines": _tail_logs(120),
    }


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


def _summary_ctx(request: Request = None, include_completed: bool = False) -> dict:
    """Contexto de resumo do sistema — nunca lança exceção."""
    ctx = build_summary_ctx(include_completed=include_completed)
    if request:
        ctx.update(_persona_ctx(request))
    return ctx


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
    if priority not in _VALID_PRIORITIES:
        import logging
        logging.getLogger("web.app").warning(
            "Prioridade inválida recebida: %r — usando 'Média'", priority
        )
        priority = "Média"
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
