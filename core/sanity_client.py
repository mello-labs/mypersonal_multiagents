"""
core/sanity_client.py — Cliente Sanity.io com cache em memória

Usa a Content API do Sanity para buscar prompts, personas e configs.
Cache de 5 minutos evita requests repetitivos.
Fallback para valores hardcoded se Sanity estiver indisponível ou não configurado.
"""

import os
import time
from typing import Any, Optional

import requests

SANITY_PROJECT_ID: str = os.getenv("SANITY_PROJECT_ID", "")
SANITY_DATASET: str    = os.getenv("SANITY_DATASET", "production")
SANITY_API_TOKEN: str  = os.getenv("SANITY_API_TOKEN", "")
SANITY_CDN: bool       = os.getenv("SANITY_USE_CDN", "false").lower() == "true"

_CACHE: dict[str, tuple[Any, float]] = {}
CACHE_TTL = 300  # 5 minutos


# ---------------------------------------------------------------------------
# GROQ query
# ---------------------------------------------------------------------------


def _query(groq: str) -> Any:
    """Executa uma query GROQ na Content API do Sanity."""
    if not SANITY_PROJECT_ID:
        return None

    if groq in _CACHE:
        value, ts = _CACHE[groq]
        if time.time() - ts < CACHE_TTL:
            return value

    host = "apicdn.sanity.io" if SANITY_CDN else "api.sanity.io"
    url = f"https://{host}/v2021-10-21/data/query/{SANITY_DATASET}"
    headers = {}
    if SANITY_API_TOKEN:
        headers["Authorization"] = f"Bearer {SANITY_API_TOKEN}"

    try:
        resp = requests.get(
            url,
            params={"query": groq},
            headers=headers,
            timeout=5,
        )
        if resp.ok:
            result = resp.json().get("result")
            _CACHE[groq] = (result, time.time())
            return result
    except Exception:
        pass  # nunca quebra o sistema por Sanity indisponível

    return None


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


def get_prompt(agent: str, prompt_type: str, fallback: str = "") -> str:
    """
    Busca system prompt de um agente no Sanity.
    Retorna fallback se Sanity não estiver configurado ou indisponível.

    Uso:
        prompt = sanity_client.get_prompt("focus_guard", "deviation", DEVIATION_PROMPT)
    """
    result = _query(
        f'*[_type == "llm_prompt" && agent == "{agent}" '
        f'&& prompt_type == "{prompt_type}" && active == true][0].system_prompt'
    )
    return result if result else fallback


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------


def get_persona(persona_id: str) -> Optional[dict]:
    """Busca uma persona completa pelo ID."""
    return _query(
        f'*[_type == "persona" && persona_id.current == "{persona_id}" && active == true][0]'
    )


def get_all_personas() -> list:
    """Lista todas as personas ativas."""
    return _query('*[_type == "persona" && active == true]') or []


# ---------------------------------------------------------------------------
# Configuração de agentes
# ---------------------------------------------------------------------------


def get_agent_config(agent_name: str) -> Optional[dict]:
    """Busca configuração de um agente (intervalo, enabled, parâmetros)."""
    return _query(
        f'*[_type == "agent_config" && agent_name == "{agent_name}"][0]'
    )


def get_agent_parameters(agent_name: str) -> dict:
    """
    Retorna os parâmetros do agent_config como dict Python.
    O campo `parameters` é armazenado como JSON string no Sanity.
    Retorna {} se o agente não existir ou não tiver parâmetros.
    """
    import json as _json
    cfg = get_agent_config(agent_name)
    if not cfg:
        return {}
    raw = cfg.get("parameters") or ""
    if not raw:
        return {}
    try:
        return _json.loads(raw)
    except Exception:
        return {}


def is_agent_enabled(agent_name: str, default: bool = True) -> bool:
    """
    Retorna se um agente está habilitado no Sanity.
    Usa `default` se o Sanity não estiver configurado ou o agente não existir.
    """
    cfg = get_agent_config(agent_name)
    if cfg is None:
        return default
    return bool(cfg.get("enabled", default))


# ---------------------------------------------------------------------------
# Scripts de intervenção (Focus Guard / escalada)
# ---------------------------------------------------------------------------


def get_intervention_scripts(agent_name: Optional[str] = None) -> list:
    """
    Lista scripts de intervenção ordenados por trigger_minutes.
    Usado pelo Focus Guard para substituir o ESCALATION_LEVELS hardcoded.
    """
    agent_filter = f' && agent_name == "{agent_name}"' if agent_name else ""
    return _query(
        f'*[_type == "intervention_script" && active == true{agent_filter}] | order(trigger_minutes asc)'
    ) or []


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def invalidate_cache() -> None:
    """Limpa o cache — chamar após editar conteúdo no Studio."""
    _CACHE.clear()


def is_configured() -> bool:
    """Retorna True se as variáveis mínimas do Sanity estão definidas."""
    return bool(SANITY_PROJECT_ID and SANITY_API_TOKEN)
