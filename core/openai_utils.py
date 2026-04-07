# =============================================================================
# core/openai_utils.py — Cadeia de fallback para modelos LLM
# =============================================================================
# Ordem de tentativa:
#   1. OpenAI cloud   → OPENAI_MODEL          (ex: gpt-4o-mini)
#   2. OpenAI cloud   → OPENAI_FALLBACK_MODEL  (ex: gpt-3.5-turbo)
#   3. Local          → LOCAL_MODEL_NAME       (Gemma3 via Docker Model Runner)
# =============================================================================

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

import httpx
from openai import OpenAI

from config import (
    LOCAL_MODEL_BASE_URL,
    LOCAL_MODEL_ENABLED,
    LOCAL_MODEL_NAME,
    OPENAI_API_KEY,
    OPENAI_FALLBACK_MODEL,
    OPENAI_MODEL,
)
from core import notifier

# Caminho do socket Unix do Docker Model Runner (Mac-local)
_DOCKER_SOCKET = (
    "/Users/nettomello/Library/Containers/com.docker.docker" "/Data/inference.sock"
)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CloudProvider:
    """Cliente OpenAI cloud reutilizável."""

    api_key: str

    @cached_property
    def client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key)

    def complete(self, model: str, **kwargs: Any):
        return self.client.chat.completions.create(model=model, **kwargs)


@dataclass(frozen=True)
class _LocalProvider:
    """Cliente local via Docker Model Runner (UDS) com fallback TCP."""

    model: str
    socket_path: str = _DOCKER_SOCKET
    base_url: str = LOCAL_MODEL_BASE_URL

    @cached_property
    def client(self) -> OpenAI:
        if os.path.exists(self.socket_path):
            transport = httpx.HTTPTransport(uds=self.socket_path)
            http_client = httpx.Client(transport=transport)
            return OpenAI(
                base_url="http://localhost/v1",
                api_key="local",
                http_client=http_client,
            )
        # Railway / ambientes sem socket exposto
        return OpenAI(base_url=self.base_url, api_key="local")

    def complete(self, **kwargs: Any):
        return self.client.chat.completions.create(model=self.model, **kwargs)


# ---------------------------------------------------------------------------
# Cadeia de fallback
# ---------------------------------------------------------------------------


@dataclass
class LLMChain:
    """Orquestra a cadeia de fallback entre providers de LLM."""

    cloud: _CloudProvider
    local: _LocalProvider | None
    primary_model: str
    fallback_model: str | None

    def complete(self, **kwargs: Any):
        """Executa a chamada LLM percorrendo a cadeia de fallback."""
        attempts: list[tuple[str, Any]] = []

        # 1. Cloud Primary
        attempts.append(
            (
                f"cloud/{self.primary_model}",
                lambda: self.cloud.complete(self.primary_model, **kwargs),
            )
        )

        # 2. Cloud Fallback
        if self.fallback_model and self.fallback_model != self.primary_model:
            attempts.append(
                (
                    f"cloud/{self.fallback_model}",
                    lambda: self.cloud.complete(self.fallback_model, **kwargs),
                )
            )

        # 3. Local
        if self.local is not None:
            attempts.append(
                (
                    f"local/{self.local.model}",
                    lambda: self.local.complete(**kwargs),
                )
            )

        last_exc: Exception | None = None
        for label, call in attempts:
            try:
                return call()
            except Exception as exc:
                last_exc = exc
                notifier.warning(f"[LLMChain] '{label}' falhou: {exc}", "openai_utils")

        raise RuntimeError(
            f"Todos os providers falharam. Último erro: {last_exc}"
        ) from last_exc


# ---------------------------------------------------------------------------
# Instância singleton — construída uma única vez no import
# ---------------------------------------------------------------------------


def _build_chain() -> LLMChain:
    cloud = _CloudProvider(api_key=OPENAI_API_KEY)
    local = _LocalProvider(model=LOCAL_MODEL_NAME) if LOCAL_MODEL_ENABLED else None
    return LLMChain(
        cloud=cloud,
        local=local,
        primary_model=OPENAI_MODEL,
        fallback_model=OPENAI_FALLBACK_MODEL,
    )


_chain: LLMChain = _build_chain()


# ---------------------------------------------------------------------------
# API pública — compatível com o contrato anterior
# ---------------------------------------------------------------------------


def chat_completions(**kwargs: Any):
    """Executa chat.completions com cadeia de fallback automática.

    Drop-in replacement da função original — aceita os mesmos kwargs
    que ``openai.chat.completions.create``, exceto ``model`` (gerenciado
    internamente pela cadeia).
    """
    return _chain.complete(**kwargs)
