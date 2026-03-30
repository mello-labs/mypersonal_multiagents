# SPRINT VIDA — Interrupção Cognitiva e Rotinas Pessoais

**Status:** Pronto para implementar
**Prioridade:** P0 — resolve o problema central: hiperfoco sem consciência de tempo
**Estimativa:** 2-3 dias de implementação real

---

## O problema que este sprint resolve

Autismo + hiperfoco = 8 horas viram 15 minutos. O terminal não interrompe.
Precisamos de canais que forcem interrupção física: tela + som ambiente.

---

## Entregáveis

```text
| # | O que | Arquivo | Depende de |
|---|---|---|---|  
| 1 | Mac push via osascript | `core/notifier.py` | nada |
| 2 | Escalada por tempo no Focus Guard | `agents/focus_guard.py` | entregável 1 |
| 3 | Alexa via IFTTT webhook | `core/notifier.py` | conta IFTTT |
| 4 | Life Guard agent (rotinas pessoais) | `agents/life_guard.py` | entregável 1 |
| 5 | Integração Life Guard no main.py | `main.py` | entregável 4 |
````

---

## Entregável 1 — Mac push via osascript

**Adicionar em `core/notifier.py`:**

```python
import subprocess

def mac_push(title: str, message: str, sound: bool = False) -> None:
    """Envia notificação nativa macOS via AppleScript."""
    sound_line = ' sound name "Sosumi"' if sound else ""
    script = f'display notification "{message}" with title "{title}"{sound_line}'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5
        )
    except Exception:
        pass  # nunca quebra o agente por falha de notificação


def alexa_announce(message: str) -> None:
    """Dispara anúncio na Alexa via IFTTT webhook."""
    import requests
    key = os.getenv("IFTTT_WEBHOOK_KEY", "")
    event = os.getenv("IFTTT_ALEXA_EVENT", "neo_alert")
    if not key:
        return
    try:
        requests.post(
            f"https://maker.ifttt.com/trigger/{event}/with/key/{key}",
            json={"value1": message},
            timeout=5
        )
    except Exception:
        pass
```

**Variáveis de ambiente a adicionar no `.env`:**

```keys
IFTTT_WEBHOOK_KEY=<sua_key_do_ifttt>
IFTTT_ALEXA_EVENT=neo_alert
```

**Setup IFTTT (10 minutos):**

1. ifttt.com → Create applet
2. If: Webhooks → "Receive a web request" → event name: `neo_alert`
3. Then: Amazon Alexa → "Announce something" → message: `{{Value1}}`
4. Conectar sua conta Alexa
5. Pegar a key em: ifttt.com/maker_webhooks/settings

---

## Entregável 2 — Escalada por tempo no Focus Guard

**Lógica de escalada em `agents/focus_guard.py`:**

A função `_run_focus_check` já detecta desvios. Adicionar camada de escalada:

```python
# Adicionar no início do arquivo
ESCALATION_LEVELS = [
    {"minutes": 30,  "channel": "mac",         "sound": False, "msg": "30 min em {task}. Planejado: {planned}min."},
    {"minutes": 60,  "channel": "mac",         "sound": True,  "msg": "1 hora em {task}. Hora de checar."},
    {"minutes": 120, "channel": "mac+alexa",   "sound": True,  "msg": "2 horas em {task}. Para agora."},
    {"minutes": 240, "channel": "mac+alexa",   "sound": True,  "msg": "4 horas. Sai do computador por 10 minutos."},
]

def _check_escalation(session_minutes: int, task_title: str, planned_minutes: int) -> None:
    """Dispara notificação no canal certo baseado no tempo de sessão."""
    for level in ESCALATION_LEVELS:
        # dispara apenas uma vez por nível (verificar se já foi enviado hoje)
        state_key = f"escalation:{datetime.now().date()}:{task_title}:{level['minutes']}"
        if memory.get_state(state_key):
            continue
        if session_minutes >= level["minutes"]:
            msg = level["msg"].format(task=task_title, planned=planned_minutes)
            if "mac" in level["channel"]:
                notifier.mac_push("⏱ NEØ Focus Guard", msg, sound=level["sound"])
            if "alexa" in level["channel"]:
                notifier.alexa_announce(msg)
            memory.set_state(state_key, "sent")
            break  # só um nível por check
