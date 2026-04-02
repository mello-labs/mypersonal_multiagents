# =============================================================================
# agents/notion_sync.py — Agente de sincronização com o Notion
# =============================================================================
# Usa a Notion REST API diretamente (requests + token).
# Responsável por criar/atualizar páginas nos databases "Tarefas" e "Agenda Diária".
#
# Databases esperados no Notion:
#   Tarefas:
#     - Nome          (title)
#     - Status        (select): "A fazer" | "Em progresso" | "Concluído"
#     - Prioridade    (select): "Alta" | "Média" | "Baixa"
#     - Horário previsto (rich_text)
#     - Horário real     (rich_text)
#
#   Agenda Diária:
#     - Data          (date)
#     - Bloco horário (rich_text)
#     - Tarefa vinculada (relation → Tarefas)
#     - Concluído     (checkbox)

import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    NOTION_AGENDA_DB_ID,
    NOTION_API_BASE,
    NOTION_API_VERSION,
    NOTION_TASKS_DB_ID,
    NOTION_TOKEN,
)
from core import memory, notifier

AGENT_NAME = "notion_sync"


# ---------------------------------------------------------------------------
# Cliente HTTP base
# ---------------------------------------------------------------------------


def _headers() -> dict:
    """Retorna os headers padrão para chamadas à Notion API."""
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


class _NotionRateLimitError(RuntimeError):
    """Levantada em 429 ou 5xx — elegível para retry automático."""


@retry(
    retry=retry_if_exception_type(_NotionRateLimitError),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _request(method: str, endpoint: str, data: Optional[dict] = None) -> dict:
    """
    Faz uma requisição à Notion API.
    Faz retry automático em 429 (rate limit) e 5xx com backoff exponencial (1s→2s→4s→30s).
    Levanta RuntimeError em caso de falha não-recuperável.
    """
    url = f"{NOTION_API_BASE}/{endpoint.lstrip('/')}"
    response = requests.request(method, url, headers=_headers(), json=data, timeout=15)

    if response.status_code == 429 or response.status_code >= 500:
        raise _NotionRateLimitError(
            f"Notion API erro {response.status_code} em {method} {endpoint}: {response.text[:200]}"
        )

    if not response.ok:
        raise RuntimeError(
            f"Notion API erro {response.status_code} em {method} {endpoint}: {response.text[:500]}"
        )

    return response.json()


# ---------------------------------------------------------------------------
# Helpers para construir propriedades Notion
# ---------------------------------------------------------------------------


def _prop_title(text: str) -> dict:
    return {"title": [{"text": {"content": text}}]}


def _prop_select(value: str) -> dict:
    return {"select": {"name": value}}


def _prop_rich_text(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text}}]}


def _prop_date(date_str: str) -> dict:
    """date_str pode ser YYYY-MM-DD ou ISO datetime."""
    return {"date": {"start": date_str}}


def _prop_checkbox(checked: bool) -> dict:
    return {"checkbox": checked}


def _prop_relation(page_id: str) -> dict:
    return {"relation": [{"id": page_id}]}


# ---------------------------------------------------------------------------
# Operações em Tarefas
# ---------------------------------------------------------------------------


def create_notion_task(
    title: str,
    status: str = "A fazer",
    priority: str = "Média",
    scheduled_time: Optional[str] = None,
    actual_time: Optional[str] = None,
) -> str:
    """
    Cria uma nova página no database Tarefas do Notion.
    Retorna o ID da página criada.
    """
    if not NOTION_TOKEN or not NOTION_TASKS_DB_ID:
        notifier.warning(
            "Notion não configurado — tarefa não sincronizada.", AGENT_NAME
        )
        return ""

    properties: dict[str, Any] = {
        "Nome": _prop_title(title),
        "Status": _prop_select(status),
        "Prioridade": _prop_select(priority),
    }
    if scheduled_time:
        properties["Horário previsto"] = _prop_rich_text(scheduled_time)
    if actual_time:
        properties["Horário real"] = _prop_rich_text(actual_time)

    payload = {
        "parent": {"database_id": NOTION_TASKS_DB_ID},
        "properties": properties,
    }

    result = _request("POST", "pages", payload)
    page_id = result["id"]
    notifier.success(
        f"Tarefa criada no Notion: '{title}' (ID: {page_id[:8]}...)", AGENT_NAME
    )
    return page_id


