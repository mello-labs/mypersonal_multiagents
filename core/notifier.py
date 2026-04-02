# =============================================================================
# core/notifier.py — Sistema de notificações e alertas
# =============================================================================
# Exibe mensagens coloridas no terminal e persiste tudo em arquivo de log.
# Os agentes chamam as funções deste módulo para comunicar eventos.

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from enum import Enum

from config import LOG_FILE, LOG_LEVEL


# ---------------------------------------------------------------------------
# Cores ANSI para terminal (funciona em Linux/macOS; desative no Windows antigo)
# ---------------------------------------------------------------------------
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"


# ---------------------------------------------------------------------------
# Configuração do logger Python padrão
# ---------------------------------------------------------------------------
def _setup_logger() -> logging.Logger:
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("multiagentes")
    if logger.handlers:
        return logger  # Evita duplicar handlers em reimportações

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Handler de arquivo (sem cores)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    # Handler de console (com cores aplicadas manualmente)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))  # já formatado abaixo

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


_logger = _setup_logger()


# ---------------------------------------------------------------------------
# Tipos de notificação
# ---------------------------------------------------------------------------
class NotifLevel(str, Enum):
    INFO    = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR   = "ERROR"
    FOCUS   = "FOCUS"      # Alertas do Focus Guard
    AGENT   = "AGENT"      # Comunicação entre agentes


# Mapeamento nível → cor + ícone
_LEVEL_STYLE: dict[NotifLevel, tuple[str, str]] = {
    NotifLevel.INFO:    (Color.CYAN,    "ℹ"),
    NotifLevel.SUCCESS: (Color.GREEN,   "✓"),
    NotifLevel.WARNING: (Color.YELLOW,  "⚠"),
    NotifLevel.ERROR:   (Color.RED,     "✗"),
    NotifLevel.FOCUS:   (Color.MAGENTA, "🎯"),
    NotifLevel.AGENT:   (Color.BLUE,    "🤖"),
}


# ---------------------------------------------------------------------------
# Função principal de notificação
# ---------------------------------------------------------------------------
def notify(
    message: str,
    level: NotifLevel = NotifLevel.INFO,
    agent: str = "system",
    also_log: bool = True,
) -> None:
    """
    Exibe uma notificação colorida no terminal e (opcionalmente) grava no log.

    Args:
        message:   Texto da mensagem.
        level:     Nível/tipo da notificação.
        agent:     Nome do agente que está notificando.
        also_log:  Se True, grava também no arquivo de log.
    """
    color, icon = _LEVEL_STYLE.get(level, (Color.WHITE, "•"))
    timestamp = datetime.now().strftime("%H:%M:%S")

    # Linha formatada para o terminal
    terminal_line = (
        f"{Color.GRAY}[{timestamp}]{Color.RESET} "
        f"{color}{Color.BOLD}{icon} [{level.value}]{Color.RESET} "
        f"{Color.GRAY}({agent}){Color.RESET} "
        f"{color}{message}{Color.RESET}"
    )

    # Imprime diretamente (sem o logging.StreamHandler duplicar)
    print(terminal_line, flush=True)

    # Grava no arquivo de log (sem cores)
    if also_log:
        log_line = f"[{level.value}] ({agent}) {message}"
        if level == NotifLevel.ERROR:
            _logger.error(log_line)
        elif level == NotifLevel.WARNING:
            _logger.warning(log_line)
        else:
            _logger.info(log_line)


# ---------------------------------------------------------------------------
# Atalhos para cada nível
# ---------------------------------------------------------------------------
def info(message: str, agent: str = "system") -> None:
    notify(message, NotifLevel.INFO, agent)

def success(message: str, agent: str = "system") -> None:
    notify(message, NotifLevel.SUCCESS, agent)

def warning(message: str, agent: str = "system") -> None:
    notify(message, NotifLevel.WARNING, agent)

def error(message: str, agent: str = "system") -> None:
    notify(message, NotifLevel.ERROR, agent)

def focus_alert(message: str, agent: str = "focus_guard") -> None:
    notify(message, NotifLevel.FOCUS, agent)

def agent_event(message: str, agent: str = "orchestrator") -> None:
    notify(message, NotifLevel.AGENT, agent)


