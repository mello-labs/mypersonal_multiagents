# =============================================================================
# config.py — Configurações centrais do sistema multiagentes
# =============================================================================
# Carrega variáveis de ambiente e expõe constantes para todos os módulos.
# Nunca coloque credenciais diretamente aqui — use o .env.

import os
from dotenv import load_dotenv
from pathlib import Path

# Carrega o .env localizado na raiz do projeto
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")          # Integration token
NOTION_TASKS_DB_ID: str = os.getenv("NOTION_TASKS_DB_ID", "")   # ID do database "Tarefas"
NOTION_AGENDA_DB_ID: str = os.getenv("NOTION_AGENDA_DB_ID", "")  # ID do database "Agenda Diária"

# URL base da Notion API v1
NOTION_API_BASE: str = "https://api.notion.com/v1"
NOTION_API_VERSION: str = "2022-06-28"

# ---------------------------------------------------------------------------
# Memória / persistência
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
MEMORY_DB_PATH: str = os.getenv("MEMORY_DB_PATH", str(BASE_DIR / "memory.db"))

# ---------------------------------------------------------------------------
# Focus Guard
# ---------------------------------------------------------------------------
# Intervalo (em minutos) entre verificações automáticas do Focus Guard
FOCUS_CHECK_INTERVAL_MINUTES: int = int(os.getenv("FOCUS_CHECK_INTERVAL", "15"))

# ---------------------------------------------------------------------------
# Logging / Notificações
# ---------------------------------------------------------------------------
LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "agent_system.log"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# Validação mínima na importação
# ---------------------------------------------------------------------------
def validate_config() -> list[str]:
    """Retorna lista de avisos para chaves obrigatórias não configuradas."""
    warnings = []
    if not OPENAI_API_KEY:
        warnings.append("OPENAI_API_KEY não configurada — agentes LLM não funcionarão.")
    if not NOTION_TOKEN:
        warnings.append("NOTION_TOKEN não configurada — Notion Sync ficará desabilitado.")
    if not NOTION_TASKS_DB_ID:
        warnings.append("NOTION_TASKS_DB_ID não configurada — sincronização de tarefas desabilitada.")
    if not NOTION_AGENDA_DB_ID:
        warnings.append("NOTION_AGENDA_DB_ID não configurada — sincronização de agenda desabilitada.")
    return warnings
