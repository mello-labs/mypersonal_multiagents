from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from agents import linear_sync  # noqa: E402
from core import memory, notifier  # noqa: E402
from core.openai_utils import chat_completions  # noqa: E402

AGENT_NAME = "capture_agent"


# ---------------------------------------------------------------------------
# Taxonomia
# ---------------------------------------------------------------------------

CATEGORIES = {
    "LOG":         "📝 Work Log · Diário",
    "TASK":        "✅ Tarefas & Ações",
    "DECISION":    "🧠 Decisões Estratégicas",
    "PROJECT":     "📁 Projetos NEØ",
    "INTEGRATION": "📋 Integrations Tracker",
}


# ---------------------------------------------------------------------------
# Normalizadores de valores (os selects do Command Center usam emoji)
# ---------------------------------------------------------------------------

_PRIORITY_MAP = {
    "alta": "🔥 Alta",
    "high": "🔥 Alta",
    "🔥 alta": "🔥 Alta",
    "media": "⚡ Média",
    "média": "⚡ Média",
    "medium": "⚡ Média",
    "⚡ média": "⚡ Média",
    "baixa": "💤 Baixa",
    "low": "💤 Baixa",
    "💤 baixa": "💤 Baixa",
}


def _norm_priority(value: Optional[str]) -> str:
    if not value:
        return "⚡ Média"
    key = str(value).strip().lower()
    return _PRIORITY_MAP.get(key, "⚡ Média")


# ---------------------------------------------------------------------------
# Classificador LLM
# ---------------------------------------------------------------------------

_CLASSIFIER_SYSTEM = """Você é o classificador do NEØ Command Center, um segundo cérebro pessoal do MELLØ.

Dado um input livre (texto, link, voz transcrita), você DEVE retornar JSON com:
{
  "category": "LOG" | "TASK" | "DECISION" | "PROJECT" | "INTEGRATION",
  "title": "<título curto, 80 chars max, em pt-BR>",
  "summary": "<resumo em 1-3 frases>",
  "priority": "Alta" | "Média" | "Baixa" | null,
  "url": "<primeira URL no texto ou null>",
  "tags": ["<opcional, curto>"],
  "project_hint": "<nome aproximado do projeto se mencionado, ex: flowpay | neoflow | null>",
  "due_date": "<YYYY-MM-DD ou null>"
}

Regras de categoria:
- LOG: relatos do dia, observações, insights rápidos, dúvidas abertas. "hoje fiz X", "percebi que Y".
- TASK: ação a executar. Verbos imperativos, prazos, to-dos. "criar endpoint", "revisar PR", "comprar X".
- DECISION: escolha entre opções, trade-off estratégico. "devo usar A ou B?", "bato o martelo em X".
- PROJECT: criação/atualização de um projeto inteiro com escopo amplo. "novo projeto: ...", "reescrever o sistema Y".
- INTEGRATION: tarefa técnica ligada a uma integração específica (Woovi, ASI1, Pix, etc).

Priorize TASK se houver verbo de ação + deadline/urgência.
Priorize LOG se for relato passado sem ação clara.
Priorize DECISION se houver "ou", "versus", "comparar opções".
Retorne APENAS o JSON, sem texto ao redor, sem markdown fences."""

_URL_RE = re.compile(r"https?://[^\s)]+")


def _extract_url(text: str) -> Optional[str]:
    m = _URL_RE.search(text)
    return m.group(0) if m else None


