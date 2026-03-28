# agents/__init__.py
# Pacote de agentes especialistas.
# Importações lazy para evitar circular imports — importe diretamente nos módulos:
#   from agents import notion_sync
#   from agents import scheduler
#   etc.

__all__ = [
    "calendar_sync",
    "focus_guard",
    "notion_sync",
    "orchestrator",
    "persona_manager",
    "retrospective",
    "scheduler",
    "validator",
]
