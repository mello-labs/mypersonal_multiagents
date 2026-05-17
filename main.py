#!/usr/bin/env python3
# =============================================================================
# main.py — Entry point CLI do sistema de multiagentes
# =============================================================================
# Uso:
#   python main.py                    → modo interativo (REPL)
#   python main.py chat               → modo interativo (equivalente)
#   python main.py status             → exibe status do sistema
#   python main.py sync               → sincroniza com Linear
#   python main.py add-task           → wizard para adicionar tarefa
#   python main.py agenda             → exibe agenda de hoje
#   python main.py focus start <id>   → inicia sessão de foco
#   python main.py focus end          → encerra sessão de foco ativa
#   python main.py validate <id>      → valida tarefa como concluída
#   python main.py tasks              → lista todas as tarefas
#   python main.py demo               → cria dados de demonstração

import atexit
import os
import signal
import sys

# Garante que o diretório raiz está no sys.path (script standalone)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import focus_guard
from cli.commands import (
    build_parser,
    cmd_add_task,
    cmd_agenda,
    cmd_capture,
    cmd_chat,
    cmd_classify,
    cmd_demo,
    cmd_focus_end,
    cmd_focus_start,
    cmd_github,
    cmd_status,
    cmd_suggest_agenda,
    cmd_tasks,
    cmd_validate,
    cmd_web,
)
from config import validate_config
from core import memory, notifier


# ---------------------------------------------------------------------------
# Setup e teardown
# ---------------------------------------------------------------------------


def _startup() -> None:
    """Inicializa o sistema: banco de dados, validação de config, banner."""
    notifier.banner()
    memory.init_db()
    if warnings := validate_config():
        notifier.separator("AVISOS DE CONFIGURAÇÃO")
        for w in warnings:
            notifier.warning(w)
        notifier.separator()
        print()


def _shutdown() -> None:
    """Garante encerramento limpo."""
    notifier.info("Encerrando sistema...", "main")
    focus_guard.stop_guard()


def _handle_sigint(sig, frame) -> None:
    """Captura Ctrl+C para encerramento gracioso."""
    print()
    notifier.info("Interrompido pelo usuário (Ctrl+C).", "main")
    _shutdown()
    sys.exit(0)


def cmd_daemon() -> None:
    """Inicia o Focus Guard em background thread e bloqueia até SIGTERM/SIGINT."""
    import time as _time

    _startup()
    focus_guard.start_guard()
    notifier.success("Daemon iniciado. Aguardando sinais...", "daemon")
    try:
        while True:
            _time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        focus_guard.stop_guard()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)
    atexit.register(_shutdown)

    _startup()

    parser = build_parser()
    args = parser.parse_args()

    command = args.command or "chat"  # Padrão: modo interativo

    if command == "chat":
        cmd_chat()
    elif command == "status":
        cmd_status()
    elif command == "agenda":
        cmd_agenda()
    elif command == "tasks":
        cmd_tasks()
    elif command == "add-task":
        cmd_add_task()
    elif command == "suggest":
        cmd_suggest_agenda()
    elif command == "focus":
        if args.focus_action == "start":
            cmd_focus_start(getattr(args, "task_id", None))
        elif args.focus_action == "end":
            cmd_focus_end()
        else:
            notifier.error("Use: python main.py focus [start|end]", "main")
    elif command == "validate":
        cmd_validate(getattr(args, "task_id", None))
    elif command == "demo":
        cmd_demo()
    elif command == "ecosistema":
        from agents import ecosystem_monitor
        report = ecosystem_monitor.run()
        print(report)
    elif command == "github":
        cmd_github(args)
    elif command == "capture":
        cmd_capture(" ".join(getattr(args, "text", []) or []))
    elif command == "classify":
        cmd_classify(" ".join(getattr(args, "text", []) or []))
    elif command == "telegram":
        from agents import telegram_bot
        telegram_bot.run()
    elif command == "daemon":
        cmd_daemon()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
