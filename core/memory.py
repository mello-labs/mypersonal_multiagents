# =============================================================================
# core/memory.py — Estado compartilhado entre agentes via Redis
# =============================================================================
# Substitui o SQLite por Redis para persistência durável no Railway.
# Mantém a mesma API pública — nenhum outro módulo precisa mudar.
#
# Estrutura de chaves Redis:
#   task:{id}                  HASH com todos os campos da tarefa
#   tasks:all                  ZSET  scored por created_at (unix ts)
#   tasks:notion:{notion_id}   STRING → task_id
#   tasks:next_id              COUNTER
#
#   block:{id}                 HASH
#   blocks:date:{YYYY-MM-DD}   ZSET scored por minutos do time_slot
#   blocks:next_id             COUNTER
#
#   session:{id}               HASH
#   sessions:all               ZSET scored por started_at
#   session:active             STRING → session_id (se houver sessão ativa)
#   sessions:next_id           COUNTER
#
#   handoff:{id}               HASH
#   handoffs:all               ZSET scored por created_at
#   handoffs:next_id           COUNTER
#
#   state:{key}                STRING (JSON)
#
#   alert:{id}                 HASH
#   alerts:pending             ZSET scored por created_at
#   alerts:all                 ZSET scored por created_at
#   alerts:next_id             COUNTER
#
#   audit:{id}                 HASH
#   audit:events               ZSET scored por created_at
#   audit:next_id              COUNTER

import json
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import redis as redis_lib

from config import REDIS_URL

# ---------------------------------------------------------------------------
# Conexão singleton (lazy) com auto-start de redis-server local
# ---------------------------------------------------------------------------

_redis_client: Optional[redis_lib.Redis] = None
_lock = threading.Lock()

# Só tenta auto-start no macOS com URL local (nunca em container Railway/Docker)
_IS_LOCAL = any(h in REDIS_URL for h in ("localhost", "127.0.0.1"))
_IS_MACOS = sys.platform == "darwin"
_CAN_AUTOSTART = _IS_LOCAL and _IS_MACOS