def classify(text: str) -> dict[str, Any]:
    """Classifica texto livre numa das 5 categorias. Sempre retorna um dict válido."""
    fallback: dict[str, Any] = {
        "category": "LOG",
        "title": text[:80].strip() or "(sem título)",
        "summary": text[:500].strip(),
        "priority": None,
        "url": _extract_url(text),
        "tags": [],
        "project_hint": None,
        "due_date": None,
    }

    try:
        resp = chat_completions(
            messages=[
                {"role": "system", "content": _CLASSIFIER_SYSTEM},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        merged = {**fallback, **{k: v for k, v in data.items() if v is not None}}
        cat = str(merged.get("category", "LOG")).upper()
        if cat not in CATEGORIES:
            cat = "LOG"
        merged["category"] = cat
        if not merged.get("url"):
            merged["url"] = _extract_url(text)
        return merged
    except Exception as exc:
        notifier.warning(f"Classifier falhou ({exc}) — caindo para LOG.", AGENT_NAME)
        return fallback


# ---------------------------------------------------------------------------
# Helper: audit tolerante (Redis pode estar fora em dev local)
# ---------------------------------------------------------------------------


def _safe_audit(**kwargs: Any) -> None:
    try:
        memory.create_audit_event(**kwargs)
    except Exception as exc:
        print(
            f"[capture_agent] audit event não persistido: {type(exc).__name__}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------


def capture(text: str, *, source: str = "manual") -> dict[str, Any]:
    """Classifica + cria issue no Linear. Retorna dict com result + metadata."""
    text = (text or "").strip()
    if not text:
        return {"status": "error", "error": "empty input"}

    cls = classify(text)
    category = cls["category"]

    try:
        issue = linear_sync.create_from_classification(cls)
        issue_id = issue.get("id", "")
        issue_url = issue.get("url", "")
        identifier = issue.get("identifier", "")
        notifier.success(
            f"[{category}] '{cls['title'][:60]}' → {CATEGORIES[category]} ({identifier})",
            AGENT_NAME,
        )
        _safe_audit(
            event_type="capture",
            title=f"[{category}] {cls['title'][:100]}",
            details=cls.get("summary", ""),
            level="info",
            agent=AGENT_NAME,
            payload={"classification": cls, "source": source, "linear_id": issue_id},
        )
        return {
            "status": "ok",
            "category": category,
            "destination": CATEGORIES[category],
            "title": cls["title"],
            "linear_id": issue_id,
            "issue_url": issue_url,
            "identifier": identifier,
            "classification": cls,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        notifier.error(f"Falha ao criar issue no Linear ({category}): {exc}", AGENT_NAME)
        _safe_audit(
            event_type="capture_failed",
            title=f"[{category}] {cls['title'][:100]}",
            details=str(exc),
            level="error",
            agent=AGENT_NAME,
            payload={"classification": cls, "source": source},
        )
        return {
            "status": "error",
            "category": category,
            "error": str(exc),
            "classification": cls,
        }


# ---------------------------------------------------------------------------
# Handoff padrão do sistema (compatível com orchestrator)
# ---------------------------------------------------------------------------


def handle_handoff(payload: dict) -> dict:
    """Contrato padrão: retorna {"status": "success"|"error", "result": ...}.

    Actions:
      capture             — classifica + cria no Linear
      capture_log         — forçando LOG
      capture_task        — forçando TASK
      capture_decision    — forçando DECISION
      capture_project     — forçando PROJECT
      capture_integration — forçando INTEGRATION
      classify            — só classifica, não cria
    """
    action = payload.get("action", "capture")
    text = payload.get("text") or payload.get("content") or ""
    source = payload.get("source", "handoff")

    if not text.strip():
        return {"status": "error", "result": "missing 'text' in payload"}

    if action == "classify":
        return {"status": "success", "result": classify(text)}

    if action == "capture":
        return _wrap(capture(text, source=source))

    forced_map = {
        "capture_log":         "LOG",
        "capture_task":        "TASK",
        "capture_decision":    "DECISION",
        "capture_project":     "PROJECT",
        "capture_integration": "INTEGRATION",
    }
    if action in forced_map:
        cls = classify(text)
        cls["category"] = forced_map[action]
        try:
            issue = linear_sync.create_from_classification(cls)
            return _wrap({
                "status": "ok",
                "category": forced_map[action],
                "destination": CATEGORIES[forced_map[action]],
                "title": cls["title"],
                "linear_id": issue.get("id", ""),
                "issue_url": issue.get("url", ""),
                "identifier": issue.get("identifier", ""),
                "forced": True,
            })
        except Exception as exc:
            return {"status": "error", "result": str(exc)}

    return {"status": "error", "result": f"unknown action: {action}"}


def _wrap(result: dict) -> dict:
    if result.get("status") == "ok":
        return {"status": "success", "result": result}
    return {"status": "error", "result": result}


# ---------------------------------------------------------------------------
# CLI helper (smoke test)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import sys as _sys

    if len(_sys.argv) < 2:
        print("Uso: python -m agents.capture_agent '<texto a capturar>'")
        _sys.exit(1)
    text = " ".join(_sys.argv[1:])
    result = capture(text, source="cli")
    print(json.dumps(result, indent=2, ensure_ascii=False))
