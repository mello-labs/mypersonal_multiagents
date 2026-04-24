# =============================================================================
# core/openai_utils.py — Cadeia de fallback entre providers LLM
# =============================================================================
# Ordem de tentativa (detectada automaticamente na ordem configurada):
#   1. OpenAI público → OPENAI_MODEL                        (primário cloud)
#   2. OpenAI público → OPENAI_FALLBACK_MODEL               (fallback cloud)
#   3. Local          → LOCAL_MODEL_NAME  (Gemma3 via Docker Model Runner)
#
# Se um provider não estiver configurado, ele é simplesmente pulado.
# A API pública continua: chat_completions(**kwargs) — sem passar model=.
# =============================================================================

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable

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

# Caminho do socket Unix do Docker Model Runner — configurável via env var
# ou auto-detectado no path padrão do macOS.
_DOCKER_SOCKET = os.getenv(
    "DOCKER_MODEL_RUNNER_SOCKET",
    os.path.expanduser(
        "~/Library/Containers/com.docker.docker/Data/inference.sock"
    ),
)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class _CloudProvider:
    """Cliente OpenAI público (api.openai.com)."""

    api_key: str

    @cached_property
    def client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key)

    def complete(self, model: str, **kwargs: Any):
        return self.client.chat.completions.create(model=model, **kwargs)


@dataclass(frozen=True, kw_only=True)
class _LocalProvider:
    """Cliente local via Docker Model Runner (UDS em Mac, TCP em outros)."""

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
        # Railway / ambientes sem socket — cai para TCP (se houver)
        return OpenAI(base_url=self.base_url, api_key="local")

    def complete(self, **kwargs: Any):
        return self.client.chat.completions.create(model=self.model, **kwargs)


# ---------------------------------------------------------------------------
# Cadeia de fallback
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True, slots=True)
class LLMChain:
    """Orquestra a cadeia de fallback OpenAI público → Local."""

    cloud: _CloudProvider | None
    cloud_primary: str | None
    cloud_fallback: str | None
    local: _LocalProvider | None

    def complete(self, **kwargs: Any):
        attempts: list[tuple[str, Callable[[], Any]]] = []

        # 1-2. OpenAI público
        if self.cloud is not None and self.cloud_primary:
            attempts.append(
                (
                    f"openai/{self.cloud_primary}",
                    lambda: self.cloud.complete(self.cloud_primary, **kwargs),  # type: ignore[union-attr]
                )
            )
            if self.cloud_fallback and self.cloud_fallback != self.cloud_primary:
                attempts.append(
                    (
                        f"openai/{self.cloud_fallback}",
                        lambda: self.cloud.complete(self.cloud_fallback, **kwargs),  # type: ignore[union-attr]
                    )
                )

        # 3. Local
        if self.local is not None:
            attempts.append(
                (
                    f"local/{self.local.model}",
                    lambda: self.local.complete(**kwargs),  # type: ignore[union-attr]
                )
            )

        if not attempts:
            raise RuntimeError(
                "Nenhum provider LLM configurado. Defina OPENAI_API_KEY ou "
                "LOCAL_MODEL_ENABLED=true."
            )

        last_exc: Exception | None = None
        for label, call in attempts:
            try:
                return call()
            except Exception as exc:
                last_exc = exc
                notifier.warning(f"[LLMChain] '{label}' falhou: {exc}", "openai_utils")

        raise RuntimeError(
            f"Todos os providers LLM falharam. Último erro: {last_exc}"
        ) from last_exc


# ---------------------------------------------------------------------------
# Construção da chain (singleton)
# ---------------------------------------------------------------------------


def _build_chain() -> LLMChain:
    cloud: _CloudProvider | None = None
    if OPENAI_API_KEY:
        cloud = _CloudProvider(api_key=OPENAI_API_KEY)

    local: _LocalProvider | None = None
    if LOCAL_MODEL_ENABLED:
        local = _LocalProvider(model=LOCAL_MODEL_NAME)

    return LLMChain(
        cloud=cloud,
        cloud_primary=OPENAI_MODEL if cloud else None,
        cloud_fallback=OPENAI_FALLBACK_MODEL if cloud else None,
        local=local,
    )


_chain: LLMChain = _build_chain()


# ---------------------------------------------------------------------------
# API pública — compatível com o contrato anterior
# ---------------------------------------------------------------------------


def chat_completions(**kwargs: Any):
    """Drop-in para openai.chat.completions.create().

    NÃO passe `model=` — a chain gerencia internamente (OpenAI público
    primary; cai para fallback model; cai para local).
    """
    return _chain.complete(**kwargs)


def describe_chain() -> list[str]:
    """Retorna lista human-readable dos providers ativos (para /status)."""
    desc: list[str] = []
    if _chain.cloud is not None and _chain.cloud_primary:
        desc.append(f"openai:{_chain.cloud_primary}")
    if _chain.cloud is not None and _chain.cloud_fallback:
        desc.append(f"openai:{_chain.cloud_fallback}(fb)")
    if _chain.local is not None:
        desc.append(f"local:{_chain.local.model}")
    return desc or ["(none — LLM desabilitado)"]
