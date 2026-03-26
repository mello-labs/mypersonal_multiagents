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
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agents import orchestrator, focus_guard
from agents import notion_sync
from core import memory

BASE_DIR = Path(__file__).parent


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
    summary = _safe(orchestrator.get_system_summary, {
        "tasks": {"a_fazer": 0, "em_progresso": 0, "concluido": 0},
        "focus": {"guard_running": focus_guard.is_running(), "on_track": True},
        "agenda_today": {"total_blocks": 0, "completed": 0},
        "alerts": {"pending": 0},
        "redis_ok": False,
    })
    return {"summary": summary}


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
    ctx["agenda"]     = _safe(memory.get_today_agenda, [])
    ctx["tasks"]      = _safe(memory.list_all_tasks, [])
    ctx["redis_warn"] = "" if ctx["summary"].get("redis_ok") else _REDIS_WARN
    return templates.TemplateResponse(request, "index.html", ctx)


# ---------------------------------------------------------------------------
# Partials HTMX
# ---------------------------------------------------------------------------

@app.post("/chat", response_class=HTMLResponse)
async def chat(request: Request, message: str = Form(...)):
    """Chat com o Orchestrator — I/O bloqueante movido para thread pool."""
    try:
        response = await asyncio.to_thread(orchestrator.process, message)
    except Exception as e:
        response = f"⚠️ Erro: {e}"
    return templates.TemplateResponse(
        request,
        "partials/chat_message.html",
        {"user_message": message, "bot_response": response},
    )


@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    return templates.TemplateResponse(request, "partials/status.html", _summary_ctx())


@app.get("/agenda", response_class=HTMLResponse)
async def agenda(request: Request):
    return templates.TemplateResponse(
        request, "partials/agenda.html",
        {"blocks": _safe(memory.get_today_agenda, [])},
    )


@app.get("/tasks", response_class=HTMLResponse)
async def tasks(request: Request):
    return templates.TemplateResponse(
        request, "partials/tasks.html",
        {"tasks": _safe(memory.list_all_tasks, [])},
    )


@app.post("/task", response_class=HTMLResponse)
async def create_task(
    request: Request,
    title: str = Form(...),
    priority: str = Form("Média"),
    scheduled_time: str = Form(""),
):
    _safe(lambda: memory.create_task(
        title=title,
        priority=priority,
        scheduled_time=scheduled_time or None,
    ), None)
    return templates.TemplateResponse(
        request, "partials/tasks.html",
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
        request, "partials/tasks.html",
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
    # Busca o bloco atualizado para swap cirúrgico
    blocks = _safe(memory.get_today_agenda, [])
    block = next((b for b in blocks if b["id"] == block_id), None)
    if block:
        return templates.TemplateResponse(
            request, "partials/block_row.html", {"b": block}
        )
    return templates.TemplateResponse(
        request, "partials/agenda.html", {"blocks": blocks}
    )


# ---------------------------------------------------------------------------
# Entry point direto
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    from config import WEB_HOST, WEB_PORT
    uvicorn.run("web.app:app", host=WEB_HOST, port=WEB_PORT, reload=True)