# ---------------------------------------------------------------------------
# Notificações nativas — macOS e Alexa
# ---------------------------------------------------------------------------
def mac_push(title: str, message: str, sound: bool = False) -> None:
    """Envia notificação nativa macOS via AppleScript."""
    import subprocess

    if sys.platform != "darwin":
        warning("mac_push ignorado: notificações nativas só funcionam em macOS.", "notifier")
        return

    sound_line = ' sound name "Sosumi"' if sound else ""
    script = f'display notification "{message}" with title "{title}"{sound_line}'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode("utf-8", errors="ignore").strip()
            warning(
                f"mac_push falhou via osascript (code={result.returncode}): {stderr or 'sem stderr'}",
                "notifier",
            )
    except Exception as exc:
        warning(f"mac_push falhou: {exc}", "notifier")


def alexa_announce(message: str) -> None:
    """Dispara anúncio na Alexa. Tenta Voice Monkey primeiro; cai para IFTTT se não configurado."""
    import requests

    vm_token = os.getenv("VOICE_MONKEY_TOKEN", "")
    if vm_token:
        try:
            device = os.getenv("VOICE_MONKEY_DEVICE", "eco-room")
            voice = os.getenv("VOICE_MONKEY_VOICE", "Ricardo")
            response = requests.get(
                "https://api-v2.voicemonkey.io/announcement",
                params={"token": vm_token, "device": device, "text": message, "voice": voice},
                timeout=5,
            )
            if not response.ok:
                warning(
                    f"Voice Monkey falhou ({response.status_code}): {response.text[:160] or 'sem resposta'}",
                    "notifier",
                )
        except Exception as exc:
            warning(f"Voice Monkey falhou: {exc}", "notifier")
        return

    ifttt_key = os.getenv("IFTTT_WEBHOOK_KEY", "")
    if ifttt_key:
        event = os.getenv("IFTTT_ALEXA_EVENT", "neo_alert")
        try:
            response = requests.post(
                f"https://maker.ifttt.com/trigger/{event}/with/key/{ifttt_key}",
                json={"value1": message},
                timeout=5,
            )
            if not response.ok:
                warning(
                    f"IFTTT Alexa falhou ({response.status_code}): {response.text[:160] or 'sem resposta'}",
                    "notifier",
                )
        except Exception as exc:
            warning(f"IFTTT Alexa falhou: {exc}", "notifier")
        return

    warning(
        "Alexa indisponível: configure VOICE_MONKEY_TOKEN ou IFTTT_WEBHOOK_KEY no ambiente.",
        "notifier",
    )


# ---------------------------------------------------------------------------
# Separadores visuais
# ---------------------------------------------------------------------------
def separator(title: str = "", char: str = "─", width: int = 70) -> None:
    """Imprime um separador visual no terminal."""
    if title:
        side = (width - len(title) - 2) // 2
        line = f"{char * side} {title} {char * (width - side - len(title) - 2)}"
    else:
        line = char * width
    print(f"{Color.GRAY}{line}{Color.RESET}", flush=True)


def banner() -> None:
    """Exibe o banner de inicialização do sistema."""
    separator()
    print(f"{Color.CYAN}{Color.BOLD}")
    print("  ███╗   ██╗███████╗ ██████╗ ")
    print("  ████╗  ██║██╔════╝██╔═══██╗")
    print("  ██╔██╗ ██║█████╗  ██║   ██║")
    print("  ██║╚██╗██║██╔══╝  ██║   ██║")
    print("  ██║ ╚████║███████╗╚██████╔╝")
    print("  ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ")
    print(f"        {Color.WHITE}Sistema de Multiagentes — Gestão Pessoal{Color.RESET}")
    separator()
    print(f"{Color.GRAY}  Agentes: Orchestrator · Scheduler · Focus Guard · Notion Sync · Validator{Color.RESET}")
    separator()
    print()


# ---------------------------------------------------------------------------
# Exibição de tabela simples no terminal
# ---------------------------------------------------------------------------
def print_table(headers: list[str], rows: list[list[str]], title: str = "") -> None:
    """Imprime uma tabela formatada no terminal."""
    if title:
        separator(title)

    if not rows:
        print(f"  {Color.GRAY}(nenhum item){Color.RESET}")
        return

    # Calcula largura de cada coluna
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Linha de cabeçalho
    header_line = "  " + "  ".join(
        f"{Color.BOLD}{Color.WHITE}{h:<{col_widths[i]}}{Color.RESET}"
        for i, h in enumerate(headers)
    )
    print(header_line)
    print("  " + "  ".join("─" * w for w in col_widths))

    # Linhas de dados
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            w = col_widths[i] if i < len(col_widths) else 10
            cells.append(f"{str(cell):<{w}}")
        print("  " + "  ".join(cells))

    print()
