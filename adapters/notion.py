# =============================================================================
# adapters/notion.py — Cliente HTTP compartilhado para a Notion API
# =============================================================================
# Centraliza autenticação, retry e as operações HTTP primitivas para o Notion.
# Todos os agentes que precisam falar com a Notion API importam daqui.
#
# Uso:
#   from adapters.notion import request as notion_request
#   result = notion_request("POST", "pages", payload)

from __future__ import annotations

from typing import Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import NOTION_API_BASE, NOTION_API_VERSION, NOTION_TOKEN


class NotionRateLimitError(RuntimeError):
    """Levantada em 429 ou 5xx — elegível para retry automático."""


def make_headers() -> dict:
    """Retorna os headers padrão para chamadas à Notion API."""
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


@retry(
    retry=retry_if_exception_type(NotionRateLimitError),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def request(method: str, endpoint: str, data: Optional[dict] = None) -> dict:
    """
    Faz uma requisição à Notion API com retry automático em 429 / 5xx.

    Args:
        method:   Método HTTP ("GET", "POST", "PATCH").
        endpoint: Caminho relativo à URL base (ex: "pages", "databases/ID/query").
        data:     Corpo JSON opcional.

    Returns:
        Dict com a resposta JSON.

    Raises:
        NotionRateLimitError: em 429 ou 5xx (retried automaticamente até 4 tentativas).
        RuntimeError: em erros não-recuperáveis (4xx exceto 429).
    """
    url = f"{NOTION_API_BASE}/{endpoint.lstrip('/')}"
    response = requests.request(method, url, headers=make_headers(), json=data, timeout=15)

    if response.status_code == 429 or response.status_code >= 500:
        raise NotionRateLimitError(
            f"Notion API erro {response.status_code} em {method} {endpoint}: "
            f"{response.text[:200]}"
        )

    if not response.ok:
        raise RuntimeError(
            f"Notion API erro {response.status_code} em {method} {endpoint}: "
            f"{response.text[:500]}"
        )

    return response.json()
