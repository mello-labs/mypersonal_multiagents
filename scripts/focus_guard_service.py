#!/usr/bin/env python3
"""
Focus Guard — serviço standalone para launchd (macOS) ou systemd (Linux).

Roda o loop do background runner na main thread (sem daemon thread).
O SO mantém o processo vivo e o reinicia automaticamente se cair.

Uso direto:
    python3 scripts/focus_guard_service.py

Instalar como serviço no macOS (launchd):
    bash scripts/install_launchd.sh

Instalar como serviço no Linux (systemd):
    bash scripts/install_systemd.sh
"""

import sys
import os
import signal
import logging

# Garante que o projeto está no path independente de onde o script é chamado
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core import memory  # noqa: E402
from agents import focus_guard  # noqa: E402
from scheduler import runner  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FocusGuard] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _handle_signal(signum, frame):
    log.info(f"Sinal {signum} recebido — encerrando graciosamente...")
    runner.stop()
    sys.exit(0)


if __name__ == "__main__":
    log.info(f"Iniciando Focus Guard Service (PID: {os.getpid()})")
    log.info(f"Projeto: {PROJECT_ROOT}")

    memory.init_db()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Roda o loop diretamente na main thread
    # (launchd/systemd gerenciam restart — não precisa de daemon thread)
    runner._loop(focus_guard._run_focus_check)

