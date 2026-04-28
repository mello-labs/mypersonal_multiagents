"""
agents/life_guard.py — Guardião de rotinas pessoais

Monitora e notifica sobre:
- Hidratação (a cada 90 min durante horário ativo)
- Exercício físico (check diário às 7h)
- Higiene (check às 10h)
- Refeições (almoço 12h30, jantar 19h30)
- Finanças (alertas de vencimento próximo)

Não julga. Apenas registra e lembra.
"""

import json
import sys
from datetime import date, datetime, timedelta

from config import (
    LIFE_GUARD_ACTIVE_HOUR_END,
    LIFE_GUARD_ACTIVE_HOUR_START,
    LIFE_GUARD_WATER_INTERVAL,
)
from core import memory, notifier

AGENT_NAME = "life_guard"

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

DAILY_ROUTINES = [
    {
        "id": "exercise",
        "name": "Exercício",
        "check_at": "07:00",
        "message": "Você se exercitou hoje?",
        "channel": "mac",
        "sound": False,
    },
    {
        "id": "shower",
        "name": "Banho",
        "check_at": "10:00",
        "message": "Hora do banho.",
        "channel": "mac",
        "sound": False,
    },
    {
        "id": "lunch",
        "name": "Almoco",
        "check_at": "12:30",
        "message": "Parar para almocar.",
        "channel": "mac+alexa",
        "sound": False,
    },
    {
        "id": "dinner",
        "name": "Jantar",
        "check_at": "19:30",
        "message": "Parar para jantar.",
        "channel": "mac",
        "sound": False,
    },
]

WATER_INTERVAL_MINUTES = LIFE_GUARD_WATER_INTERVAL
ACTIVE_HOUR_START = LIFE_GUARD_ACTIVE_HOUR_START
ACTIVE_HOUR_END = LIFE_GUARD_ACTIVE_HOUR_END


# ---------------------------------------------------------------------------
# Despacho de notificações
# ---------------------------------------------------------------------------


def _dispatch(message: str, channel: str, sound: bool) -> None:
    if "mac" in channel:
        notifier.mac_push("NEO Life Guard", message, sound=sound)
    if "alexa" in channel:
        notifier.alexa_announce(message)
    notifier.info(f"[life_guard] {message}", AGENT_NAME)


# ---------------------------------------------------------------------------
# Rotinas diárias
# ---------------------------------------------------------------------------


def check_daily_routines() -> list:
    """Verifica rotinas diárias e dispara lembretes."""
    now = datetime.now()
    today = date.today().isoformat()
    triggered = []

    for routine in DAILY_ROUTINES:
        state_key = f"life_guard:{today}:{routine['id']}"
        if memory.get_state(state_key):
            continue  # já enviado hoje

        h, m = map(int, routine["check_at"].split(":"))
        scheduled_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)

        # janela de 30 minutos após o horário programado
        if scheduled_dt <= now <= scheduled_dt + timedelta(minutes=30):
            _dispatch(
                routine["message"], routine["channel"], routine.get("sound", False)
            )
            memory.set_state(state_key, "sent")
            triggered.append(routine["id"])

    return triggered


# ---------------------------------------------------------------------------
# Hidratação
# ---------------------------------------------------------------------------


def check_hydration() -> bool:
    """Lembra de beber água a cada 90 minutos no horário ativo."""
    now = datetime.now()
    if not (ACTIVE_HOUR_START <= now.hour < ACTIVE_HOUR_END):
        return False

    state_key = "life_guard:water:last_sent"
    last_sent_iso = memory.get_state(state_key)

    if last_sent_iso:
        try:
            last_sent = datetime.fromisoformat(last_sent_iso)
            if (now - last_sent).total_seconds() < WATER_INTERVAL_MINUTES * 60:
                return False
        except Exception:
            pass

    _dispatch("Beber agua.", "mac", sound=False)
    memory.set_state(state_key, now.isoformat())
    return True


# ---------------------------------------------------------------------------
# Finanças
# ---------------------------------------------------------------------------


def check_finances() -> list:
    """
    Verifica pagamentos próximos do vencimento.
    Formato esperado em life_guard:finances (JSON):
    [{"name": "Cartao XP", "due_day": 15, "amount": 1200.00}]
    """
    today = date.today()
    finances_raw = memory.get_state("life_guard:finances")
    if not finances_raw:
        return []

    try:
        finances = json.loads(finances_raw)
    except Exception:
        return []

    alerts = []
    for item in finances:
        due_day = item.get("due_day", 0)
        days_until = (due_day - today.day) % 30  # aproximação mensal

        if 0 <= days_until <= 3:
            state_key = f"life_guard:finance:{today.year}-{today.month}:{item['name']}"
            if memory.get_state(state_key):
                continue
            msg = f"{item['name']}: vence em {days_until}d - R$ {item['amount']:.2f}"
            _dispatch(msg, "mac", sound=True)
            memory.set_state(state_key, "sent")
            alerts.append(item)

    return alerts


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_all_checks() -> dict:
    """Entry point para o loop de background."""
    return {
        "routines": check_daily_routines(),
        "hydration": check_hydration(),
        "finances": check_finances(),
    }


# ---------------------------------------------------------------------------
# Ações manuais
# ---------------------------------------------------------------------------


def add_finance(name: str, due_day: int, amount: float) -> dict:
    """Adiciona ou atualiza um item de finanças pessoais."""
    finances_raw = memory.get_state("life_guard:finances") or "[]"
    try:
        finances = json.loads(finances_raw)
    except Exception:
        finances = []
    finances = [f for f in finances if f["name"] != name]
    finances.append({"name": name, "due_day": due_day, "amount": amount})
    memory.set_state("life_guard:finances", json.dumps(finances))
    return {"status": "ok", "item": name}


def confirm_routine(routine_id: str) -> dict:
    """Marca rotina como feita (ex: 'já me exercitei')."""
    today = date.today().isoformat()
    memory.set_state(f"life_guard:{today}:{routine_id}", "sent")
    memory.set_state(f"life_guard:{today}:{routine_id}:done", "true")
    return {"status": "confirmed", "routine": routine_id}


# ---------------------------------------------------------------------------
# Handoff entry point
# ---------------------------------------------------------------------------


def handle_handoff(payload: dict) -> dict:
    action = payload.get("action")
    if action == "add_finance":
        return add_finance(payload["name"], payload["due_day"], payload["amount"])
    if action == "confirm_routine":
        return confirm_routine(payload["routine_id"])
    if action == "check":
        return run_all_checks()
    return {"error": f"unknown action: {action}"}
