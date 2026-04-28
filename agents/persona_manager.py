# =============================================================================
# agents/persona_manager.py — Gerenciador de identidades/personas
# =============================================================================
# Carrega personas de personas/*.json e fornece a persona ativa para o
# orchestrator compor prompts dinamicamente.
#
# Uso:
#   from agents.persona_manager import get_persona, list_personas, set_active_persona

import json
from pathlib import Path
from typing import Optional


from core import memory, notifier

_PERSONAS_DIR = Path(__file__).parent.parent / "personas"
_DEFAULT_PERSONA_ID = "coordinator"

# Cache em memória
_personas: dict[str, dict] = {}
_active_persona_id: str = _DEFAULT_PERSONA_ID


def _normalize_persona(source: dict, fallback_id: str) -> dict:
    persona_id = (
        source.get("id")
        or source.get("persona_id", {}).get("current")
        or source.get("persona_id")
        or fallback_id
    )
    params = source.get("parameters") or {}
    if not params:
        params = {
            "temperature_routing": source.get("temperature_routing", 0.2),
            "temperature_synthesis": source.get("temperature_synthesis", 0.5),
            "temperature_direct": source.get("temperature_direct", 0.7),
        }

    return {
        "id": persona_id,
        "name": source.get("name", fallback_id),
        "short_name": source.get("short_name", source.get("name", fallback_id)[:6]),
        "icon": source.get("icon", "●"),
        "description": source.get("description", ""),
        "tone": source.get("tone", "neutral"),
        "language": source.get("language", "pt-BR"),
        "system_prompt": source.get("system_prompt", ""),
        "synthesis_prompt_override": source.get("synthesis_prompt_override", ""),
        "direct_prompt_override": source.get("direct_prompt_override", ""),
        "preferred_model": source.get("preferred_model", ""),
        "role": source.get("role", ""),
        "parameters": params,
        "active": source.get("active", True),
    }


def _load_personas_from_disk() -> dict[str, dict]:
    personas: dict[str, dict] = {}
    if not _PERSONAS_DIR.exists():
        return personas
    for filepath in sorted(_PERSONAS_DIR.glob("*.json")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                persona = json.load(f)
            pid = persona.get("id", filepath.stem)
            personas[pid] = _normalize_persona(persona, pid)
        except (json.JSONDecodeError, OSError) as e:
            notifier.error(f"Erro ao carregar {filepath.name}: {e}", "persona_manager")
    return personas


def _load_personas() -> None:
    """Carrega personas do disco."""
    global _personas
    disk_personas = _load_personas_from_disk()
    _personas.clear()
    _personas.update(disk_personas)
    global _active_persona_id
    # Restaura a persona ativa do Redis (sobrevive a restarts do servidor)
    try:
        saved = memory.get_state("active_persona_id")
        if saved and saved in _personas:
            _active_persona_id = saved
    except Exception:
        pass
    if _active_persona_id not in _personas:
        _active_persona_id = (
            _DEFAULT_PERSONA_ID
            if _DEFAULT_PERSONA_ID in _personas
            else next(iter(_personas), _DEFAULT_PERSONA_ID)
        )


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
    """Define a persona ativa. Persiste no Redis para sobreviver a restarts."""
    global _active_persona_id
    _ensure_loaded()
    if persona_id in _personas:
        _active_persona_id = persona_id
        try:
            memory.set_state("active_persona_id", persona_id)
        except Exception:
            pass  # nunca falha por Redis indisponível
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
    defaults = {
        "temperature_routing": 0.2,
        "temperature_synthesis": 0.5,
        "temperature_direct": 0.7,
    }
    return params.get(key, defaults.get(key, 0.5))
