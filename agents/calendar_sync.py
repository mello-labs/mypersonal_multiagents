# =============================================================================
# agents/calendar_sync.py — Agente de integração com Google Calendar
# =============================================================================
# Importa eventos do Google Calendar como blocos de agenda.
# Exporta blocos criados pelo Scheduler de volta ao calendário.
#
# Setup:
#   1. Crie um projeto no Google Cloud Console
#   2. Ative a Google Calendar API
#   3. Baixe credentials.json e coloque na raiz do projeto
#   4. Execute: python main.py calendar-auth
#      → Abre o browser para OAuth e salva token.json
#
# Variáveis de ambiente:
#   GOOGLE_CREDENTIALS_FILE  = caminho para credentials.json  (padrão: ./credentials.json)
#   GOOGLE_TOKEN_FILE        = caminho para token.json        (padrão: ./token.json)
#   GOOGLE_CALENDAR_ID       = ID do calendário               (padrão: primary)

import sys
import os
from datetime import datetime, date, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    GOOGLE_CREDENTIALS_FILE,
    GOOGLE_TOKEN_FILE,
    GOOGLE_CALENDAR_ID,
)
from core import memory, notifier

AGENT_NAME = "calendar_sync"

# Escopos necessários
SCOPES = ["https://www.googleapis.com/auth/calendar"]


# ---------------------------------------------------------------------------
# Autenticação OAuth
# ---------------------------------------------------------------------------

