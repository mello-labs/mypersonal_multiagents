# =============================================================================
# core/memory.py — Estado compartilhado entre agentes via SQLite
# =============================================================================
# Todos os agentes leem/escrevem neste módulo para manter consistência.
# O SQLite é thread-safe no modo WAL e adequado para uso local.

import sqlite3
import json
import threading
from datetime import datetime, date
from typing import Optional, Any
from pathlib import Path

from config import MEMORY_DB_PATH


# Lock global para operações críticas (extra segurança além do WAL)
_lock = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    """Retorna uma conexão SQLite configurada com WAL e row_factory."""
    conn = sqlite3.connect(MEMORY_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # Write-Ahead Logging: melhor concorrência
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """
    Cria todas as tabelas necessárias se não existirem.
    Chamar no startup da aplicação.
    """
    Path(MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with _get_connection() as conn:
        conn.executescript("""
            -- Tarefas gerenciadas localmente (espelho do Notion)
            CREATE TABLE IF NOT EXISTS tasks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                notion_page_id  TEXT UNIQUE,           -- ID da página no Notion (nullable)
                title           TEXT NOT NULL,
                status          TEXT DEFAULT 'A fazer', -- A fazer | Em progresso | Concluído
                priority        TEXT DEFAULT 'Média',   -- Alta | Média | Baixa
                scheduled_time  TEXT,                   -- ISO datetime ou hora HH:MM
                actual_time     TEXT,                   -- Horário real de início/conclusão
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            -- Blocos de agenda diária
            CREATE TABLE IF NOT EXISTS agenda_blocks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                notion_page_id  TEXT UNIQUE,
                block_date      TEXT NOT NULL,          -- YYYY-MM-DD
                time_slot       TEXT NOT NULL,          -- ex: "09:00-10:00"
                task_id         INTEGER REFERENCES tasks(id),
                task_title      TEXT,                   -- Cache do título da tarefa
                completed       INTEGER DEFAULT 0,      -- 0=false, 1=true
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            -- Sessões de foco rastreadas pelo Focus Guard
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         INTEGER REFERENCES tasks(id),
                task_title      TEXT,
                started_at      TEXT NOT NULL,
                ended_at        TEXT,
                planned_minutes INTEGER,
                actual_minutes  INTEGER,
                status          TEXT DEFAULT 'active',  -- active | completed | abandoned
                notes           TEXT
            );

            -- Log de handoffs entre agentes (auditoria)
            CREATE TABLE IF NOT EXISTS agent_handoffs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source_agent    TEXT NOT NULL,
                target_agent    TEXT NOT NULL,
                action          TEXT NOT NULL,
                payload         TEXT,                   -- JSON serializado
                result          TEXT,                   -- JSON serializado
                status          TEXT DEFAULT 'pending', -- pending | success | error
                created_at      TEXT DEFAULT (datetime('now'))
            );

            -- Estado global do sistema (chave-valor)
            CREATE TABLE IF NOT EXISTS system_state (
                key             TEXT PRIMARY KEY,
                value           TEXT NOT NULL,          -- JSON serializado
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            -- Alertas gerados pelo Focus Guard
            CREATE TABLE IF NOT EXISTS alerts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type      TEXT NOT NULL,          -- focus_check | deviation | reminder
                message         TEXT NOT NULL,
                acknowledged    INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now'))
            );
        """)
    print(f"[Memory] Banco de dados inicializado em: {MEMORY_DB_PATH}")


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
    """Cria uma nova tarefa e retorna seu ID local."""
    with _lock, _get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO tasks (title, priority, scheduled_time, notes, notion_page_id)
               VALUES (?, ?, ?, ?, ?)""",
            (title, priority, scheduled_time, notes, notion_page_id),
        )
        return cur.lastrowid


def update_task_status(task_id: int, status: str, actual_time: Optional[str] = None) -> None:
    """Atualiza o status de uma tarefa (e opcionalmente o horário real)."""
    with _lock, _get_connection() as conn:
        conn.execute(
            """UPDATE tasks
               SET status = ?, actual_time = COALESCE(?, actual_time),
                   updated_at = datetime('now')
               WHERE id = ?""",
            (status, actual_time, task_id),
        )


def get_task(task_id: int) -> Optional[dict]:
    """Retorna uma tarefa por ID ou None."""
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def get_tasks_by_status(status: str) -> list[dict]:
    """Retorna todas as tarefas com um determinado status."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY scheduled_time ASC",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_today_tasks() -> list[dict]:
    """Retorna tarefas agendadas para hoje (por data no scheduled_time)."""
    today = date.today().isoformat()
    with _get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE scheduled_time LIKE ? OR scheduled_time LIKE ?
               ORDER BY scheduled_time ASC""",
            (f"{today}%", "%:%"),  # data completa ou só hora
        ).fetchall()
        return [dict(r) for r in rows]


def list_all_tasks() -> list[dict]:
    """Lista todas as tarefas ordenadas por horário."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def update_task_notion_id(task_id: int, notion_page_id: str) -> None:
    """Vincula uma tarefa local a uma página do Notion."""
    with _lock, _get_connection() as conn:
        conn.execute(
            "UPDATE tasks SET notion_page_id = ?, updated_at = datetime('now') WHERE id = ?",
            (notion_page_id, task_id),
        )


# =============================================================================
# AGENDA BLOCKS
# =============================================================================

def create_agenda_block(
    block_date: str,
    time_slot: str,
    task_title: str,
    task_id: Optional[int] = None,
    notion_page_id: Optional[str] = None,
) -> int:
    """Cria um bloco de agenda e retorna seu ID."""
    with _lock, _get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO agenda_blocks (block_date, time_slot, task_id, task_title, notion_page_id)
               VALUES (?, ?, ?, ?, ?)""",
            (block_date, time_slot, task_id, task_title, notion_page_id),
        )
        return cur.lastrowid


def get_today_agenda() -> list[dict]:
    """Retorna todos os blocos da agenda de hoje, ordenados por horário."""
    today = date.today().isoformat()
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM agenda_blocks WHERE block_date = ? ORDER BY time_slot ASC",
            (today,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_block_completed(block_id: int, completed: bool = True) -> None:
    """Marca um bloco de agenda como concluído ou não."""
    with _lock, _get_connection() as conn:
        conn.execute(
            "UPDATE agenda_blocks SET completed = ?, updated_at = datetime('now') WHERE id = ?",
            (1 if completed else 0, block_id),
        )


# =============================================================================
# FOCUS SESSIONS
# =============================================================================

def start_focus_session(task_id: int, task_title: str, planned_minutes: int = 25) -> int:
    """Inicia uma sessão de foco e retorna seu ID."""
    with _lock, _get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO focus_sessions (task_id, task_title, started_at, planned_minutes, status)
               VALUES (?, ?, datetime('now'), ?, 'active')""",
            (task_id, task_title, planned_minutes),
        )
        return cur.lastrowid


def end_focus_session(session_id: int, status: str = "completed", notes: Optional[str] = None) -> None:
    """Finaliza uma sessão de foco calculando o tempo real."""
    with _lock, _get_connection() as conn:
        conn.execute(
            """UPDATE focus_sessions
               SET ended_at = datetime('now'),
                   actual_minutes = CAST(
                       (julianday('now') - julianday(started_at)) * 24 * 60 AS INTEGER
                   ),
                   status = ?,
                   notes = COALESCE(?, notes)
               WHERE id = ?""",
            (status, notes, session_id),
        )


def get_active_focus_session() -> Optional[dict]:
    """Retorna a sessão de foco ativa no momento, ou None."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM focus_sessions WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


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
    """Registra um handoff entre agentes para auditoria. Retorna o ID do log."""
    with _lock, _get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO agent_handoffs (source_agent, target_agent, action, payload, result, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                source_agent,
                target_agent,
                action,
                json.dumps(payload) if payload is not None else None,
                json.dumps(result) if result is not None else None,
                status,
            ),
        )
        return cur.lastrowid


def update_handoff_result(handoff_id: int, result: Any, status: str = "success") -> None:
    """Atualiza o resultado de um handoff já registrado."""
    with _lock, _get_connection() as conn:
        conn.execute(
            "UPDATE agent_handoffs SET result = ?, status = ? WHERE id = ?",
            (json.dumps(result), status, handoff_id),
        )


# =============================================================================
# SYSTEM STATE (chave-valor)
# =============================================================================

def set_state(key: str, value: Any) -> None:
    """Persiste um valor de estado do sistema (upsert)."""
    with _lock, _get_connection() as conn:
        conn.execute(
            """INSERT INTO system_state (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, json.dumps(value)),
        )


def get_state(key: str, default: Any = None) -> Any:
    """Lê um valor de estado do sistema."""
    with _get_connection() as conn:
        row = conn.execute("SELECT value FROM system_state WHERE key = ?", (key,)).fetchone()
        if row:
            return json.loads(row["value"])
        return default


# =============================================================================
# ALERTS
# =============================================================================

def create_alert(alert_type: str, message: str) -> int:
    """Cria um alerta do Focus Guard."""
    with _lock, _get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO alerts (alert_type, message) VALUES (?, ?)",
            (alert_type, message),
        )
        return cur.lastrowid


def get_pending_alerts() -> list[dict]:
    """Retorna alertas não reconhecidos."""
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def acknowledge_alert(alert_id: int) -> None:
    """Marca um alerta como reconhecido."""
    with _lock, _get_connection() as conn:
        conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
