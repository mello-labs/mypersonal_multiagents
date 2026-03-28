# =============================================================================
# core/openai_utils.py — Helper OpenAI com fallback para modelo de contingência
# =============================================================================

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_FALLBACK_MODEL
from core import notifier

# Cliente único para todo o projeto
_client = OpenAI(api_key=OPENAI_API_KEY)


def _apply_model(kwargs: dict, model: str) -> dict:
    payload = kwargs.copy()
    payload["model"] = model
    return payload


def chat_completions(**kwargs):
    """Executa chat.completions.create com fallback de modelo."""
    primary = OPENAI_MODEL
    fallback = OPENAI_FALLBACK_MODEL

    # Tenta primeira vez com modelo principal
    try:
        return _client.chat.completions.create(**_apply_model(kwargs, primary))
    except Exception as primary_exc:
        notifier.warning(
            f"OpenAI primary model '{primary}' falhou: {primary_exc}. Tentando fallback '{fallback}'...",
            "openai_utils",
        )
        if not fallback or fallback == primary:
            raise

        try:
            return _client.chat.completions.create(**_apply_model(kwargs, fallback))
        except Exception as fallback_exc:
            notifier.error(
                f"OpenAI fallback model '{fallback}' também falhou: {fallback_exc}.",
                "openai_utils",
            )
            raise