def _get_service():
    """
    Retorna o serviço autenticado da Google Calendar API.
    Requer google-api-python-client e google-auth-oauthlib instalados.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "Instale as dependências: pip install google-api-python-client google-auth-oauthlib"
        )

    creds = None

    # Carrega token salvo
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)

    # Renova ou inicia fluxo OAuth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
                raise RuntimeError(
                    f"Arquivo de credenciais não encontrado: {GOOGLE_CREDENTIALS_FILE}\n"
                    "Baixe o credentials.json do Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Salva token para próximas execuções
        with open(GOOGLE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def authorize() -> bool:
    """Inicia o fluxo de autorização OAuth. Retorna True se bem-sucedido."""
    try:
        _get_service()
        notifier.success("Google Calendar autorizado com sucesso!", AGENT_NAME)
        return True
    except Exception as e:
        notifier.error(f"Erro na autorização: {e}", AGENT_NAME)
        return False


def is_authorized() -> bool:
    """Verifica se já existe um token válido."""
    return os.path.exists(GOOGLE_TOKEN_FILE)


# ---------------------------------------------------------------------------
# Leitura de eventos
# ---------------------------------------------------------------------------

def _parse_event_time(event_time: dict) -> Optional[str]:
    """Extrai string de horário de um evento (dateTime ou date)."""
    if "dateTime" in event_time:
        dt = datetime.fromisoformat(event_time["dateTime"])
        return dt.strftime("%H:%M")
    elif "date" in event_time:
        return "00:00"
    return None


def fetch_today_events() -> list[dict]:
    """
    Busca eventos do calendário de hoje.
    Retorna lista normalizada com time_slot, title, all_day, event_id.
    """
    try:
        service = _get_service()
    except Exception as e:
        notifier.warning(f"Não foi possível conectar ao Google Calendar: {e}", AGENT_NAME)
        return []

    today = date.today()
    time_min = datetime.combine(today, datetime.min.time()).isoformat() + "Z"
    time_max = datetime.combine(today + timedelta(days=1), datetime.min.time()).isoformat() + "Z"

    try:
        result = (
            service.events()
            .list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except Exception as e:
        notifier.error(f"Erro ao buscar eventos: {e}", AGENT_NAME)
        return []

    events = []
    for ev in result.get("items", []):
        start = _parse_event_time(ev.get("start", {}))
        end   = _parse_event_time(ev.get("end", {}))
        time_slot = f"{start}-{end}" if start and end and start != end else (start or "")
        all_day = "dateTime" not in ev.get("start", {})

        events.append({
            "google_event_id": ev["id"],
            "title":     ev.get("summary", "Sem título"),
            "time_slot": time_slot,
            "all_day":   all_day,
            "location":  ev.get("location", ""),
            "description": ev.get("description", ""),
        })

    notifier.info(f"Google Calendar: {len(events)} evento(s) hoje.", AGENT_NAME)
    return events


def fetch_week_events(days_ahead: int = 7) -> list[dict]:
    """Busca eventos dos próximos N dias."""
    try:
        service = _get_service()
    except Exception as e:
        notifier.warning(f"Google Calendar indisponível: {e}", AGENT_NAME)
        return []

    time_min = datetime.now().isoformat() + "Z"
    time_max = (datetime.now() + timedelta(days=days_ahead)).isoformat() + "Z"

    try:
        result = (
            service.events()
            .list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=50,
            )
            .execute()
        )
    except Exception as e:
        notifier.error(f"Erro ao buscar eventos da semana: {e}", AGENT_NAME)
        return []

    events = []
    for ev in result.get("items", []):
        start_raw = ev.get("start", {})
        start_time = _parse_event_time(start_raw)
        end_time   = _parse_event_time(ev.get("end", {}))
        time_slot  = f"{start_time}-{end_time}" if start_time and end_time else (start_time or "")

        event_date = ""
        if "dateTime" in start_raw:
            event_date = datetime.fromisoformat(start_raw["dateTime"]).strftime("%Y-%m-%d")
        elif "date" in start_raw:
            event_date = start_raw["date"]

        events.append({
            "google_event_id": ev["id"],
            "title":     ev.get("summary", "Sem título"),
            "time_slot": time_slot,
            "date":      event_date,
            "all_day":   "dateTime" not in start_raw,
        })

    return events


# ---------------------------------------------------------------------------
# Importar eventos como blocos de agenda
# ---------------------------------------------------------------------------

def import_today_as_blocks(skip_all_day: bool = True) -> int:
    """
    Importa eventos de hoje do Google Calendar como blocos de agenda local.
    Evita duplicatas verificando se já existe um bloco com o mesmo time_slot + título.
    Retorna número de blocos criados.
    """
    events = fetch_today_events()
    if not events:
        return 0

    today = date.today().isoformat()
    existing_blocks = memory.get_today_agenda()
    existing_keys = {
        (b.get("time_slot", ""), b.get("task_title", ""))
        for b in existing_blocks
    }

    created = 0
    for ev in events:
        if skip_all_day and ev.get("all_day"):
            continue

        key = (ev["time_slot"], ev["title"])
        if key in existing_keys:
            continue  # Já existe

        memory.create_agenda_block(
            block_date=today,
            time_slot=ev["time_slot"],
            task_title=ev["title"],
        )
        existing_keys.add(key)
        created += 1
        notifier.info(f"Bloco importado: {ev['time_slot']} — {ev['title']}", AGENT_NAME)

    if created:
        notifier.success(f"{created} evento(s) do Google Calendar importados.", AGENT_NAME)
    else:
        notifier.info("Nenhum evento novo para importar.", AGENT_NAME)

    return created


# ---------------------------------------------------------------------------
# Exportar blocos para o Google Calendar
# ---------------------------------------------------------------------------

def export_block_to_calendar(
    block_date: str,
    time_slot: str,
    task_title: str,
    description: str = "",
) -> Optional[str]:
    """
    Cria um evento no Google Calendar para um bloco de agenda.
    Retorna o Google Event ID ou None em caso de erro.
    """
    try:
        service = _get_service()
    except Exception as e:
        notifier.warning(f"Não foi possível exportar para o Calendar: {e}", AGENT_NAME)
        return None

    # Parseia o time_slot (formato "HH:MM-HH:MM")
    if "-" not in time_slot:
        notifier.warning(f"Formato de time_slot inválido: {time_slot}", AGENT_NAME)
        return None

    start_str, end_str = time_slot.split("-", 1)
    start_dt = datetime.fromisoformat(f"{block_date}T{start_str.strip()}:00")
    end_dt   = datetime.fromisoformat(f"{block_date}T{end_str.strip()}:00")

    # Ajuste de fuso (usa o fuso local via isoformat)
    try:
        import tzlocal  # type: ignore
        local_tz = tzlocal.get_localzone()
        start_dt = start_dt.replace(tzinfo=local_tz)
        end_dt   = end_dt.replace(tzinfo=local_tz)
        tz_str = str(local_tz)
    except ImportError:
        tz_str = "America/Sao_Paulo"

    event_body = {
        "summary": task_title,
        "description": description or "Criado pelo Multiagentes",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz_str},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": tz_str},
    }

    try:
        created = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body).execute()
        event_id = created["id"]
        notifier.success(f"Evento criado no Calendar: '{task_title}' ({time_slot})", AGENT_NAME)
        return event_id
    except Exception as e:
        notifier.error(f"Erro ao criar evento: {e}", AGENT_NAME)
        return None


# ---------------------------------------------------------------------------
# Handoff entry point
# ---------------------------------------------------------------------------

def handle_handoff(payload: dict) -> dict:
    action = payload.get("action", "")
    notifier.agent_event(f"Recebendo handoff: action='{action}'", AGENT_NAME)
    handoff_id = memory.log_handoff("orchestrator", AGENT_NAME, action, payload)

    try:
        result: dict = {}

        if action == "import_today":
            skip_all_day = payload.get("skip_all_day", True)
            count = import_today_as_blocks(skip_all_day=skip_all_day)
            result = {"imported": count, "message": f"{count} evento(s) importados."}

        elif action == "fetch_today":
            events = fetch_today_events()
            result = {"events": events, "count": len(events)}

        elif action == "fetch_week":
            days = payload.get("days_ahead", 7)
            events = fetch_week_events(days_ahead=days)
            result = {"events": events, "count": len(events)}

        elif action == "export_block":
            event_id = export_block_to_calendar(
                block_date=payload["block_date"],
                time_slot=payload["time_slot"],
                task_title=payload["task_title"],
                description=payload.get("description", ""),
            )
            result = {"event_id": event_id, "exported": event_id is not None}

        elif action == "status":
            result = {
                "authorized": is_authorized(),
                "calendar_id": GOOGLE_CALENDAR_ID,
                "credentials_file": GOOGLE_CREDENTIALS_FILE,
                "token_file": GOOGLE_TOKEN_FILE,
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
