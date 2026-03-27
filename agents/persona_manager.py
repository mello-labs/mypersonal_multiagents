# =============================================================================
# agents/persona_manager.py — Gerenciador de identidades/personas
# =============================================================================
# Carrega personas de personas/*.json e fornece a persona ativa para o
# orchestrator compor prompts dinamicamente.
#
# Uso:
#   from agents.persona_manager import get_persona, list_personas, set_active_persona

import json
import os
from pathlib import Path
from typing import Optional

_PERSONAS_DIR = Path(__file__).parent.parent / "personas"
_DEFAULT_PERSONA_ID = "coordinator"

# Cache em memória
_personas: dict[str, dict] = {}
_active_persona_id: str = _DEFAULT_PERSONA_ID


def _load_personas() -> None:
    """Carrega todas as personas do diretório personas/."""
    global _personas
    _personas.clear()
    if not _PERSONAS_DIR.exists():
        return
    for filepath in sorted(_PERSONAS_DIR.glob("*.json")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                persona = json.load(f)
            pid = persona.get("id", filepath.stem)
            persona["id"] = pid
            _personas[pid] = persona
        except (json.JSONDecodeError, OSError) as e:
            print(f"[persona_manager] Erro ao carregar {filepath.name}: {e}")


def _ensure_loaded() -> None:
    if not _personas:
        _load_personas()


def reload_personas() -> None:
    """Força recarga das personas do disco."""
    _load_personas()


def list_personas() -> list[dict]:
    """Retorna lista resumida de todas as personas disponíveis."""
    _ensure_loaded()
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "short_name": p.get("short_name", p["name"][:6]),
            "icon": p.get("icon", "●"),
            "description": p.get("description", ""),
            "tone": p.get("tone", "neutral"),
        }
        for p in _personas.values()
    ]


def get_persona(persona_id: Optional[str] = None) -> dict:
    """Retorna a persona completa pelo ID, ou a persona ativa."""
    _ensure_loaded()
    pid = persona_id or _active_persona_id
    persona = _personas.get(pid)
    if not persona:
        # Fallback para a default
        persona = _personas.get(_DEFAULT_PERSONA_ID, {})
    return persona


def get_active_persona_id() -> str:
    """Retorna o ID da persona ativa globalmente."""
    return _active_persona_id


def set_active_persona(persona_id: str) -> bool:
    """Define a persona ativa. Retorna True se persona existe."""
    global _active_persona_id
    _ensure_loaded()
    if persona_id in _personas:
        _active_persona_id = persona_id
        return True
    return False


def get_system_prompt(persona_id: Optional[str] = None) -> str:
    """Retorna o system prompt da persona."""
    persona = get_persona(persona_id)
    return persona.get("system_prompt", "")


def get_synthesis_prompt(persona_id: Optional[str] = None) -> str:
    """Retorna o prompt de síntese customizado ou o padrão."""
    persona = get_persona(persona_id)
    return persona.get("synthesis_prompt_override", "")


def get_direct_prompt(persona_id: Optional[str] = None) -> str:
    """Retorna o prompt de resposta direta customizado."""
    persona = get_persona(persona_id)
    return persona.get("direct_prompt_override", "")


def get_temperature(persona_id: Optional[str] = None, phase: str = "direct") -> float:
    """Retorna a temperature para uma fase específica (routing, synthesis, direct)."""
    persona = get_persona(persona_id)
    params = persona.get("parameters", {})
    key = f"temperature_{phase}"
    defaults = {"temperature_routing": 0.2, "temperature_synthesis": 0.5, "temperature_direct": 0.7}
    return params.get(key, defaults.get(key, 0.5))