def update_notion_task_status(
    notion_page_id: str,
    status: str,
    actual_time: Optional[str] = None,
) -> None:
    """Atualiza o status (e horário real) de uma tarefa no Notion."""
    if not NOTION_TOKEN or not notion_page_id:
        return

    properties: dict[str, Any] = {"Status": _prop_select(status)}
    if actual_time:
        properties["Horário real"] = _prop_rich_text(actual_time)

    _request("PATCH", f"pages/{notion_page_id}", {"properties": properties})
    notifier.info(
        f"Status atualizado no Notion → {status} (página {notion_page_id[:8]}...)",
        AGENT_NAME,
    )


def fetch_notion_tasks(filter_status: Optional[str] = None) -> list[dict]:
    """
    Lê todas as tarefas do Notion (com filtro opcional por status).
    Retorna lista de dicts com campos normalizados.
    """
    if not NOTION_TOKEN or not NOTION_TASKS_DB_ID:
        notifier.warning(
            "Notion não configurado — leitura de tarefas impossível.", AGENT_NAME
        )
        return []

    payload: dict[str, Any] = {"page_size": 100}
    if filter_status:
        payload["filter"] = {
            "property": "Status",
            "select": {"equals": filter_status},
        }

    result = _request("POST", f"databases/{NOTION_TASKS_DB_ID}/query", payload)
    tasks = []
    for page in result.get("results", []):
        props = page.get("properties", {})
        task = {
            "notion_page_id": page["id"],
            "title": _extract_title(props.get("Nome")),
            "status": _extract_select(props.get("Status")),
            "priority": _extract_select(props.get("Prioridade")),
            "scheduled_time": _extract_rich_text(props.get("Horário previsto")),
            "actual_time": _extract_rich_text(props.get("Horário real")),
        }
        tasks.append(task)

    notifier.info(f"Lidas {len(tasks)} tarefas do Notion.", AGENT_NAME)
    return tasks


# ---------------------------------------------------------------------------
# Operações na Agenda Diária
# ---------------------------------------------------------------------------


def create_notion_agenda_block(
    block_date: str,
    time_slot: str,
    task_title: str,
    notion_task_page_id: Optional[str] = None,
    completed: bool = False,
) -> str:
    """
    Cria um bloco na Agenda Diária do Notion.
    Retorna o ID da página criada.
    """
    if not NOTION_TOKEN or not NOTION_AGENDA_DB_ID:
        notifier.warning(
            "Notion não configurado — bloco de agenda não criado.", AGENT_NAME
        )
        return ""

    properties: dict[str, Any] = {
        "Data": _prop_date(block_date),
        "Bloco horário": _prop_rich_text(f"{time_slot} — {task_title}"),
        "Concluído": _prop_checkbox(completed),
    }

    # Se temos o ID da tarefa no Notion, criamos a relação
    if notion_task_page_id:
        properties["Tarefa vinculada"] = _prop_relation(notion_task_page_id)

    payload = {
        "parent": {"database_id": NOTION_AGENDA_DB_ID},
        "properties": properties,
    }

    result = _request("POST", "pages", payload)
    page_id = result["id"]
    notifier.success(
        f"Bloco de agenda criado: {block_date} {time_slot} → '{task_title}'", AGENT_NAME
    )
    return page_id


def mark_notion_agenda_block_done(notion_page_id: str, completed: bool = True) -> None:
    """Marca um bloco de agenda como concluído no Notion."""
    if not NOTION_TOKEN or not notion_page_id:
        return
    _request(
        "PATCH",
        f"pages/{notion_page_id}",
        {"properties": {"Concluído": _prop_checkbox(completed)}},
    )
    notifier.info(
        f"Bloco de agenda {'concluído' if completed else 'reaberto'} no Notion.",
        AGENT_NAME,
    )


def fetch_today_agenda_from_notion() -> list[dict]:
    """Lê os blocos de hoje da Agenda Diária no Notion."""
    today = date.today().isoformat()
    return fetch_agenda_range_from_notion(today, today)


