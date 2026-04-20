# =============================================================================
# core/openai_utils.py — Cadeia de fallback entre providers LLM
# =============================================================================
# Ordem de tentativa (detectada automaticamente na ordem configurada):
#   1. Azure OpenAI   → AZURE_OPENAI_DEPLOYMENT             (primário em prod)
#   2. Azure OpenAI   → AZURE_OPENAI_FALLBACK_DEPLOYMENT    (opcional)
#   3. OpenAI público → OPENAI_MODEL                        (fallback cloud)
#   4. OpenAI público → OPENAI_FALLBACK_MODEL
#   5. Local          → LOCAL_MODEL_NAME  (Gemma3 via Docker Model Runner)
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
from openai import AzureOpenAI, OpenAI

from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_FALLBACK_DEPLOYMENT,
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
    "/Users/nettomello/Library/Containers/com.docker.docker/Data/inference.sock"
)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class _AzureProvider:
    """Cliente Azure OpenAI. Na API do SDK, `model=` recebe o NOME DO DEPLOYMENT."""

    endpoint: str
    api_key: str
    api_version: str

    @cached_property
    def client(self) -> AzureOpenAI:
        return AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )

    def complete(self, deployment: str, **kwargs: Any):
        # No SDK da Azure, `model` é o deployment name
        return self.client.chat.completions.create(model=deployment, **kwargs)


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
    """Orquestra a cadeia de fallback Azure → OpenAI → Local."""

    azure: _AzureProvider | None
    azure_primary: str | None
    azure_fallback: str | None
    cloud: _CloudProvider | None
    cloud_primary: str | None
    cloud_fallback: str | None
    local: _LocalProvider | None

    def complete(self, **kwargs: Any):
        attempts: list[tuple[str, Callable[[], Any]]] = []

        # 1-2. Azure OpenAI
        if self.azure is not None and self.azure_primary:
            attempts.append(
                (
                    f"azure/{self.azure_primary}",
                    lambda: self.azure.complete(self.azure_primary, **kwargs),  # type: ignore[union-attr]
                )
            )
            if self.azure_fallback and self.azure_fallback != self.azure_primary:
                attempts.append(
                    (
                        f"azure/{self.azure_fallback}",
                        lambda: self.azure.complete(self.azure_fallback, **kwargs),  # type: ignore[union-attr]
                    )
                )

        # 3-4. OpenAI público
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

        # 5. Local
        if self.local is not None:
            attempts.append(
                (
                    f"local/{self.local.model}",
                    lambda: self.local.complete(**kwargs),  # type: ignore[union-attr]
                )
            )

        if not attempts:
            raise RuntimeError(
                "Nenhum provider LLM configurado. Defina AZURE_OPENAI_* ou "
                "OPENAI_API_KEY ou LOCAL_MODEL_ENABLED=true."
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
    azure: _AzureProvider | None = None
    if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT:
        azure = _AzureProvider(
            endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        )

    cloud: _CloudProvider | None = None
    if OPENAI_API_KEY:
        cloud = _CloudProvider(api_key=OPENAI_API_KEY)

    local: _LocalProvider | None = None
    if LOCAL_MODEL_ENABLED:
        local = _LocalProvider(model=LOCAL_MODEL_NAME)

    return LLMChain(
        azure=azure,
        azure_primary=AZURE_OPENAI_DEPLOYMENT or None,
        azure_fallback=AZURE_OPENAI_FALLBACK_DEPLOYMENT or None,
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

    NÃO passe `model=` — a chain gerencia internamente (Azure deployment
    vence; cai para OpenAI público; cai para local).
    """
    return _chain.complete(**kwargs)


def describe_chain() -> list[str]:
    """Retorna lista human-readable dos providers ativos (para /status)."""
    desc: list[str] = []
    if _chain.azure is not None and _chain.azure_primary:
        desc.append(f"azure:{_chain.azure_primary}")
    if _chain.azure is not None and _chain.azure_fallback:
        desc.append(f"azure:{_chain.azure_fallback}(fb)")
    if _chain.cloud is not None and _chain.cloud_primary:
        desc.append(f"openai:{_chain.cloud_primary}")
    if _chain.cloud is not None and _chain.cloud_fallback:
        desc.append(f"openai:{_chain.cloud_fallback}(fb)")
    if _chain.local is not None:
        desc.append(f"local:{_chain.local.model}")
    return desc or ["(none — LLM desabilitado)"]
