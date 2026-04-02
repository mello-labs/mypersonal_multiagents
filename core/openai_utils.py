# =============================================================================
# core/openai_utils.py — Helper OpenAI com fallback para modelo de contingência
# =============================================================================
# Cadeia de fallback:
#   1. OpenAI (OPENAI_MODEL, ex: gpt-4o-mini)
#   2. OpenAI fallback (OPENAI_FALLBACK_MODEL, ex: gpt-3.5-turbo)
#   3. Local — Docker Model Runner (Gemma3 4B-F16 em http://localhost:12434/v1)

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_FALLBACK_MODEL,
    LOCAL_MODEL_ENABLED,
    LOCAL_MODEL_BASE_URL,
    LOCAL_MODEL_NAME,
)
from core import notifier

# Cliente OpenAI cloud
_client = OpenAI(api_key=OPENAI_API_KEY)

# Cliente local (Docker Model Runner via Unix socket) — criado sob demanda
_local_client: OpenAI | None = None

_DOCKER_SOCKET = (
    "/Users/nettomello/Library/Containers/com.docker.docker/Data/inference.sock"
)


def _get_local_client() -> OpenAI:
    global _local_client
    if _local_client is None:
        try:
            import httpx
            transport = httpx.HTTPTransport(uds=_DOCKER_SOCKET)
            http_client = httpx.Client(transport=transport)
            _local_client = OpenAI(
                base_url="http://localhost/v1",
                api_key="local",
                http_client=http_client,
            )
        except Exception:
            # Fallback TCP caso o socket não exista (Railway, etc.)
            _local_client = OpenAI(base_url=LOCAL_MODEL_BASE_URL, api_key="local")
    return _local_client


def _apply_model(kwargs: dict, model: str) -> dict:
    payload = kwargs.copy()
    payload["model"] = model
    return payload


def chat_completions(**kwargs):
    """Executa chat.completions.create com cadeia de fallback:
    OpenAI primary → OpenAI fallback → Gemma3 local (Docker Model Runner).
    """
    primary = OPENAI_MODEL
    fallback = OPENAI_FALLBACK_MODEL

    # 1. Modelo principal (OpenAI cloud)
    try:
        return _client.chat.completions.create(**_apply_model(kwargs, primary))
    except Exception as primary_exc:
        notifier.warning(
            f"OpenAI '{primary}' falhou: {primary_exc}. Tentando fallback '{fallback}'...",
            "openai_utils",
        )

    # 2. Fallback OpenAI cloud
    if fallback and fallback != primary:
        try:
            return _client.chat.completions.create(**_apply_model(kwargs, fallback))
        except Exception as fallback_exc:
            notifier.warning(
                f"OpenAI fallback '{fallback}' falhou: {fallback_exc}.",
                "openai_utils",
            )

    # 3. Fallback local — Gemma3 via Docker Model Runner
    if LOCAL_MODEL_ENABLED:
        notifier.warning(
            f"Tentando modelo local '{LOCAL_MODEL_NAME}' via Docker Model Runner...",
            "openai_utils",
        )
        try:
            return _get_local_client().chat.completions.create(
                **_apply_model(kwargs, LOCAL_MODEL_NAME)
            )
        except Exception as local_exc:
            notifier.error(
                f"Modelo local '{LOCAL_MODEL_NAME}' também falhou: {local_exc}.",
                "openai_utils",
            )
            raise

    raise RuntimeError("Todos os modelos falharam e LOCAL_MODEL_ENABLED=false.")