```

**Chamar `_check_escalation` dentro de `_run_focus_check`:**

```python
# Após calcular session_minutes a partir da sessão ativa
if active_session and session_minutes:
    _check_escalation(session_minutes, task_title, planned_minutes)
```

---

## Entregável 3 — Life Guard agent

**Criar `agents/life_guard.py`:**

```python
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

import os
import sys
from datetime import datetime, date, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import memory, notifier

# ---------------------------------------------------------------------------
# Rotinas diárias — horário e mensagem
# ---------------------------------------------------------------------------

```code
DAILY_ROUTINES = [
    {
        "id":      "exercise",
        "name":    "Exercício",
        "check_at": "07:00",
        "message": "Você se exercitou hoje?",
        "channel": "mac",
        "sound":   False,
    },
    {
        "id":      "shower",
        "name":    "Banho",
        "check_at": "10:00",
        "message": "Hora do banho.",
        "channel": "mac",
        "sound":   False,
    },
    {
        "id":      "lunch",
        "name":    "Almoço",
        "check_at": "12:30",
        "message": "Parar para almoçar.",
        "channel": "mac+alexa",
        "sound":   False,
    },
    {
        "id":      "dinner",
        "name":    "Jantar",
        "check_at": "19:30",
        "message": "Parar para jantar.",
        "channel": "mac",
        "sound":   False,
    },
]

````

WATER_INTERVAL_MINUTES = 90
ACTIVE_HOURS = (8, 22)  # só lembra entre 8h e 22h

```code
def check_daily_routines() -> list[dict]:
    """Verifica rotinas diárias e dispara lembretes."""
    now = datetime.now()
    today = date.today().isoformat()
    triggered = []

    for routine in DAILY_ROUTINES:
        state_key = f"life_guard:{today}:{routine['id']}"
        if memory.get_state(state_key):
            continue  # já enviado hoje

        scheduled_h, scheduled_m = map(int, routine["check_at"].split(":"))
        scheduled_dt = now.replace(hour=scheduled_h, minute=scheduled_m, second=0)

        # janela de 30 minutos após o horário programado
        if scheduled_dt <= now <= scheduled_dt + timedelta(minutes=30):
            _dispatch(routine["message"], routine["channel"], routine.get("sound", False))
            memory.set_state(state_key, "sent")
            triggered.append(routine["id"])

    return triggered
````

```code
def check_hydration() -> bool:
    """Lembra de beber água a cada 90 minutos no horário ativo."""
    now = datetime.now()
    if not (ACTIVE_HOURS[0] <= now.hour < ACTIVE_HOURS[1]):
        return False

    state_key = "life_guard:water:last_sent"
    last_sent_iso = memory.get_state(state_key)

    if last_sent_iso:
        last_sent = datetime.fromisoformat(last_sent_iso)
        if (now - last_sent).total_seconds() < WATER_INTERVAL_MINUTES * 60:
            return False

    _dispatch("Beber água.", "mac", sound=False)
    memory.set_state(state_key, now.isoformat())
    return True
```

def check_finances() -> list[dict]:
    """
    Verifica pagamentos próximos do vencimento.
    Os dados vêm de `life_guard:finances` no Redis (JSON array).

## Formato esperado

```code
    [
      {"name": "Cartão XP", "due_day": 15, "amount": 1200.00},
      {"name": "Aluguel",   "due_day": 5,  "amount": 3500.00},
    ]
    """
    today = date.today()
    finances_raw = memory.get_state("life_guard:finances")
    if not finances_raw:
        return []

    import json
    finances = json.loads(finances_raw)
    alerts = []

    for item in finances:
        due_day = item.get("due_day", 0)
        days_until = (due_day - today.day) % 30  # aproximação

        if 0 <= days_until <= 3:
            state_key = f"life_guard:finance:{today.year}-{today.month}:{item['name']}"
            if memory.get_state(state_key):
                continue
            msg = f"{item['name']}: vence em {days_until}d — R$ {item['amount']:.2f}"
            _dispatch(msg, "mac", sound=True)
            memory.set_state(state_key, "sent")
            alerts.append(item)

    return alerts

def _dispatch(message: str, channel: str, sound: bool) -> None:
    if "mac" in channel:
        notifier.mac_push("NEØ Life Guard", message, sound=sound)
    if "alexa" in channel:
        notifier.alexa_announce(message)
    notifier.info(f"[life_guard] {message}")

