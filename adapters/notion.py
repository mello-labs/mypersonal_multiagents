from __future__ import annotations

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import NOTION_API_BASE, NOTION_API_VERSION, NOTION_TOKEN


class NotionRateLimitError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


@retry(
    retry=retry_if_exception_type(NotionRateLimitError),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def request(method: str, endpoint: str, payload: dict | None = None) -> dict:
    url = f"{NOTION_API_BASE}/{endpoint.lstrip('/')}"
    r = requests.request(method, url, headers=_headers(), json=payload, timeout=30)
    if r.status_code == 429:
        raise NotionRateLimitError(f"Rate limited: {r.text[:200]}")
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Property helpers
# ---------------------------------------------------------------------------


def p_title(text: str) -> dict:
    return {"title": [{"text": {"content": text[:2000]}}]}


def p_rich(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def p_select(name: str) -> dict:
    return {"select": {"name": name}}


def p_date(iso: str) -> dict:
    return {"date": {"start": iso}}


def p_url(url: str) -> dict:
    return {"url": url}


def p_relation(page_ids: list[str]) -> dict:
    return {"relation": [{"id": pid} for pid in page_ids if pid]}
