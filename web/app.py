# =============================================================================
# web/app.py — Interface Web (FastAPI + HTMX + Jinja2)
# =============================================================================
# Expõe o Orchestrator via HTTP com UI minimalista dark-mode.
# O Focus Guard roda em background thread via lifespan.
#
# Iniciar:  python -m web.app
#           uvicorn web.app:app --reload --port 8000

import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from agents import orchestrator, focus_guard
from agents import notion_sync
from core import memory, notifier

BASE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Lifespan: inicia/para Focus Guard junto com o servidor
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    memory.init_db()
    if not focus_guard.is_running():
        focus_guard.start_guard()
    yield
    focus_guard.stop_guard()


app = FastAPI(title="Multiagentes", lifespan=lifespan)
# Starlette 0.36+ usa request como primeiro argumento em TemplateResponse
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _summary_ctx() -> dict:
    return {"summary": orchestrator.get_system_summary()}


# ---------------------------------------------------------------------------
# Rotas principais
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    ctx = _summary_ctx()
    ctx["agenda"] = memory.get_today_agenda()
    ctx["tasks"] = memory.list_all_tasks()
    return templates.TemplateResponse(request, "index.html", ctx)


@app.post("/chat", response_class=HTMLResponse)
async def chat(request: Request, message: str = Form(...)):
    response = orchestrator.process(message)
    return templates.TemplateResponse(
        request,
        "partials/chat_message.html",
        {"user_message": message, "bot_response": response},
    )


@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    return templates.TemplateResponse(
        request, "partials/status.html", _summary_ctx()
    )


@app.get("/agenda", response_class=HTMLResponse)
async def agenda(request: Request):
    return templates.TemplateResponse(
        request, "partials/agenda.html", {"blocks": memory.get_today_agenda()}
    )


@app.get("/tasks", response_class=HTMLResponse)
async def tasks(request: Request):
    return templates.TemplateResponse(
        request, "partials/tasks.html", {"tasks": memory.list_all_tasks()}
    )


@app.post("/task", response_class=HTMLResponse)
async def create_task(
    request: Request,
    title: str = Form(...),
    priority: str = Form("Média"),
    scheduled_time: str = Form(""),
):
    memory.create_task(
        title=title,
        priority=priority,
        scheduled_time=scheduled_time or None,
    )
    return templates.TemplateResponse(
        request, "partials/tasks.html", {"tasks": memory.list_all_tasks()}
    )


@app.post("/task/{task_id}/complete", response_class=HTMLResponse)
async def complete_task(request: Request, task_id: int):
    memory.update_task_status(task_id, "Concluído")
    return templates.TemplateResponse(
        request, "partials/tasks.html", {"tasks": memory.list_all_tasks()}
    )


@app.post("/sync", response_class=HTMLResponse)
async def sync(request: Request):
    count = notion_sync.sync_differential()
    ctx = _summary_ctx()
    ctx["sync_msg"] = f"{count} tarefa(s) sincronizada(s)."
    return templates.TemplateResponse(request, "partials/status.html", ctx)


@app.post("/block/{block_id}/complete", response_class=HTMLResponse)
async def complete_block(request: Request, block_id: int):
    memory.mark_block_completed(block_id, True)
    return templates.TemplateResponse(
        request, "partials/agenda.html", {"blocks": memory.get_today_agenda()}
    )


# ---------------------------------------------------------------------------
# Entry point direto
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    from config import WEB_HOST, WEB_PORT
    uvicorn.run("web.app:app", host=WEB_HOST, port=WEB_PORT, reload=True)
