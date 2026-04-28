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

import re
import hashlib
from datetime import date, datetime, timedelta
from typing import Any, Optional

from adapters.notion import request as _request
from config import (
    NOTION_AGENDA_DB_ID,
    NOTION_TASKS_DB_ID,
    NOTION_TOKEN,
)
from core import memory, notifier

AGENT_NAME = "notion_sync"

# ---------------------------------------------------------------------------
# Nomes das colunas nos databases do Notion
# (altere aqui se renomear no Notion)
# ---------------------------------------------------------------------------

# DB "Tarefas"
_TASK_NAME_FIELD = "Nome"
_TASK_STATUS_FIELD = "Status"
_TASK_PRIORITY_FIELD = "Prioridade"
_TASK_SCHEDULED_FIELD = "Horário previsto"   # tipo: date
_TASK_ACTUAL_FIELD = "Horário real"           # tipo: rich_text

# DB "Agenda" (antigo "Agenda Diária")
_AGENDA_NAME_FIELD = "Name"            # título da página (title)
_AGENDA_DATE_FIELD = "Data de entrega" # data de entrega (date)
_AGENDA_RELATION_FIELD = "Tarefa vinculada"  # relation → Tarefas
_AGENDA_DONE_FIELD = "Concluído"       # checkbox


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
        date_prop = _prop_scheduled_time(scheduled_time)
        if date_prop is not None:
            properties["Horário previsto"] = date_prop
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
            "scheduled_time": _extract_scheduled_time(props.get("Horário previsto")),
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
    task_title: str,
    notion_task_page_id: Optional[str] = None,
    completed: bool = False,
    time_slot: str = "",  # mantido por retrocompat, não enviado ao Notion
) -> str:
    """
    Cria um bloco no DB de Agenda do Notion usando o schema atual:
      - Name            (title)  — nome do bloco
      - Data de entrega (date)   — data alvo
      - Tarefa vinculada(relation)
      - Concluído       (checkbox)
    Retorna o ID da página criada.
    """
    if not NOTION_TOKEN or not NOTION_AGENDA_DB_ID:
        notifier.warning(
            "Notion não configurado — bloco de agenda não criado.", AGENT_NAME
        )
        return ""

    properties: dict[str, Any] = {
        _AGENDA_NAME_FIELD: _prop_title(task_title),
        _AGENDA_DATE_FIELD: _prop_date(block_date),
        _AGENDA_DONE_FIELD: _prop_checkbox(completed),
    }

    if notion_task_page_id:
        properties[_AGENDA_RELATION_FIELD] = _prop_relation(notion_task_page_id)

    payload = {
        "parent": {"database_id": NOTION_AGENDA_DB_ID},
        "properties": properties,
    }

    result = _request("POST", "pages", payload)
    page_id = result["id"]
    notifier.success(
        f"Bloco de agenda criado: {block_date} → '{task_title}'", AGENT_NAME
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
    """
    Lê blocos da Agenda do Notion em um intervalo de datas.
    Schema atual do DB:
      - Name            (title) → task_title
      - Data de entrega (date)  → date (YYYY-MM-DD)
      - Tarefa vinculada(relation)
      - Concluído       (checkbox)
    Sem time_slot — agenda orientada a data de entrega.
    """
    if not NOTION_TOKEN or not NOTION_AGENDA_DB_ID:
        return []

    start_dt, end_dt = _normalize_date_range(start_date, end_date)
    payload = {
        "page_size": 100,
        "filter": {
            "and": [
                {"property": _AGENDA_DATE_FIELD, "date": {"on_or_after": start_dt}},
                {"property": _AGENDA_DATE_FIELD, "date": {"on_or_before": end_dt}},
            ]
        },
        "sorts": [
            {"property": _AGENDA_DATE_FIELD, "direction": "ascending"},
        ],
    }

    result = _request("POST", f"databases/{NOTION_AGENDA_DB_ID}/query", payload)
    blocks = []
    for page in result.get("results", []):
        props = page.get("properties", {})
        # Título vem do campo Name (title da página)
        task_title = _extract_title(
            props.get(_AGENDA_NAME_FIELD) or props.get("Nome")
        ) or "Sem título"
        blocks.append(
            {
                "notion_page_id": page["id"],
                "date": _extract_date(props.get(_AGENDA_DATE_FIELD)),
                "time_slot": "",        # agenda date-only, sem horário fixo
                "task_title": task_title,
                "completed": _extract_checkbox(props.get(_AGENDA_DONE_FIELD)),
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
                notion_page_id=nt.get("notion_page_id")
                or existing.get("notion_page_id"),
            )
            if nt.get("status"):
                memory.update_task_status(
                    existing["id"],
                    nt["status"],
                    nt.get("actual_time") or None,
                )
            # Tarefa já existe — garante bloco de agenda se tiver horário
            _maybe_create_agenda_block(existing["id"], nt)

    # Reconciliação: remove do Redis tarefas que já não existem no Notion
    notion_ids = {
        nt["notion_page_id"] for nt in notion_tasks if nt.get("notion_page_id")
    }
    removed = 0
    for lt in memory.list_all_tasks():
        local_notion_id = lt.get("notion_page_id") or ""
        title = lt.get("title") or ""
        # Caso 1: tem notion_page_id mas sumiu do Notion → órfã real
        orphan = local_notion_id and local_notion_id not in notion_ids
        # Caso 2: notion_page_id vazio + título sentinela → foi criada com título vazio no Notion
        sentinel = not local_notion_id and title in ("Sem título", "")
        if orphan or sentinel:
            memory.delete_task(lt["id"])
            removed += 1
            reason = (
                "não existe mais no Notion"
                if orphan
                else "notion_page_id vazio e título inválido"
            )
            notifier.info(
                f"Tarefa removida do Redis ({reason}): id={lt['id']} title='{title}'",
                AGENT_NAME,
            )

    notifier.success(
        f"Sincronização concluída: {count} nova(s), {removed} removida(s).", AGENT_NAME
    )
    return count


def _split_scheduled_time(scheduled_time: str) -> tuple[str, str]:
    """
    Quebra um scheduled_time em (block_date, hhmm).
    Aceita:
      - "HH:MM"            → (hoje, "HH:MM")
      - "YYYY-MM-DD"       → (essa data, "")
      - "YYYY-MM-DD HH:MM" → (essa data, "HH:MM")
      - ISO datetime       → (data, "HH:MM")
    Retorna ("", "") se não conseguir parsear nada útil.
    """
    raw = (scheduled_time or "").strip()
    if not raw:
        return "", ""

    # Procura HH:MM em qualquer lugar
    hhmm_match = _HHMM_RE.search(raw)
    hhmm = ""
    if hhmm_match:
        h, m = hhmm_match.groups()
        try:
            hhmm = datetime.strptime(f"{int(h):02d}:{m}", "%H:%M").strftime("%H:%M")
        except ValueError:
            hhmm = ""

    # Procura YYYY-MM-DD
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    block_date = ""
    if date_match:
        try:
            block_date = (
                datetime.strptime(date_match.group(0), "%Y-%m-%d").date().isoformat()
            )
        except ValueError:
            block_date = ""

    # Sem data explícita mas com hora → assume hoje
    if hhmm and not block_date:
        block_date = date.today().isoformat()

    return block_date, hhmm


def _maybe_create_agenda_block(task_id: int, nt: dict) -> None:
    """
    Cria bloco de agenda para uma tarefa com scheduled_time, respeitando a data
    real da tarefa. Pula a criação se:
      - scheduled_time está vazio
      - status é Concluído
      - scheduled_time só tem data (sem HH:MM) — usuário precisa decidir o horário
      - já existe bloco para essa task_id na data alvo
    """
    scheduled_time = (nt.get("scheduled_time") or "").strip()
    status = nt.get("status") or "A fazer"
    if not scheduled_time or status == "Concluído":
        return

    block_date, hhmm = _split_scheduled_time(scheduled_time)

    # Sem hora real, não vira bloco automático — o scheduled_time fica armazenado
    # na tarefa, mas não criamos um bloco de agenda mal-formado.
    if not hhmm:
        notifier.info(
            f"Tarefa {task_id} tem só data ({scheduled_time}) — bloco automático "
            "não criado. Defina um horário no Notion ou crie o bloco manualmente.",
            AGENT_NAME,
        )
        return

    if not block_date:
        block_date = date.today().isoformat()

    # Evita duplicata: verifica se já existe bloco com esse task_id na data alvo
    existing_blocks = memory.get_agenda_for_date(block_date, include_rescheduled=True)
    for b in existing_blocks:
        if str(b.get("task_id")) == str(task_id):
            return

    time_slot = _normalize_time_slot(hhmm)

    memory.create_agenda_block(
        block_date=block_date,
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
    existing_notion_ids = {
        str(block.get("notion_page_id"))
        for block in local_blocks
        if block.get("notion_page_id")
    }
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
        notion_page_id = str(block.get("notion_page_id") or "")
        if notion_page_id and notion_page_id in existing_notion_ids:
            continue

        block_date = block.get("date") or start_date
        task_title = block.get("task_title") or "Sem título"
        time_slot = block.get("time_slot") or ""
        if not time_slot:
            time_slot = _synthetic_time_slot_for_date_only(
                notion_page_id=notion_page_id,
                task_title=task_title,
                block_date=block_date,
                used_keys=existing_keys,
            )

        key = (block_date, time_slot, task_title.strip().lower())
        if key in existing_keys:
            continue

        memory.create_agenda_block(
            block_date=block_date,
            time_slot=time_slot,
            task_title=task_title,
            notion_page_id=notion_page_id or None,
        )
        existing_keys.add(key)
        if notion_page_id:
            existing_notion_ids.add(notion_page_id)
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


# ---------------------------------------------------------------------------
# Horário previsto — aceita 'date' (atual) e 'rich_text' (legacy)
# ---------------------------------------------------------------------------


def _extract_scheduled_time(prop: Optional[dict]) -> str:
    """
    Lê 'Horário previsto' do Notion aceitando tanto o tipo 'date' (atual)
    quanto 'rich_text' (schemas antigos).
      - date:      retorna "YYYY-MM-DD HH:MM" ou "YYYY-MM-DD"
      - rich_text: retorna o texto bruto (comportamento antigo)
    """
    if not prop:
        return ""
    ptype = prop.get("type")

    # Caminho explícito por tipo declarado na resposta da API
    if ptype == "date":
        d = prop.get("date")
        if not d:
            return ""
        start = d.get("start", "")
        if not start:
            return ""
        if "T" in start:
            try:
                dt = datetime.fromisoformat(start)
                return dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                return start[:16].replace("T", " ")
        return start

    if ptype == "rich_text":
        return _extract_rich_text(prop)

    # Fallback para mocks de teste (sem 'type'): detecta pelo conteúdo
    if "date" in prop and prop.get("date"):
        return _extract_scheduled_time({"type": "date", **prop})
    if "rich_text" in prop:
        return _extract_rich_text(prop)
    return ""


def _prop_scheduled_time(scheduled_time: str) -> Optional[dict]:
    """
    Constrói a propriedade Notion 'Horário previsto' como tipo 'date'.
    Aceita várias strings locais:
      - "HH:MM"            → hoje + hora
      - "YYYY-MM-DD"       → só data
      - "YYYY-MM-DD HH:MM" → data + hora
      - ISO datetime       → parseado
    Retorna None para entrada vazia (chamador decide se omite a prop).
    """
    raw = (scheduled_time or "").strip()
    if not raw:
        return None

    # Só "HH:MM" → assume hoje
    if len(raw) == 5 and raw[2:3] == ":":
        try:
            datetime.strptime(raw, "%H:%M")
            raw = f"{date.today().isoformat()} {raw}"
        except ValueError:
            pass

    for fmt in (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            if fmt == "%Y-%m-%d":
                return {"date": {"start": dt.date().isoformat()}}
            return {"date": {"start": dt.strftime("%Y-%m-%dT%H:%M:%S")}}
        except ValueError:
            continue

    # Último recurso: ISO com timezone ou similar
    try:
        dt = datetime.fromisoformat(raw)
        return {"date": {"start": dt.strftime("%Y-%m-%dT%H:%M:%S")}}
    except ValueError:
        return {"date": {"start": raw}}


# ---------------------------------------------------------------------------
# Normalização de time_slot — tolerante a datetime completo
# ---------------------------------------------------------------------------


_HHMM_RE = re.compile(r"(\d{1,2}):(\d{2})")


def _normalize_time_slot(value: str) -> str:
    """
    Normaliza uma string de horário em 'HH:MM-HH:MM'.
    Aceita formatos amplos: 'HH:MM', 'HH:MM-HH:MM', 'YYYY-MM-DD HH:MM',
    ISO datetime etc. Extrai os HH:MM por regex, ignorando a parte de data —
    assim não se confunde com o '-' do 'YYYY-MM-DD'.
    """
    raw = (value or "").strip()
    if not raw:
        return ""

    matches = _HHMM_RE.findall(raw)

    def _fmt(h: str, m: str) -> Optional[str]:
        try:
            return datetime.strptime(f"{int(h):02d}:{m}", "%H:%M").strftime("%H:%M")
        except ValueError:
            return None

    if len(matches) >= 2:
        a = _fmt(*matches[0])
        b = _fmt(*matches[1])
        if a and b:
            return f"{a}-{b}"
    if len(matches) == 1:
        a = _fmt(*matches[0])
        if a:
            start_dt = datetime.strptime(a, "%H:%M")
            end_dt = start_dt + timedelta(hours=1)
            return f"{a}-{end_dt.strftime('%H:%M')}"
    return raw


def _synthetic_time_slot_for_date_only(
    notion_page_id: str,
    task_title: str,
    block_date: str,
    used_keys: set[tuple[str, str, str]],
) -> str:
    """
    Gera slot de 1h para blocos date-only da agenda do Notion.
    Determinístico por notion_page_id (ou data+título) e sem colisão local.
    """
    seed_src = (notion_page_id or f"{block_date}:{task_title}").encode("utf-8")
    digest = hashlib.sha1(seed_src).hexdigest()
    base = int(digest[:2], 16) % 12  # janela 08:00..19:00
    title_key = task_title.strip().lower()

    for offset in range(12):
        hour = 8 + ((base + offset) % 12)
        slot = f"{hour:02d}:00-{(hour + 1):02d}:00"
        if (block_date, slot, title_key) not in used_keys:
            return slot
    return "19:00-20:00"


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
            "scheduled_time": _extract_scheduled_time(props.get("Horário previsto")),
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
