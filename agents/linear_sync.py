from __future__ import annotations

import os
import sys
from typing import Any, Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LINEAR_API_KEY, LINEAR_TEAM_ID  # noqa: E402
from core import notifier  # noqa: E402

AGENT_NAME = "linear_sync"
LINEAR_ENDPOINT = "https://api.linear.app/graphql"

# Linear priority: 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low
_PRIORITY_MAP = {
    "alta": 2,
    "high": 2,
    "🔥 alta": 2,
    "urgente": 1,
    "urgent": 1,
    "média": 3,
    "media": 3,
    "medium": 3,
    "⚡ média": 3,
    "baixa": 4,
    "low": 4,
    "💤 baixa": 4,
}

_CREATE_ISSUE = """
mutation CreateIssue(
  $teamId: String!
  $title: String!
  $description: String
  $priority: Int
  $dueDate: TimelessDate
  $labelIds: [String!]
) {
  issueCreate(input: {
    teamId: $teamId
    title: $title
    description: $description
    priority: $priority
    dueDate: $dueDate
    labelIds: $labelIds
  }) {
    success
    issue {
      id
      identifier
      url
      title
      state { name }
    }
  }
}
"""

_UPDATE_ISSUE = """
mutation UpdateIssue(
  $id: String!
  $title: String
  $description: String
  $priority: Int
  $stateId: String
  $dueDate: TimelessDate
) {
  issueUpdate(id: $id, input: {
    title: $title
    description: $description
    priority: $priority
    stateId: $stateId
    dueDate: $dueDate
  }) {
    success
    issue {
      id
      identifier
      url
      title
      state { name }
    }
  }
}
"""


class _LinearRateLimitError(RuntimeError):
    pass