def _start_local_redis() -> None:
    """Tenta iniciar redis-server local via brew (somente macOS)."""
    try:
        subprocess.Popen(
            ["redis-server", "--daemonize", "yes", "--loglevel", "warning"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.8)
    except FileNotFoundError:
        raise RuntimeError(
            "Redis não encontrado. Instale com:\n"
            "  brew install redis\n"
            "Ou suba via Docker:\n"
            "  make redis-up"
        )


def _r() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        client = redis_lib.from_url(
            REDIS_URL, decode_responses=True, socket_connect_timeout=2
        )
        try:
            client.ping()
            print(f"[Memory] Redis conectado: {REDIS_URL}")
        except (
            redis_lib.exceptions.ConnectionError,
            redis_lib.exceptions.TimeoutError,
        ):
            if _CAN_AUTOSTART:
                print("[Memory] Redis offline — tentando iniciar redis-server local...")
                _start_local_redis()
                client = redis_lib.from_url(REDIS_URL, decode_responses=True)
                client.ping()  # levanta exceção se ainda falhar
            else:
                raise redis_lib.exceptions.ConnectionError(
                    f"Não foi possível conectar ao Redis ({REDIS_URL}). "
                    "Verifique se REDIS_URL está configurado corretamente no Railway."
                )
        _redis_client = client
    return _redis_client


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _ts(dt_str: Optional[str] = None) -> float:
    """Converte string ISO para unix timestamp (score do ZSET)."""
    if dt_str is None:
        return datetime.now(timezone.utc).timestamp()
    try:
        return datetime.fromisoformat(dt_str).timestamp()
    except Exception:
        return datetime.now(timezone.utc).timestamp()


def _ts_from_timeslot(time_slot: str) -> float:
    """'09:00-10:00' → 540.0  (minutos desde meia-noite, para sort)."""
    try:
        t = time_slot.split("-")[0].strip()
        h, m = t.split(":")
        return float(int(h) * 60 + int(m))
    except Exception:
        return 0.0


def _next_id(counter_key: str) -> int:
    return _r().incr(counter_key)


def _to_dict(data: dict, int_fields: list[str] | None = None) -> dict:
    """Limpa strings vazias e converte campos numéricos."""
    result = {}
    for k, v in data.items():
        result[k] = v if v != "" else None
    if int_fields:
        for f in int_fields:
            if result.get(f) is not None:
                try:
                    result[f] = int(result[f])
                except (ValueError, TypeError):
                    pass
    return result


# =============================================================================
# INIT
# =============================================================================


def init_db() -> None:
    """Verifica conexão Redis. Substitui o init_db() do SQLite."""
    try:
        _r().ping()
        print(f"[Memory] Redis conectado: {REDIS_URL}")
    except Exception as e:
        print(
            f"[Memory] AVISO: Redis indisponível ({e}). Tentativas serão feitas sob demanda."
        )
        # Não levanta exceção — o app sobe; falha nas operações reais se Redis não estiver acessível


# =============================================================================
# TASKS
# =============================================================================


def create_task(
    title: str,
    priority: str = "Média",
    scheduled_time: Optional[str] = None,
    notes: Optional[str] = None,
    notion_page_id: Optional[str] = None,
) -> int:
    with _lock:
        task_id = _next_id("tasks:next_id")
        now = _now()
        data = {
            "id": str(task_id),
            "title": title,
            "priority": priority,
            "status": "A fazer",
            "scheduled_time": scheduled_time or "",
            "actual_time": "",
            "notes": notes or "",
            "notion_page_id": notion_page_id or "",
            "created_at": now,
            "updated_at": now,
        }
        r = _r()
        r.hset(f"task:{task_id}", mapping=data)
        r.zadd("tasks:all", {str(task_id): _ts(now)})
        if notion_page_id:
            r.set(f"tasks:notion:{notion_page_id}", task_id)
        return task_id


def update_task_status(
    task_id: int, status: str, actual_time: Optional[str] = None
) -> None:
    r = _r()
    key = f"task:{task_id}"
    r.hset(key, "status", status)
    r.hset(key, "updated_at", _now())
    if actual_time:
        r.hset(key, "actual_time", actual_time)


def update_task(task_id: int, **fields: Any) -> None:
    """Atualiza campos arbitrários de uma tarefa existente."""
    r = _r()
    mapping = {}
    notion_page_id = None
    old_notion_page_id = None
    task_key = f"task:{task_id}"

    if "notion_page_id" in fields:
        old_notion_page_id = r.hget(task_key, "notion_page_id")

    for key, value in fields.items():
        if key == "id":
            continue
        if key == "notion_page_id":
            notion_page_id = value
        if value is None:
            mapping[key] = ""
        else:
            mapping[key] = str(value)

    if not mapping:
        return

    mapping["updated_at"] = _now()
    r.hset(task_key, mapping=mapping)
    if "notion_page_id" in fields and old_notion_page_id:
        if old_notion_page_id != mapping.get("notion_page_id", ""):
            r.delete(f"tasks:notion:{old_notion_page_id}")
    if notion_page_id:
        r.set(f"tasks:notion:{notion_page_id}", task_id)
    elif "notion_page_id" in fields and old_notion_page_id:
        r.delete(f"tasks:notion:{old_notion_page_id}")


def get_task(task_id: int) -> Optional[dict]:
    data = _r().hgetall(f"task:{task_id}")
    if not data:
        return None
    data["id"] = int(task_id)
    return _to_dict(data, int_fields=["id"])


def get_tasks_by_status(status: str) -> list[dict]:
    r = _r()
    task_ids = r.zrange("tasks:all", 0, -1)
    tasks = []
    for tid in task_ids:
        data = r.hgetall(f"task:{tid}")
        if data and data.get("status") == status:
            data["id"] = int(tid)
            tasks.append(_to_dict(data, int_fields=["id"]))
    tasks.sort(key=lambda t: t.get("scheduled_time") or "")
    return tasks


def get_today_tasks() -> list[dict]:
    today = date.today().isoformat()
    return [
        t for t in list_all_tasks() if (t.get("scheduled_time") or "").startswith(today)
    ]


def list_all_tasks() -> list[dict]:
    r = _r()
    task_ids = r.zrevrange("tasks:all", 0, -1)  # mais recentes primeiro
    tasks = []
    for tid in task_ids:
        data = r.hgetall(f"task:{tid}")
        if data:
            data["id"] = int(tid)
            tasks.append(_to_dict(data, int_fields=["id"]))
    return tasks


def update_task_notion_id(task_id: int, notion_page_id: str) -> None:
    r = _r()
    r.hset(f"task:{task_id}", "notion_page_id", notion_page_id)
    r.hset(f"task:{task_id}", "updated_at", _now())
    r.set(f"tasks:notion:{notion_page_id}", task_id)


# =============================================================================
# AGENDA BLOCKS
# =============================================================================


def create_agenda_block(
    block_date: str,
    time_slot: str,
    task_title: str,
    task_id: Optional[int] = None,
    notion_page_id: Optional[str] = None,
    source_block_id: Optional[int] = None,
    created_by: str = "manual",
    reschedule_count: int = 0,
) -> int:
    with _lock:
        block_id = _next_id("blocks:next_id")
        now = _now()
        data = {
            "id": str(block_id),
            "block_date": block_date,
            "time_slot": time_slot,
            "task_id": str(task_id) if task_id is not None else "",
            "task_title": task_title,
            "notion_page_id": notion_page_id or "",
            "completed": "0",
            "rescheduled": "0",
            "rescheduled_to_block_id": "",
            "source_block_id": str(source_block_id)
            if source_block_id is not None
            else "",
            "created_by": created_by,
            "reschedule_count": str(reschedule_count),
            "created_at": now,
            "updated_at": now,
        }
        r = _r()
        r.hset(f"block:{block_id}", mapping=data)
        r.zadd(
            f"blocks:date:{block_date}", {str(block_id): _ts_from_timeslot(time_slot)}
        )
        if task_id is not None:
            r.zadd(f"blocks:task:{task_id}", {str(block_id): _ts_from_timeslot(time_slot)})
        if notion_page_id:
            r.set(f"blocks:notion:{notion_page_id}", block_id)
        return block_id


def get_today_agenda(include_rescheduled: bool = False) -> list[dict]:
    return get_agenda_for_date(
        date.today().isoformat(), include_rescheduled=include_rescheduled
    )


def get_agenda_for_date(
    block_date: str, include_rescheduled: bool = False
) -> list[dict]:
    r = _r()
    block_ids = r.zrange(f"blocks:date:{block_date}", 0, -1)
    blocks = []
    for bid in block_ids:
        data = r.hgetall(f"block:{bid}")
        if data:
            if not include_rescheduled and data.get("rescheduled", "0") == "1":
                continue
            data["id"] = int(bid)
            blocks.append(
                _to_dict(
                    data,
                    int_fields=[
                        "id",
                        "task_id",
                        "completed",
                        "rescheduled",
                        "rescheduled_to_block_id",
                        "source_block_id",
                        "reschedule_count",
                    ],
                )
            )
    return blocks


def list_agenda_between(
    start_date: str,
    end_date: str,
    include_rescheduled: bool = False,
) -> list[dict]:
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return []

    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt

    blocks = []
    cursor = start_dt
    while cursor <= end_dt:
        blocks.extend(
            get_agenda_for_date(
                cursor.isoformat(), include_rescheduled=include_rescheduled
            )
        )
        cursor += timedelta(days=1)
    return blocks


def get_block(block_id: int) -> Optional[dict]:
    data = _r().hgetall(f"block:{block_id}")
    if not data:
        return None
    data["id"] = int(block_id)
    return _to_dict(
        data,
        int_fields=[
            "id",
            "task_id",
            "completed",
            "rescheduled",
            "rescheduled_to_block_id",
            "source_block_id",
            "reschedule_count",
        ],
    )


def update_block(block_id: int, **fields: Any) -> None:
    r = _r()
    mapping = {}
    for key, value in fields.items():
        if value is None:
            mapping[key] = ""
        elif isinstance(value, bool):
            mapping[key] = "1" if value else "0"
        else:
            mapping[key] = str(value)
    mapping["updated_at"] = _now()
    r.hset(f"block:{block_id}", mapping=mapping)


def mark_block_completed(block_id: int, completed: bool = True) -> None:
    update_block(block_id, completed=completed)


# =============================================================================
# FOCUS SESSIONS
# =============================================================================


def start_focus_session(
    task_id: int, task_title: str, planned_minutes: int = 25
) -> int:
    with _lock:
        session_id = _next_id("sessions:next_id")
        now = _now()
        data = {
            "id": str(session_id),
            "task_id": str(task_id),
            "task_title": task_title,
            "started_at": now,
            "ended_at": "",
            "planned_minutes": str(planned_minutes),
            "actual_minutes": "",
            "status": "active",
            "notes": "",
        }
        r = _r()
        r.hset(f"session:{session_id}", mapping=data)
        r.zadd("sessions:all", {str(session_id): _ts(now)})
        r.zadd(f"sessions:task:{task_id}", {str(session_id): _ts(now)})
        r.set("session:active", session_id)
        return session_id


def end_focus_session(
    session_id: int, status: str = "completed", notes: Optional[str] = None
) -> None:
    r = _r()
    now = _now()
    session = r.hgetall(f"session:{session_id}")

    actual_minutes = ""
    if session.get("started_at"):
        try:
            started = datetime.fromisoformat(session["started_at"])
            ended = datetime.fromisoformat(now)
            actual_minutes = str(int((ended - started).total_seconds() / 60))
        except Exception:
            pass

    r.hset(
        f"session:{session_id}",
        mapping={
            "ended_at": now,
            "status": status,
            "actual_minutes": actual_minutes,
            "notes": notes or session.get("notes", ""),
        },
    )

    active = r.get("session:active")
    if active and int(active) == session_id:
        r.delete("session:active")


def get_active_focus_session() -> Optional[dict]:
    r = _r()
    active_id = r.get("session:active")
    if not active_id:
        return None
    data = r.hgetall(f"session:{active_id}")
    if data and data.get("status") == "active":
        data["id"] = int(active_id)
        return _to_dict(data, int_fields=["id"])
    # Sessão expirou ou foi finalizada; limpa ponteiro
    r.delete("session:active")
    return None


def get_focus_sessions_for_task(task_id: int) -> list[dict]:
    """Retorna todas as sessões de foco associadas a uma tarefa específica."""
    r = _r()
    session_ids = r.zrange(f"sessions:task:{task_id}", 0, -1)
    sessions = []
    for sid in session_ids:
        data = r.hgetall(f"session:{sid}")
        if data:
            data["id"] = int(sid)
            sessions.append(_to_dict(data, int_fields=["id"]))
    return sessions


def get_agenda_blocks_for_task(task_id: int) -> list[dict]:
    """Retorna todos os blocos de agenda associados a uma tarefa específica."""
    r = _r()
    block_ids = r.zrange(f"blocks:task:{task_id}", 0, -1)
    blocks = []
    for bid in block_ids:
        data = r.hgetall(f"block:{bid}")
        if data:
            data["id"] = int(bid)
            blocks.append(
                _to_dict(
                    data,
                    int_fields=[
                        "id",
                        "task_id",
                        "completed",
                        "rescheduled",
                        "rescheduled_to_block_id",
                        "source_block_id",
                        "reschedule_count",
                    ],
                )
            )
    return blocks


def get_agenda_blocks_for_tasks(task_ids: list[int]) -> dict[int, list[dict]]:
    """Retorna blocos por tarefa em lote para reduzir round-trips ao Redis."""
    if not task_ids:
        return {}

    r = _r()
    pipe = r.pipeline()
    for task_id in task_ids:
        pipe.zrange(f"blocks:task:{task_id}", 0, -1)
    block_id_lists = pipe.execute()

    seen = set()
    unique_block_ids = []
    for block_ids in block_id_lists:
        for bid in block_ids:
            if bid not in seen:
                seen.add(bid)
                unique_block_ids.append(bid)

    block_data_map = {}
    if unique_block_ids:
        pipe = r.pipeline()
        for bid in unique_block_ids:
            pipe.hgetall(f"block:{bid}")
        raw_blocks = pipe.execute()
        for bid, data in zip(unique_block_ids, raw_blocks):
            if not data:
                continue
            data["id"] = int(bid)
            block_data_map[bid] = _to_dict(
                data,
                int_fields=[
                    "id",
                    "task_id",
                    "completed",
                    "rescheduled",
                    "rescheduled_to_block_id",
                    "source_block_id",
                    "reschedule_count",
                ],
            )

    blocks_by_task: dict[int, list[dict]] = {}
    for task_id, block_ids in zip(task_ids, block_id_lists):
        blocks_by_task[task_id] = [
            block_data_map[bid] for bid in block_ids if bid in block_data_map
        ]
    return blocks_by_task


# =============================================================================
# AGENT HANDOFFS (auditoria)
# =============================================================================


def log_handoff(
    source_agent: str,
    target_agent: str,
    action: str,
    payload: Any = None,
    result: Any = None,
    status: str = "pending",
) -> int:
    with _lock:
        handoff_id = _next_id("handoffs:next_id")
        now = _now()
        data = {
            "id": str(handoff_id),
            "source_agent": source_agent,
            "target_agent": target_agent,
            "action": action,
            "payload": json.dumps(payload) if payload is not None else "",
            "result": json.dumps(result) if result is not None else "",
            "status": status,
            "created_at": now,
        }
        r = _r()
        r.hset(f"handoff:{handoff_id}", mapping=data)
        r.zadd("handoffs:all", {str(handoff_id): _ts(now)})
        return handoff_id


def update_handoff_result(
    handoff_id: int, result: Any, status: str = "success"
) -> None:
    _r().hset(
        f"handoff:{handoff_id}",
        mapping={
            "result": json.dumps(result),
            "status": status,
        },
    )


# =============================================================================
# SYSTEM STATE (chave-valor)
# =============================================================================


def set_state(key: str, value: Any) -> None:
    _r().set(f"state:{key}", json.dumps(value))


def get_state(key: str, default: Any = None) -> Any:
    val = _r().get(f"state:{key}")
    if val is None:
        return default
    try:
        return json.loads(val)
    except Exception:
        return val


# =============================================================================
# ALERTS
# =============================================================================


def create_alert(alert_type: str, message: str) -> int:
    with _lock:
        alert_id = _next_id("alerts:next_id")
        now = _now()
        data = {
            "id": str(alert_id),
            "alert_type": alert_type,
            "message": message,
            "acknowledged": "0",
            "created_at": now,
        }
        r = _r()
        r.hset(f"alert:{alert_id}", mapping=data)
        r.zadd("alerts:pending", {str(alert_id): _ts(now)})
        r.zadd("alerts:all", {str(alert_id): _ts(now)})
        return alert_id


def get_pending_alerts() -> list[dict]:
    r = _r()
    alert_ids = r.zrevrange("alerts:pending", 0, -1)
    alerts = []
    for aid in alert_ids:
        data = r.hgetall(f"alert:{aid}")
        if data and data.get("acknowledged", "0") == "0":
            data["id"] = int(aid)
            alerts.append(_to_dict(data, int_fields=["id", "acknowledged"]))
    return alerts


def list_alerts(limit: int = 50, include_acknowledged: bool = True) -> list[dict]:
    r = _r()
    alert_ids = r.zrevrange("alerts:all", 0, max(limit - 1, 0))
    alerts = []
    for aid in alert_ids:
        data = r.hgetall(f"alert:{aid}")
        if not data:
            continue
        if not include_acknowledged and data.get("acknowledged", "0") != "0":
            continue
        data["id"] = int(aid)
        alerts.append(_to_dict(data, int_fields=["id", "acknowledged"]))
    return alerts


def acknowledge_alert(alert_id: int) -> None:
    r = _r()
    r.hset(f"alert:{alert_id}", "acknowledged", "1")
    r.zrem("alerts:pending", str(alert_id))


# =============================================================================
# AUDIT EVENTS
# =============================================================================


def create_audit_event(
    event_type: str,
    title: str,
    details: str = "",
    level: str = "info",
    agent: str = "system",
    payload: Any = None,
    related_id: Optional[str] = None,
) -> int:
    with _lock:
        event_id = _next_id("audit:next_id")
        now = _now()
        data = {
            "id": str(event_id),
            "event_type": event_type,
            "title": title,
            "details": details,
            "level": level,
            "agent": agent,
            "payload": json.dumps(payload, ensure_ascii=False)
            if payload is not None
            else "",
            "related_id": related_id or "",
            "created_at": now,
        }
        r = _r()
        r.hset(f"audit:{event_id}", mapping=data)
        r.zadd("audit:events", {str(event_id): _ts(now)})
        return event_id


def list_audit_events(limit: int = 50, event_type: Optional[str] = None) -> list[dict]:
    r = _r()
    event_ids = r.zrevrange("audit:events", 0, max(limit - 1, 0))
    events = []
    for eid in event_ids:
        data = r.hgetall(f"audit:{eid}")
        if not data:
            continue
        if event_type and data.get("event_type") != event_type:
            continue
        data["id"] = int(eid)
        events.append(_to_dict(data, int_fields=["id"]))
    return events


# =============================================================================
# RETROSPECTIVE QUERIES
# =============================================================================


def get_sessions_since(since_iso: str) -> list[dict]:
    r = _r()
    since_ts = _ts(since_iso)
    session_ids = r.zrangebyscore("sessions:all", since_ts, "+inf")
    sessions = []
    for sid in session_ids:
        data = r.hgetall(f"session:{sid}")
        if data:
            data["id"] = int(sid)
            sessions.append(_to_dict(data, int_fields=["id"]))
    return sessions


def get_completed_tasks_since(since_iso: str) -> list[dict]:
    return [
        t
        for t in list_all_tasks()
        if t.get("status") == "Concluído" and (t.get("updated_at") or "") >= since_iso
    ]


def get_handoffs_since(since_iso: str) -> list[dict]:
    r = _r()
    since_ts = _ts(since_iso)
    handoff_ids = r.zrangebyscore("handoffs:all", since_ts, "+inf")
    handoffs = []
    for hid in handoff_ids:
        data = r.hgetall(f"handoff:{hid}")
        if data:
            data["id"] = int(hid)
            handoffs.append(_to_dict(data, int_fields=["id"]))
    return handoffs


def list_recent_handoffs(limit: int = 50) -> list[dict]:
    r = _r()
    handoff_ids = r.zrevrange("handoffs:all", 0, max(limit - 1, 0))
    handoffs = []
    for hid in handoff_ids:
        data = r.hgetall(f"handoff:{hid}")
        if data:
            data["id"] = int(hid)
            handoffs.append(_to_dict(data, int_fields=["id"]))
    return handoffs