def fetch_agenda_range_from_notion(start_date: str, end_date: str) -> list[dict]:
    """Lê blocos da Agenda Diária do Notion em um intervalo de datas."""
    if not NOTION_TOKEN or not NOTION_AGENDA_DB_ID:
        return []

    start_dt, end_dt = _normalize_date_range(start_date, end_date)
    payload = {
        "page_size": 100,
        "filter": {
            "and": [
                {"property": "Data", "date": {"on_or_after": start_dt}},
                {"property": "Data", "date": {"on_or_before": end_dt}},
            ]
        },
        "sorts": [
            {"property": "Data", "direction": "ascending"},
            {"property": "Bloco horário", "direction": "ascending"},
        ],
    }

    result = _request("POST", f"databases/{NOTION_AGENDA_DB_ID}/query", payload)
    blocks = []
    for page in result.get("results", []):
        props = page.get("properties", {})
        block_text = _extract_rich_text(props.get("Bloco horário"))
        time_slot, task_title = _split_agenda_block_text(block_text)
        blocks.append(
            {
                "notion_page_id": page["id"],
                "date": _extract_date(props.get("Data")),
                "time_slot": time_slot,
                "task_title": task_title,
                "completed": _extract_checkbox(props.get("Concluído")),
                "raw_block": block_text,
            }
        )

    return blocks


# ---------------------------------------------------------------------------
# Sincronização bidirecional
# ---------------------------------------------------------------------------


def sync_tasks_to_local() -> int:
    """
    Puxa tarefas do Notion e insere/atualiza no banco local.
    Retorna quantas tarefas foram sincronizadas.
    """
    notion_tasks = fetch_notion_tasks()
    count = 0
    for nt in notion_tasks:
        # Verifica se já existe localmente pela page_id
        existing = None
        all_local = memory.list_all_tasks()
        for lt in all_local:
            if lt.get("notion_page_id") == nt["notion_page_id"]:
                existing = lt
                break

        if not existing:
            task_id = memory.create_task(
                title=nt["title"] or "Sem título",
                priority=nt["priority"] or "Média",
                scheduled_time=nt["scheduled_time"],
                notion_page_id=nt["notion_page_id"],
            )
            if nt["status"]:
                memory.update_task_status(task_id, nt["status"])
            count += 1
            _maybe_create_agenda_block(task_id, nt)
        else:
            memory.update_task(
                existing["id"],
                title=nt["title"] or existing.get("title") or "Sem título",
                priority=nt["priority"] or existing.get("priority") or "Média",
                scheduled_time=nt.get("scheduled_time"),
                actual_time=nt.get("actual_time"),
                notion_page_id=nt.get("notion_page_id") or existing.get("notion_page_id"),
            )
            if nt.get("status"):
                memory.update_task_status(
                    existing["id"],
                    nt["status"],
                    nt.get("actual_time") or None,
                )
            # Tarefa já existe — garante bloco de agenda se tiver horário
            _maybe_create_agenda_block(existing["id"], nt)

    notifier.success(
        f"Sincronização concluída: {count} tarefa(s) nova(s) importadas.", AGENT_NAME
    )
    return count


def _maybe_create_agenda_block(task_id: int, nt: dict) -> None:
    """Cria bloco de agenda hoje para tarefa com scheduled_time, sem duplicar."""
    from datetime import date as _date

    scheduled_time = (nt.get("scheduled_time") or "").strip()
    status = nt.get("status") or "A fazer"
    if not scheduled_time or status == "Concluído":
        return

    today = _date.today().isoformat()
    # Evita duplicata: verifica se já existe bloco com esse task_id hoje
    existing_blocks = memory.get_today_agenda()
    for b in existing_blocks:
        if str(b.get("task_id")) == str(task_id):
            return  # Já tem bloco para essa tarefa hoje

    # Normaliza o horário para "HH:MM-HH:MM"
    time_slot = _normalize_time_slot(scheduled_time)

    memory.create_agenda_block(
        block_date=today,
        time_slot=time_slot,
        task_title=nt.get("title") or "Sem título",
        task_id=task_id,
        notion_page_id=nt.get("notion_page_id"),
    )


def sync_agenda_range_to_local(start_date: str, end_date: str) -> int:
    """Importa blocos da Agenda Diária do Notion para o banco local."""
    blocks = fetch_agenda_range_from_notion(start_date, end_date)
    if not blocks:
        return 0

    local_blocks = memory.list_agenda_between(
        start_date, end_date, include_rescheduled=True
    )
    existing_keys = {
        (
            block.get("block_date"),
            block.get("time_slot"),
            (block.get("task_title") or "").strip().lower(),
        )
        for block in local_blocks
    }

    created = 0
    for block in blocks:
        block_date = block.get("date") or start_date
        task_title = block.get("task_title") or "Sem título"
        key = (block_date, block.get("time_slot"), task_title.strip().lower())
        if not block.get("time_slot") or key in existing_keys:
            continue

        memory.create_agenda_block(
            block_date=block_date,
            time_slot=block["time_slot"],
            task_title=task_title,
            notion_page_id=block.get("notion_page_id"),
        )
        existing_keys.add(key)
        created += 1

    if created:
        notifier.success(
            f"Agenda Notion: {created} bloco(s) importado(s) entre {start_date} e {end_date}.",
            AGENT_NAME,
        )
    return created


