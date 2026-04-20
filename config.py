# =============================================================================
# config.py — Configurações centrais do sistema multiagentes
# =============================================================================
# Carrega variáveis de ambiente e expõe constantes para todos os módulos.
# Nunca coloque credenciais diretamente aqui — use o .env.
#
# Em Railway: as variáveis vêm do Dashboard → Variables. O .env só é usado
# em dev local (o load_dotenv ignora silenciosamente se o arquivo não existe).

import os
from dotenv import load_dotenv
from pathlib import Path

# Carrega o .env localizado na raiz do projeto (dev local apenas)
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# LLM — OpenAI clássico (legado, mantido p/ rollback)
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_FALLBACK_MODEL: str = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-3.5-turbo")

# ---------------------------------------------------------------------------
# LLM — Azure OpenAI (provider primário)
# ---------------------------------------------------------------------------
# Para ativar, defina AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY + AZURE_OPENAI_DEPLOYMENT.
# openai_utils detecta e prioriza Azure sobre OpenAI público.
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_FALLBACK_DEPLOYMENT: str = os.getenv(
    "AZURE_OPENAI_FALLBACK_DEPLOYMENT", ""
)

# Modelo local via Docker Model Runner (Gemma3 4B) — só em dev local
LOCAL_MODEL_ENABLED: bool = os.getenv("LOCAL_MODEL_ENABLED", "false").lower() == "true"
LOCAL_MODEL_BASE_URL: str = os.getenv(
    "LOCAL_MODEL_BASE_URL", "http://localhost:12434/engines/llama.cpp/v1"
)
LOCAL_MODEL_NAME: str = os.getenv("LOCAL_MODEL_NAME", "docker.io/ai/gemma3:4B-F16")

# Sinal agregado — True se qualquer provider LLM está minimamente configurado
LLM_CONFIGURED: bool = bool(
    (AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT)
    or OPENAI_API_KEY
    or LOCAL_MODEL_ENABLED
)

# ---------------------------------------------------------------------------
# Notion — API + databases do NEØ Command Center (workspace "neoflw")
# ---------------------------------------------------------------------------
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")  # Integration token

# Databases originais (legado multiagents — mantidos p/ compatibilidade)
NOTION_TASKS_DB_ID: str = os.getenv("NOTION_TASKS_DB_ID", "")
NOTION_AGENDA_DB_ID: str = os.getenv("NOTION_AGENDA_DB_ID", "")

# NEØ Command Center — destinos do Capture Agent (segundo cérebro)
NOTION_DB_PROJETOS: str = os.getenv("NOTION_DB_PROJETOS", "")
NOTION_DB_TAREFAS: str = os.getenv("NOTION_DB_TAREFAS", "")
NOTION_DB_DECISOES: str = os.getenv("NOTION_DB_DECISOES", "")
NOTION_DB_WORKLOG: str = os.getenv("NOTION_DB_WORKLOG", "")
NOTION_DB_INTEGRATIONS: str = os.getenv("NOTION_DB_INTEGRATIONS", "")

# URL base da Notion API
NOTION_API_BASE: str = "https://api.notion.com/v1"
NOTION_API_VERSION: str = "2022-06-28"

# ---------------------------------------------------------------------------
# Memória / persistência (Redis — Railway provisiona automaticamente)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
# No Railway use a rede interna: REDIS_URL=redis://default:PASS@redis.railway.internal:6379
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MEMORY_DB_PATH: str = os.getenv("MEMORY_DB_PATH", str(BASE_DIR / "memory.db"))

# ---------------------------------------------------------------------------
# Telegram (captura inbound → Capture Agent)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
# ID(s) autorizados a falar com o bot (comma-separated ints). Vazio = libera todos.
TELEGRAM_ALLOWED_CHAT_IDS: list[int] = [
    int(x.strip())
    for x in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
    if x.strip().lstrip("-").isdigit()
]

# ---------------------------------------------------------------------------
# GitHub Projects v2 (espelho para issues/tarefas de engenharia)
# ---------------------------------------------------------------------------
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")  # PAT com scopes: project, read:org, repo
# Mapeamento org → project number (configurável via env)
GITHUB_PROJECTS: dict[str, int] = {
    "flowpay-system": int(os.getenv("GH_PROJECT_FLOWPAY", "1")),
    "NEO-FlowOFF": int(os.getenv("GH_PROJECT_FLOWOFF", "1")),
    "NEO-PROTOCOL": int(os.getenv("GH_PROJECT_NEO", "1")),
    "neo-smart-factory": int(os.getenv("GH_PROJECT_FACTORY", "1")),
}

# ---------------------------------------------------------------------------
# Focus Guard
# ---------------------------------------------------------------------------
FOCUS_CHECK_INTERVAL_MINUTES: int = int(os.getenv("FOCUS_CHECK_INTERVAL", "15"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "agent_system.log"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# Notion sync interval
# ---------------------------------------------------------------------------
NOTION_SYNC_INTERVAL_MINUTES: int = int(os.getenv("NOTION_SYNC_INTERVAL", "5"))
NOTION_RETROSPECTIVE_PAGE_ID: str = os.getenv("NOTION_RETROSPECTIVE_PAGE_ID", "")

# ---------------------------------------------------------------------------
# Google Calendar (opcional)
# ---------------------------------------------------------------------------
GOOGLE_CREDENTIALS_FILE: str = os.getenv(
    "GOOGLE_CREDENTIALS_FILE", str(BASE_DIR / "credentials.json")
)
GOOGLE_TOKEN_FILE: str = os.getenv("GOOGLE_TOKEN_FILE", str(BASE_DIR / "token.json"))
GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")

# ---------------------------------------------------------------------------
# Web
# ---------------------------------------------------------------------------
WEB_HOST: str = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT: int = int(os.getenv("WEB_PORT", os.getenv("PORT", "8000")))

# Flag de runtime (útil p/ logs)
RUNNING_ON_RAILWAY: bool = bool(os.getenv("RAILWAY_ENVIRONMENT"))


# ---------------------------------------------------------------------------
# Validação mínima
# ---------------------------------------------------------------------------
def validate_config() -> list[str]:
    """Retorna lista de avisos para chaves obrigatórias não configuradas."""
    warnings: list[str] = []
    if not LLM_CONFIGURED:
        warnings.append(
            "Nenhum provider LLM configurado — defina AZURE_OPENAI_* "
            "ou OPENAI_API_KEY ou LOCAL_MODEL_ENABLED=true."
        )
    if not NOTION_TOKEN:
        warnings.append("NOTION_TOKEN não configurada — Notion Sync desabilitado.")
    # Os 5 DBs do Command Center são opcionais individualmente, mas avisa se
    # nenhum deles estiver configurado (capture_agent fica mudo)
    command_center_dbs = [
        NOTION_DB_PROJETOS,
        NOTION_DB_TAREFAS,
        NOTION_DB_DECISOES,
        NOTION_DB_WORKLOG,
        NOTION_DB_INTEGRATIONS,
    ]
    if not any(command_center_dbs):
        warnings.append(
            "Nenhum NOTION_DB_* do Command Center configurado — "
            "Capture Agent não tem destino. Configure ao menos um."
        )
    if not TELEGRAM_BOT_TOKEN:
        warnings.append(
            "TELEGRAM_BOT_TOKEN não configurada — captura via Telegram desabilitada."
        )
    if not GITHUB_TOKEN:
        warnings.append(
            "GITHUB_TOKEN não configurada — espelho GitHub Projects desabilitado."
        )
    return warnings
