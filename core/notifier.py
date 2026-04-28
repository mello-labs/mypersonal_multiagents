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
# Cores ANSI para terminal (Linux/macOS; desative no Windows antigo)
# ---------------------------------------------------------------------------
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


_IS_RAILWAY = bool(
    os.getenv("RAILWAY_ENVIRONMENT")
    or os.getenv("RAILWAY_PROJECT_ID")
    or os.getenv("RAILWAY_SERVICE_ID")
)
_FORCE_COLOR = os.getenv("FORCE_COLOR", "").lower() in {"1", "true", "yes"}
_NO_COLOR = os.getenv("NO_COLOR") is not None
_USE_COLOR = _FORCE_COLOR or (
    sys.stdout.isatty() and not _NO_COLOR and not _IS_RAILWAY
)


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

    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


_logger = _setup_logger()


# ---------------------------------------------------------------------------
# Tipos de notificação
# ---------------------------------------------------------------------------
class NotifLevel(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FOCUS = "FOCUS"  # Alertas do Focus Guard
    AGENT = "AGENT"  # Comunicação entre agentes


# Mapeamento nível → cor + ícone
_LEVEL_STYLE: dict[NotifLevel, tuple[str, str]] = {
    NotifLevel.INFO: (Color.CYAN, "ℹ"),
    NotifLevel.SUCCESS: (Color.GREEN, "✓"),
    NotifLevel.WARNING: (Color.YELLOW, "⚠"),
    NotifLevel.ERROR: (Color.RED, "✗"),
    NotifLevel.FOCUS: (Color.MAGENTA, "🎯"),
    NotifLevel.AGENT: (Color.BLUE, "🤖"),
}

_LEVEL_PLAIN_ICON: dict[NotifLevel, str] = {
    NotifLevel.INFO: "i",
    NotifLevel.SUCCESS: "ok",
    NotifLevel.WARNING: "warn",
    NotifLevel.ERROR: "err",
    NotifLevel.FOCUS: "focus",
    NotifLevel.AGENT: "agent",
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

    if _USE_COLOR:
        terminal_line = (
            f"{Color.GRAY}[{timestamp}]{Color.RESET} "
            f"{color}{Color.BOLD}{icon} [{level.value}]{Color.RESET} "
            f"{Color.GRAY}({agent}){Color.RESET} "
            f"{color}{message}{Color.RESET}"
        )
    else:
        plain_icon = _LEVEL_PLAIN_ICON.get(level, "log")
        terminal_line = f"[{timestamp}] [{plain_icon.upper()}] ({agent}) {message}"

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
    """Envia notificação nativa macOS. Delegado a notifications/channels.py."""
    from notifications.channels import mac_push as _mac_push
    _mac_push(title, message, sound)


def alexa_announce(message: str) -> None:
    """Dispara anúncio na Alexa via Voice Monkey. Delegado a notifications/channels.py."""
    from notifications.channels import alexa_announce as _alexa_announce
    _alexa_announce(message)


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
    if _USE_COLOR:
        print(f"{Color.GRAY}{line}{Color.RESET}", flush=True)
    else:
        print(line, flush=True)


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
    print(
        f"{Color.GRAY}  Agentes: Orchestrator · Scheduler · Focus Guard · "
        f"Notion Sync · Validator{Color.RESET}"
    )
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