def sync_local_task_to_notion(task_id: int) -> Optional[str]:
    """
    Envia uma tarefa local para o Notion (cria ou atualiza).
    Retorna o notion_page_id.
    """
    task = memory.get_task(task_id)
    if not task:
        notifier.error(f"Tarefa {task_id} não encontrada.", AGENT_NAME)
        return None

    if task.get("notion_page_id"):
        # Atualiza
        update_notion_task_status(
            task["notion_page_id"],
            task["status"],
            task.get("actual_time"),
        )
        return task["notion_page_id"]
    else:
        # Cria
        page_id = create_notion_task(
            title=task["title"],
            status=task["status"],
            priority=task["priority"],
            scheduled_time=task.get("scheduled_time"),
            actual_time=task.get("actual_time"),
        )
        if page_id:
            memory.update_task_notion_id(task_id, page_id)
        return page_id


# ---------------------------------------------------------------------------
# Helpers de extração de propriedades Notion
# ---------------------------------------------------------------------------


def _extract_title(prop: Optional[dict]) -> str:
    if not prop:
        return ""
    items = prop.get("title", [])
    return "".join(t.get("plain_text", "") for t in items)


def _extract_select(prop: Optional[dict]) -> str:
    if not prop:
        return ""
    sel = prop.get("select")
    return sel.get("name", "") if sel else ""


def _extract_rich_text(prop: Optional[dict]) -> str:
    if not prop:
        return ""
    items = prop.get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in items)


def _extract_date(prop: Optional[dict]) -> str:
    if not prop:
        return ""
    d = prop.get("date")
    return d.get("start", "") if d else ""


def _extract_checkbox(prop: Optional[dict]) -> bool:
    if not prop:
        return False
    return bool(prop.get("checkbox", False))