class LinearSync:
    def __init__(self) -> None:
        self.api_key = LINEAR_API_KEY
        self.team_id = LINEAR_TEAM_ID

    def _headers(self) -> dict:
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

    @retry(
        retry=retry_if_exception_type(_LinearRateLimitError),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("LINEAR_API_KEY não configurada.")
        if not self.team_id:
            raise RuntimeError("LINEAR_TEAM_ID não configurada.")
        resp = requests.post(
            LINEAR_ENDPOINT,
            headers=self._headers(),
            json={"query": query, "variables": variables},
            timeout=20,
        )
        if resp.status_code == 429 or resp.status_code >= 500:
            raise _LinearRateLimitError(f"Linear {resp.status_code}: {resp.text[:200]}")
        if not resp.ok:
            raise RuntimeError(
                f"Linear {resp.status_code}: {resp.text[:500]}"
            )
        data = resp.json()
        if data.get("errors"):
            raise RuntimeError(f"Linear GraphQL errors: {data['errors']}")
        return data.get("data") or {}

    def _norm_priority(self, value: Optional[str]) -> int:
        if not value:
            return 0
        return _PRIORITY_MAP.get(str(value).strip().lower(), 3)

    def create_issue(
        self,
        title: str,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        due_date: Optional[str] = None,
        label_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Cria uma issue no Linear. Retorna o objeto issue ou lança RuntimeError."""
        variables: dict[str, Any] = {
            "teamId": self.team_id,
            "title": title[:255],
            "priority": self._norm_priority(priority),
        }
        if description:
            variables["description"] = description[:10000]
        if due_date:
            variables["dueDate"] = due_date
        if label_ids:
            variables["labelIds"] = label_ids

        data = self._graphql(_CREATE_ISSUE, variables)
        result = data.get("issueCreate", {})
        if not result.get("success"):
            raise RuntimeError(f"issueCreate retornou success=false: {result}")
        return result.get("issue") or {}

    def update_issue(
        self,
        issue_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        state_id: Optional[str] = None,
        due_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Atualiza uma issue existente pelo ID interno do Linear."""
        variables: dict[str, Any] = {"id": issue_id}
        if title is not None:
            variables["title"] = title[:255]
        if description is not None:
            variables["description"] = description[:10000]
        if priority is not None:
            variables["priority"] = self._norm_priority(priority)
        if state_id is not None:
            variables["stateId"] = state_id
        if due_date is not None:
            variables["dueDate"] = due_date

        data = self._graphql(_UPDATE_ISSUE, variables)
        result = data.get("issueUpdate", {})
        if not result.get("success"):
            raise RuntimeError(f"issueUpdate retornou success=false: {result}")
        return result.get("issue") or {}

    def create_from_classification(self, cls: dict[str, Any]) -> dict[str, Any]:
        """Cria uma issue Linear a partir do dict de classificação do capture_agent."""
        category = cls.get("category", "LOG")
        title = cls.get("title", "(sem título)")
        summary = cls.get("summary", "")
        project_hint = cls.get("project_hint")
        url = cls.get("url")

        lines = []
        if summary:
            lines.append(summary)
        if project_hint:
            lines.append(f"\n**Projeto:** {project_hint}")
        if url:
            lines.append(f"\n**Link:** {url}")
        lines.append(f"\n**Categoria:** {category}")
        description = "\n".join(lines) if lines else None

        return self.create_issue(
            title=title,
            description=description,
            priority=cls.get("priority"),
            due_date=cls.get("due_date"),
        )

    def handle_handoff(self, payload: dict) -> dict:
        """Contrato padrão do sistema. Actions: create_issue, update_issue.

        create_issue:
          payload["title"]        — obrigatório
          payload["description"]  — opcional
          payload["priority"]     — "Alta" | "Média" | "Baixa" | None
          payload["due_date"]     — "YYYY-MM-DD" | None
          payload["label_ids"]    — lista de IDs de label | None

        update_issue:
          payload["issue_id"]     — obrigatório (ID interno Linear)
          payload["title"]        — opcional
          payload["description"]  — opcional
          payload["priority"]     — opcional
          payload["state_id"]     — opcional
          payload["due_date"]     — opcional
        """
        action = payload.get("action", "")

        if action == "create_issue":
            title = payload.get("title", "").strip()
            if not title:
                return {"status": "error", "result": "missing 'title' in payload"}
            try:
                issue = self.create_issue(
                    title=title,
                    description=payload.get("description"),
                    priority=payload.get("priority"),
                    due_date=payload.get("due_date"),
                    label_ids=payload.get("label_ids"),
                )
                notifier.success(
                    f"Issue criada: {issue.get('identifier')} — {issue.get('title')}",
                    AGENT_NAME,
                )
                return {"status": "success", "result": issue}
            except Exception as exc:
                notifier.error(f"Erro ao criar issue: {exc}", AGENT_NAME)
                return {"status": "error", "result": str(exc)}

        if action == "update_issue":
            issue_id = payload.get("issue_id", "").strip()
            if not issue_id:
                return {"status": "error", "result": "missing 'issue_id' in payload"}
            try:
                issue = self.update_issue(
                    issue_id=issue_id,
                    title=payload.get("title"),
                    description=payload.get("description"),
                    priority=payload.get("priority"),
                    state_id=payload.get("state_id"),
                    due_date=payload.get("due_date"),
                )
                notifier.success(
                    f"Issue atualizada: {issue.get('identifier')} — {issue.get('title')}",
                    AGENT_NAME,
                )
                return {"status": "success", "result": issue}
            except Exception as exc:
                notifier.error(f"Erro ao atualizar issue: {exc}", AGENT_NAME)
                return {"status": "error", "result": str(exc)}

        return {"status": "error", "result": f"unknown action: {action}"}


# ---------------------------------------------------------------------------
# Instância de módulo (singleton leve — mesmas credenciais para todos os callers)
# ---------------------------------------------------------------------------

_instance: Optional[LinearSync] = None


def _get() -> LinearSync:
    global _instance
    if _instance is None:
        _instance = LinearSync()
    return _instance


def create_from_classification(cls: dict[str, Any]) -> dict[str, Any]:
    return _get().create_from_classification(cls)


def handle_handoff(payload: dict) -> dict:
    return _get().handle_handoff(payload)
