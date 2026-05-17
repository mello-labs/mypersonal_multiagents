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
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

# ---------------------------------------------------------------------------
# LLM — Azure OpenAI (NEOone, provider primário)
# ---------------------------------------------------------------------------
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-oss-120b")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

# ---------------------------------------------------------------------------
# LLM — OpenAI público (fallback cloud)
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_FALLBACK_MODEL: str = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-3.5-turbo")

# Modelo local via Docker Model Runner (Gemma3 4B) — fallback dev local
LOCAL_MODEL_ENABLED: bool = os.getenv("LOCAL_MODEL_ENABLED", "false").lower() == "true"
LOCAL_MODEL_BASE_URL: str = os.getenv(
    "LOCAL_MODEL_BASE_URL", "http://localhost:12434/engines/llama.cpp/v1"
)
LOCAL_MODEL_NAME: str = os.getenv("LOCAL_MODEL_NAME", "docker.io/ai/gemma3:4B-F16")

# Sinal agregado — True se qualquer provider LLM está minimamente configurado
LLM_CONFIGURED: bool = bool(
    (AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT)
    or OPENAI_API_KEY
    or LOCAL_MODEL_ENABLED
)

# ---------------------------------------------------------------------------
# Notion — NEØ Command Center (destino de captura — capture_agent, github_projects)
# ---------------------------------------------------------------------------
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
NOTION_DB_PROJETOS: str = os.getenv("NOTION_DB_PROJETOS", "")
NOTION_DB_TAREFAS: str = os.getenv("NOTION_DB_TAREFAS", "")
NOTION_DB_DECISOES: str = os.getenv("NOTION_DB_DECISOES", "")
NOTION_DB_WORKLOG: str = os.getenv("NOTION_DB_WORKLOG", "")
NOTION_DB_INTEGRATIONS: str = os.getenv("NOTION_DB_INTEGRATIONS", "")

# URL base da Notion API
NOTION_API_BASE: str = "https://api.notion.com/v1"
NOTION_API_VERSION: str = "2022-06-28"

# ---------------------------------------------------------------------------
# Redis — fonte de verdade para estado operacional (Railway provisiona)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
# No Railway use a rede interna: REDIS_URL=redis://default:PASS@redis.railway.internal:6379
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

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
# Linear (tracking de issues de engenharia)
# ---------------------------------------------------------------------------
LINEAR_API_KEY: str = os.getenv("LINEAR_API_KEY", "")
LINEAR_TEAM_ID: str = os.getenv("LINEAR_TEAM_ID", "")

# ---------------------------------------------------------------------------
# GitHub Projects v2 (espelho GitHub → Notion DB)
# ---------------------------------------------------------------------------
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")  # PAT com scopes: project, read:org, repo
GITHUB_PROJECTS: dict[str, int] = {
    "flowpay-system": int(os.getenv("GH_PROJECT_FLOWPAY", "1")),
    "NEO-FlowOFF": int(os.getenv("GH_PROJECT_FLOWOFF", "1")),
    "NEO-PROTOCOL": int(os.getenv("GH_PROJECT_NEO", "1")),
    "neo-smart-factory": int(os.getenv("GH_PROJECT_FACTORY", "1")),
}

# GitHub Projects — Notion field mappings (configurável se o schema mudar)
GITHUB_NOTION_STATUS_OPEN: str = os.getenv("GITHUB_NOTION_STATUS_OPEN", "📋 Backlog")
GITHUB_NOTION_STATUS_CLOSED: str = os.getenv("GITHUB_NOTION_STATUS_CLOSED", "✅ Concluído")
GITHUB_NOTION_PRIORITY_DEFAULT: str = os.getenv("GITHUB_NOTION_PRIORITY_DEFAULT", "⚡ Média")

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
# Railway (ecosystem monitor)
# ---------------------------------------------------------------------------
RAILWAY_TOKEN: str = os.getenv("RAILWAY_TOKEN", "")
RAILWAY_WORKSPACE_ID: str = os.getenv("RAILWAY_WORKSPACE_ID", "")
RUNNING_ON_RAILWAY: bool = bool(os.getenv("RAILWAY_ENVIRONMENT"))

# ---------------------------------------------------------------------------
# Workspace root (github discover)
# ---------------------------------------------------------------------------
NEOMELLO_WORKSPACES_ROOT: str = os.getenv(
    "NEOMELLO_WORKSPACES_ROOT", "/Users/nettomello/neomello"
)


# ---------------------------------------------------------------------------
# Validação mínima
# ---------------------------------------------------------------------------
def validate_config() -> list[str]:
    """Retorna lista de avisos para chaves obrigatórias não configuradas."""
    warnings: list[str] = []
    if not LLM_CONFIGURED:
        warnings.append(
            "Nenhum provider LLM configurado — defina AZURE_OPENAI_API_KEY + "
            "AZURE_OPENAI_ENDPOINT, ou OPENAI_API_KEY, ou LOCAL_MODEL_ENABLED=true."
        )
    if not NOTION_TOKEN:
        warnings.append(
            "NOTION_TOKEN não configurada — capture_agent e github_projects desabilitados."
        )
    if not LINEAR_API_KEY:
        warnings.append(
            "LINEAR_API_KEY não configurada — linear_sync desabilitado."
        )
    if not LINEAR_TEAM_ID:
        warnings.append(
            "LINEAR_TEAM_ID não configurada — linear_sync não sabe em qual time criar issues."
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