def _normalize_time_slot(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if "-" in raw:
        start_str, end_str = [part.strip() for part in raw.split("-", 1)]
        return f"{start_str}-{end_str}"
    try:
        start_dt = datetime.strptime(raw, "%H:%M")
        end_dt = start_dt + timedelta(hours=1)
        return f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
    except ValueError:
        return raw


def _split_agenda_block_text(raw_text: str) -> tuple[str, str]:
    if "—" in raw_text:
        left, right = raw_text.split("—", 1)
        return left.strip(), right.strip() or "Sem título"
    return raw_text.strip(), "Sem título"


def _normalize_date_range(start_date: str, end_date: str) -> tuple[str, str]:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt
    return start_dt.isoformat(), end_dt.isoformat()


# ---------------------------------------------------------------------------
# Sincronização diferencial
# ---------------------------------------------------------------------------


def fetch_tasks_modified_since(last_sync_iso: str) -> list[dict]:
    """Puxa apenas tarefas modificadas após last_sync_iso (polling diferencial)."""
    if not NOTION_TOKEN or not NOTION_TASKS_DB_ID:
        return []

    payload: dict[str, Any] = {
        "page_size": 100,
        "filter": {
            "timestamp": "last_edited_time",
            "last_edited_time": {"after": last_sync_iso},
        },
    }

    result = _request("POST", f"databases/{NOTION_TASKS_DB_ID}/query", payload)
    tasks = []
    for page in result.get("results", []):
        props = page.get("properties", {})
        task = {
            "notion_page_id": page["id"],
            "title": _extract_title(props.get("Nome")),
            "status": _extract_select(props.get("Status")),
            "priority": _extract_select(props.get("Prioridade")),
            "scheduled_time": _extract_rich_text(props.get("Horário previsto")),
            "actual_time": _extract_rich_text(props.get("Horário real")),
            "last_edited_time": page.get("last_edited_time", ""),
        }
        tasks.append(task)

    notifier.info(
        f"Sync diferencial: {len(tasks)} tarefa(s) modificada(s) desde {last_sync_iso[:16]}.",
        AGENT_NAME,
    )
    return tasks


def sync_differential() -> int:
    """
    Sincronização diferencial: importa do Notion apenas o que mudou desde
    o último sync. Guarda/lê o timestamp em system_state['notion_last_sync_ts'].
    Retorna número de tarefas criadas/atualizadas.
    """
    last_sync = memory.get_state("notion_last_sync_ts")

    if not last_sync:
        notifier.info("Primeira sync — executando full sync.", AGENT_NAME)
        count = sync_tasks_to_local()
    else:
        modified = fetch_tasks_modified_since(last_sync)
        count = 0
        all_local = memory.list_all_tasks()
        local_by_notion_id = {
            lt["notion_page_id"]: lt for lt in all_local if lt.get("notion_page_id")
        }

        for nt in modified:
            existing = local_by_notion_id.get(nt["notion_page_id"])
            if existing:
                if nt["status"] and existing["status"] != nt["status"]:
                    memory.update_task_status(existing["id"], nt["status"])
                    count += 1
                _maybe_create_agenda_block(existing["id"], nt)
            else:
                task_id = memory.create_task(
                    title=nt["title"] or "Sem título",
                    priority=nt["priority"] or "Média",
                    scheduled_time=nt["scheduled_time"],
                    notion_page_id=nt["notion_page_id"],
                )
                if nt["status"]:
                    memory.update_task_status(task_id, nt["status"])
                count += 1
                _maybe_create_agenda_block(task_id, nt)

    memory.set_state("notion_last_sync_ts", datetime.now().isoformat())
    if count:
        notifier.success(
            f"Sync diferencial: {count} tarefa(s) processada(s).", AGENT_NAME
        )
    return count


# ---------------------------------------------------------------------------
# Handoff entry point — chamado pelo Orchestrator
# ---------------------------------------------------------------------------


class HandoffPayload:
    """Estrutura de handoff padronizada para este agente."""

    @staticmethod
    def create_task(
        title: str, priority: str = "Média", scheduled_time: str = ""
    ) -> dict:
        return {
            "action": "create_task",
            "title": title,
            "priority": priority,
            "scheduled_time": scheduled_time,
        }

    @staticmethod
    def update_status(task_id: int, status: str) -> dict:
        return {"action": "update_status", "task_id": task_id, "status": status}

    @staticmethod
    def sync_from_notion() -> dict:
        return {"action": "sync_from_notion"}

    @staticmethod
    def get_today_agenda() -> dict:
        return {"action": "get_today_agenda"}


def handle_handoff(payload: dict) -> dict:
    """
    Ponto de entrada para handoffs do Orchestrator.
    Retorna dict com 'status' e 'result'.
    """
    action = payload.get("action", "")
    notifier.agent_event(f"Recebendo handoff: action='{action}'", AGENT_NAME)

    handoff_id = memory.log_handoff("orchestrator", AGENT_NAME, action, payload)

    try:
        result = {}

        if action == "create_task":
            page_id = create_notion_task(
                title=payload["title"],
                priority=payload.get("priority", "Média"),
                scheduled_time=payload.get("scheduled_time", ""),
            )
            result = {
                "notion_page_id": page_id,
                "message": f"Tarefa '{payload['title']}' criada.",
            }

        elif action == "update_status":
            task = memory.get_task(payload["task_id"])
            if task and task.get("notion_page_id"):
                update_notion_task_status(task["notion_page_id"], payload["status"])
            result = {"message": f"Status atualizado para '{payload['status']}'."}

        elif action == "sync_from_notion":
            count = sync_tasks_to_local()
            result = {"synced": count, "message": f"{count} tarefa(s) importada(s)."}

        elif action == "get_today_agenda":
            blocks = fetch_today_agenda_from_notion()
            local_blocks = memory.get_today_agenda()
            result = {
                "notion_blocks": blocks,
                "local_blocks": local_blocks,
                "total": len(blocks) or len(local_blocks),
            }

        elif action == "sync_agenda_range":
            start_date, end_date = _normalize_date_range(
                payload["start_date"],
                payload["end_date"],
            )
            count = sync_agenda_range_to_local(start_date, end_date)
            result = {
                "synced": count,
                "message": f"{count} bloco(s) de agenda importado(s).",
                "start_date": start_date,
                "end_date": end_date,
            }

        elif action == "sync_differential":
            count = sync_differential()
            result = {
                "synced": count,
                "message": f"{count} tarefa(s) atualizada(s) pelo sync diferencial.",
            }

        else:
            raise ValueError(f"Ação desconhecida: '{action}'")

        memory.update_handoff_result(handoff_id, result, "success")
        return {"status": "success", "result": result}

    except Exception as exc:
        error_msg = str(exc)
        notifier.error(f"Erro no handoff '{action}': {error_msg}", AGENT_NAME)
        memory.update_handoff_result(handoff_id, {"error": error_msg}, "error")
        return {"status": "error", "result": {"error": error_msg}}