def run_all_checks() -> dict:
    """Entry point para o loop de background."""
    return {
        "routines": check_daily_routines(),
        "hydration": check_hydration(),
        "finances": check_finances(),
    }

def add_finance(name: str, due_day: int, amount: float) -> dict:
    """Adiciona ou atualiza um item de finanças pessoais."""
    import json
    finances_raw = memory.get_state("life_guard:finances") or "[]"
    finances = json.loads(finances_raw)
    finances = [f for f in finances if f["name"] != name]  # remove duplicata
    finances.append({"name": name, "due_day": due_day, "amount": amount})
    memory.set_state("life_guard:finances", json.dumps(finances))
    return {"status": "ok", "item": name}

def confirm_routine(routine_id: str) -> dict:
    """Marca rotina como feita (ex: 'já me exercitei')."""
    today = date.today().isoformat()
    memory.set_state(f"life_guard:{today}:{routine_id}:done", "true")
    return {"status": "confirmed", "routine": routine_id}

def handle_handoff(payload: dict) -> dict:
    action = payload.get("action")
    if action == "add_finance":
        return add_finance(payload["name"], payload["due_day"], payload["amount"])
    if action == "confirm_routine":
        return confirm_routine(payload["routine_id"])
    if action == "check":
        return run_all_checks()
    return {"error": f"unknown action: {action}"}
````

```

---

## Entregável 4 — Registrar Life Guard no main.py e Focus Guard

**Em `main.py` / `focus_guard_service.py`, adicionar ao loop de background:**

```python
from agents import life_guard

# No loop do Focus Guard (a cada 15 min já está rodando)
# Adicionar:
life_guard.run_all_checks()
```

**No CLI (main.py), adicionar comandos:**

```python
elif command in ["vida", "life"]:
    result = life_guard.run_all_checks()
    print(result)
elif command.startswith("pagar "):
    # ex: "pagar Cartão XP dia 15 valor 1200"
    # parsear e chamar life_guard.add_finance(...)
    pass
elif command.startswith("fiz "):
    # ex: "fiz exercicio"
    routine_map = {"exercicio": "exercise", "banho": "shower"}
    routine_id = routine_map.get(command.replace("fiz ", "").strip())
    if routine_id:
        life_guard.confirm_routine(routine_id)
```

---

## Setup IFTTT + Alexa (passo a passo)

```terminal
1. Criar conta em ifttt.com
2. My Applets → New Applet
3. IF: Webhooks → "Receive a web request"
   - Event Name: neo_alert
4. THEN: Amazon Alexa → "Announce something"
   - Message: {{Value1}}
5. Salvar
6. Ir em: ifttt.com/maker_webhooks/settings
   - Copiar a key (formato: xXxXxXxXx...)
7. Adicionar no .env:
   IFTTT_WEBHOOK_KEY=<sua_key>
   IFTTT_ALEXA_EVENT=neo_alert
8. Testar:
   curl -X POST "https://maker.ifttt.com/trigger/neo_alert/with/key/SUA_KEY" \
     -H "Content-Type: application/json" \
     -d '{"value1": "Teste da Alexa funcionando"}'
```

---

## Variáveis de ambiente necessárias

Adicionar ao `.env`:

```bash
# Notificações
IFTTT_WEBHOOK_KEY=           # da conta IFTTT
IFTTT_ALEXA_EVENT=neo_alert  # nome do evento

# Life Guard
LIFE_GUARD_ACTIVE_HOUR_START=8
LIFE_GUARD_ACTIVE_HOUR_END=22
LIFE_GUARD_WATER_INTERVAL=90
```

---

## Critérios de aceite

- [ ] `notifier.mac_push("teste", "funciona")` abre pop-up no canto da tela
- [ ] `notifier.alexa_announce("teste")` faz a Alexa falar na sala
- [ ] Focus Guard com sessão aberta há 30min → mac push automático
- [ ] Focus Guard com sessão aberta há 2h → mac push + Alexa
- [ ] `python main.py vida` imprime status das rotinas do dia
- [ ] `python main.py fiz banho` confirma a rotina e para o lembrete do dia
- [ ] Finance alert dispara 3 dias antes do vencimento
