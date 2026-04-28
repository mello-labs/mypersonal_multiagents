# =============================================================================
# scheduler/runner.py — Loop de background e registro de jobs periódicos
# =============================================================================
# Responsável por:
#   - Manter o loop `schedule.run_pending()` em background thread
#   - Registrar jobs periódicos de cada agente (notion_sync, ecosystem_monitor,
#     github_projects, retrospective)
#
# O Focus Guard registra apenas o seu próprio job (_run_focus_check).
# Cada agente é responsável apenas por executar sua própria tarefa —
# este módulo cuida do "quando".
#
# Uso:
#   from scheduler.runner import start, stop

import threading
import time

import schedule

from config import (
    FOCUS_CHECK_INTERVAL_MINUTES,
    GITHUB_TOKEN,
    NOTION_SYNC_INTERVAL_MINUTES,
    NOTION_TOKEN,
)
from core import notifier

_RUNNER_NAME = "scheduler.runner"

_stop_event = threading.Event()
_runner_thread: threading.Thread | None = None

_ecosystem_lock = threading.Lock()
_github_lock = threading.Lock()
_retrospective_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fire_and_forget(fn, lock: threading.Lock, name: str) -> None:
    """Dispara fn em thread daemon com lock anti-overlap."""
    if not lock.acquire(blocking=False):
        notifier.info(f"{name} ainda em execução — pulando rodada.", _RUNNER_NAME)
        return

    def _run():
        try:
            fn()
        except Exception as e:
            notifier.warning(f"Erro em {name}: {e}", _RUNNER_NAME)
        finally:
            lock.release()

    threading.Thread(target=_run, name=name, daemon=True).start()


# ---------------------------------------------------------------------------
# Jobs periódicos registrados por este módulo
# ---------------------------------------------------------------------------


def _run_differential_sync() -> None:
    """Sync diferencial Notion → local a cada NOTION_SYNC_INTERVAL_MINUTES minutos."""
    try:
        from agents import notion_sync
        count = notion_sync.sync_differential()
        if count:
            notifier.info(f"Auto-sync: {count} tarefa(s) sincronizada(s).", _RUNNER_NAME)
    except Exception as e:
        notifier.warning(f"Erro no auto-sync diferencial: {e}", _RUNNER_NAME)


def _run_ecosystem_check() -> None:
    """Health check do ecossistema (Railway, GitHub, on-chain) a cada 60 min."""
    def _do():
        from agents import ecosystem_monitor
        ecosystem_monitor.run()
    _fire_and_forget(_do, _ecosystem_lock, "ecosystem_monitor")


def _run_github_sync() -> None:
    """Sync GitHub Projects → Notion a cada 30 min."""
    if not NOTION_TOKEN or not GITHUB_TOKEN:
        notifier.info(
            "github_sync ignorado: NOTION_TOKEN ou GITHUB_TOKEN ausente.", _RUNNER_NAME
        )
        return

    def _do():
        from agents import github_projects
        github_projects.sync_all_orgs(dry_run=False)
    _fire_and_forget(_do, _github_lock, "github_projects")


def _run_retrospective() -> None:
    """Retrospectiva semanal toda segunda-feira às 21h."""
    def _do():
        from agents import retrospective
        retrospective.run_retrospective(push_to_notion=True)
    _fire_and_forget(_do, _retrospective_lock, "retrospective")


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------


def _loop(focus_check_fn) -> None:
    """
    Loop de background.

    Args:
        focus_check_fn: Callable do Focus Guard a chamar periodicamente.
    """
    schedule.every(FOCUS_CHECK_INTERVAL_MINUTES).minutes.do(focus_check_fn)
    schedule.every(NOTION_SYNC_INTERVAL_MINUTES).minutes.do(_run_differential_sync)
    schedule.every(60).minutes.do(_run_ecosystem_check)
    schedule.every(30).minutes.do(_run_github_sync)
    schedule.every().monday.at("21:00").do(_run_retrospective)

    # Check imediato ao iniciar
    try:
        focus_check_fn()
    except Exception as e:
        notifier.warning(
            f"Check inicial ignorado (Redis indisponível?): {e}", _RUNNER_NAME
        )

    while not _stop_event.is_set():
        try:
            schedule.run_pending()
        except Exception as e:
            notifier.warning(f"Erro no runner (ignorado): {e}", _RUNNER_NAME)
        time.sleep(30)

    notifier.info("Background runner encerrado.", _RUNNER_NAME)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def start(focus_check_fn) -> None:
    """
    Inicia o loop de background em daemon thread.

    Args:
        focus_check_fn: Callable do Focus Guard a registrar como job periódico.
    """
    global _runner_thread
    if _runner_thread and _runner_thread.is_alive():
        notifier.warning("Background runner já está rodando.", _RUNNER_NAME)
        return

    _stop_event.clear()
    _runner_thread = threading.Thread(
        target=_loop,
        args=(focus_check_fn,),
        name="BackgroundRunnerThread",
        daemon=True,
    )
    _runner_thread.start()
    notifier.success(
        f"Background runner iniciado (focus check a cada {FOCUS_CHECK_INTERVAL_MINUTES} min).",
        _RUNNER_NAME,
    )


def stop() -> None:
    """Para o loop de background e limpa os jobs agendados."""
    _stop_event.set()
    schedule.clear()
    notifier.info("Background runner parado.", _RUNNER_NAME)
