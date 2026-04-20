"""
core/sanity_client.py — SHIM NO-OP (Sanity foi removido do stack)

Antes este módulo fazia queries GROQ no Sanity.io para buscar prompts,
personas e configs de agentes. O Sanity foi descontinuado do NEØ stack
(migração para Notion/local YAML como fonte da verdade).

Este arquivo permanece apenas como camada de compatibilidade: preserva a API
pública (`get_prompt`, `get_persona`, `get_agent_config`, ...) retornando os
fallbacks passados pelo caller. Nenhum agente precisa ser reescrito — eles já
foram programados para receber fallbacks hardcoded caso o Sanity estivesse
indisponível.

Quando todos os call-sites forem refatorados para usar fontes locais, este
arquivo pode ser deletado com segurança.
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "get_prompt",
    "get_persona",
    "get_all_personas",
    "get_agent_config",
    "get_agent_parameters",
    "is_agent_enabled",
    "get_intervention_scripts",
    "invalidate_cache",
    "is_configured",
]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


def get_prompt(agent: str, prompt_type: str, fallback: str = "") -> str:
    """No-op: sempre retorna o fallback hardcoded do chamador."""
    return fallback


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------


def get_persona(persona_id: str) -> Optional[dict]:
    """No-op: sem persona externa, persona_manager usa defaults locais."""
    return None


def get_all_personas() -> list:
    """No-op: lista vazia → persona_manager.PERSONAS (local) prevalece."""
    return []


# ---------------------------------------------------------------------------
# Configuração de agentes
# ---------------------------------------------------------------------------


def get_agent_config(agent_name: str) -> Optional[dict]:
    """No-op: sem config externa, agentes usam defaults do .env/código."""
    return None


def get_agent_parameters(agent_name: str) -> dict:
    """No-op: dict vazio → agente usa parâmetros hardcoded."""
    return {}


def is_agent_enabled(agent_name: str, default: bool = True) -> bool:
    """No-op: sempre respeita o `default` do chamador."""
    return default


# ---------------------------------------------------------------------------
# Scripts de intervenção (Focus Guard)
# ---------------------------------------------------------------------------


def get_intervention_scripts(agent_name: Optional[str] = None) -> list:
    """No-op: lista vazia → focus_guard usa ESCALATION_LEVELS hardcoded."""
    return []


# ---------------------------------------------------------------------------
# Cache / status
# ---------------------------------------------------------------------------


def invalidate_cache() -> None:
    """No-op: não há cache para invalidar."""
    return None


def is_configured() -> bool:
    """Sanity foi removido — sempre retorna False."""
    return False


# Sinaliza explicitamente para quem tentar usar como módulo legado
DEPRECATED: bool = True
REMOVED_AT: str = "2026-04"
REPLACED_BY: str = "Notion databases (NEØ Command Center) + persona_manager local"
