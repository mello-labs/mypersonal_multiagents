# =============================================================================
# agents/capture_agent.py — Classificador + Router para o NEØ Command Center
# =============================================================================
# Recebe texto livre (vindo de Telegram, CLI, FastAPI) e decide:
#   LOG         → 📝 Work Log · Diário
#   TASK        → ✅ Tarefas & Ações
#   DECISION    → 🧠 Decisões Estratégicas
#   PROJECT     → 📁 Projetos NEØ
#   INTEGRATION → 📋 Integrations Tracker
#   IDEA        → (default LOG com tag "idea")
#
# O classificador usa chat_completions (cadeia OpenAI público → Local).
# A escrita no Notion segue o mesmo padrão de notion_sync (requests + tenacity).
# =============================================================================

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from adapters.notion import request as _notion_request
from config import (  # noqa: E402
    NOTION_DB_DECISOES,
    NOTION_DB_INTEGRATIONS,
    NOTION_DB_PROJETOS,
    NOTION_DB_TAREFAS,
    NOTION_DB_WORKLOG,
    NOTION_TOKEN,
)
from core import memory, notifier  # noqa: E402
from core.openai_utils import chat_completions  # noqa: E402

AGENT_NAME = "capture_agent"


# ---------------------------------------------------------------------------
# Taxonomia
# ---------------------------------------------------------------------------

CATEGORIES = {
    "LOG": {
        "db_var": "NOTION_DB_WORKLOG",
        "db_id": NOTION_DB_WORKLOG,
        "label": "📝 Work Log · Diário",
    },
    "TASK": {
        "db_var": "NOTION_DB_TAREFAS",
        "db_id": NOTION_DB_TAREFAS,
        "label": "✅ Tarefas & Ações",
    },
    "DECISION": {
        "db_var": "NOTION_DB_DECISOES",
        "db_id": NOTION_DB_DECISOES,
        "label": "🧠 Decisões Estratégicas",
    },
    "PROJECT": {
        "db_var": "NOTION_DB_PROJETOS",
        "db_id": NOTION_DB_PROJETOS,
        "label": "📁 Projetos NEØ",
    },
    "INTEGRATION": {
        "db_var": "NOTION_DB_INTEGRATIONS",
        "db_id": NOTION_DB_INTEGRATIONS,
        "label": "📋 Integrations Tracker",
    },
}


# ---------------------------------------------------------------------------
# Property helpers
# ---------------------------------------------------------------------------


def _p_title(text: str) -> dict:
    return {"title": [{"text": {"content": text[:2000]}}]}


def _p_rich(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def _p_select(name: str) -> dict:
    return {"select": {"name": name}}


def _p_date(iso: str) -> dict:
    return {"date": {"start": iso}}


def _p_url(url: str) -> dict:
    return {"url": url}


def _p_relation(page_ids: list[str]) -> dict:
    return {"relation": [{"id": pid} for pid in page_ids if pid]}


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
    """Normaliza 'Alta' → '🔥 Alta' etc. Default: ⚡ Média."""
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
        # Merge com fallback p/ garantir chaves mínimas
        merged = {**fallback, **{k: v for k, v in data.items() if v is not None}}
        # Normaliza categoria
        cat = str(merged.get("category", "LOG")).upper()
        if cat not in CATEGORIES:
            cat = "LOG"
        merged["category"] = cat
        # Enriquece URL se o LLM não viu
        if not merged.get("url"):
            merged["url"] = _extract_url(text)
        return merged
    except Exception as exc:
        notifier.warning(f"Classifier falhou ({exc}) — caindo para LOG.", AGENT_NAME)
        return fallback


# ---------------------------------------------------------------------------
# Resolução de projeto (match fuzzy no nome)
# ---------------------------------------------------------------------------


def _query_database(db_id: str, filter_: Optional[dict] = None, page_size: int = 100) -> list[dict]:
    if not db_id or not NOTION_TOKEN:
        return []
    payload: dict = {"page_size": page_size}
    if filter_:
        payload["filter"] = filter_
    result = _notion_request("POST", f"databases/{db_id}/query", payload)
    return result.get("results", [])


def _extract_title(page: dict) -> str:
    props = page.get("properties", {})
    for _name, prop in props.items():
        if prop.get("type") == "title":
            rt = prop.get("title", [])
            if rt:
                return "".join(chunk.get("plain_text", "") for chunk in rt)
    return ""


def find_project_page_id(hint: str) -> Optional[str]:
    """Retorna o ID da página de Projeto cujo nome mais se aproxima de `hint`."""
    if not hint or not NOTION_DB_PROJETOS:
        return None
    hint_l = hint.lower().strip()
    candidates = _query_database(NOTION_DB_PROJETOS)
    best: tuple[int, Optional[str]] = (0, None)
    for page in candidates:
        title = _extract_title(page).lower()
        if not title:
            continue
        score = 0
        if hint_l == title:
            score = 100
        elif hint_l in title or title in hint_l:
            score = 60
        else:
            # token overlap simples
            tokens_a = set(re.findall(r"\w+", hint_l))
            tokens_b = set(re.findall(r"\w+", title))
            if tokens_a & tokens_b:
                score = 20 + 10 * len(tokens_a & tokens_b)
        if score > best[0]:
            best = (score, page.get("id"))
    return best[1] if best[0] >= 20 else None


# ---------------------------------------------------------------------------
# Criadores por categoria (respeitam os schemas reais do Command Center)
# ---------------------------------------------------------------------------


def _require_db(category: str) -> str:
    info = CATEGORIES[category]
    db_id = info["db_id"]
    if not db_id:
        raise RuntimeError(
            f"{info['label']}: env {info['db_var']} não configurada."
        )
    if not NOTION_TOKEN:
        raise RuntimeError("NOTION_TOKEN não configurada.")
    return db_id


def _create_page(db_id: str, properties: dict, children: Optional[list] = None) -> dict:
    payload: dict = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }
    if children:
        payload["children"] = children
    return _notion_request("POST", "pages", payload)


def _paragraph_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text[:1900]}}]
        },
    }


def create_log(cls: dict[str, Any]) -> dict:
    """📝 Work Log · Diário — title=Registro, rich_text=Detalhes, relation=Projeto."""
    db_id = _require_db("LOG")
    props: dict[str, Any] = {
        "Registro": _p_title(cls["title"]),
        "Detalhes": _p_rich(cls.get("summary", "")),
    }
    proj_id = find_project_page_id(cls.get("project_hint") or "")
    if proj_id:
        props["Projeto"] = _p_relation([proj_id])
    return _create_page(db_id, props)


def create_task(cls: dict[str, Any]) -> dict:
    """✅ Tarefas & Ações — Tarefa(title), Descrição, Status, Prioridade, Data Limite, Projeto."""
    db_id = _require_db("TASK")
    props: dict[str, Any] = {
        "Tarefa": _p_title(cls["title"]),
        "Descrição": _p_rich(cls.get("summary", "")),
        "Status": _p_select("📋 Backlog"),
        "Prioridade": _p_select(_norm_priority(cls.get("priority"))),
    }
    if cls.get("due_date"):
        props["Data Limite"] = _p_date(cls["due_date"])
    proj_id = find_project_page_id(cls.get("project_hint") or "")
    if proj_id:
        props["Projeto"] = _p_relation([proj_id])
    return _create_page(db_id, props)


def create_decision(cls: dict[str, Any]) -> dict:
    """🧠 Decisões — Decisão(title), Opções, Status, Prioridade, Data Limite, Projetos Afetados."""
    db_id = _require_db("DECISION")
    props: dict[str, Any] = {
        "Decisão": _p_title(cls["title"]),
        "Opções": _p_rich(cls.get("summary", "")),
        "Status": _p_select("⏳ Pendente"),
        "Prioridade": _p_select(_norm_priority(cls.get("priority"))),
    }
    if cls.get("due_date"):
        props["Data Limite"] = _p_date(cls["due_date"])
    proj_id = find_project_page_id(cls.get("project_hint") or "")
    if proj_id:
        props["Projetos Afetados"] = _p_relation([proj_id])
    return _create_page(db_id, props)


def create_project(cls: dict[str, Any]) -> dict:
    """📁 Projetos NEØ — Nome(title), Descrição, Fase, Status, Prioridade, GitHub."""
    db_id = _require_db("PROJECT")
    props: dict[str, Any] = {
        "Nome": _p_title(cls["title"]),
        "Descrição": _p_rich(cls.get("summary", "")),
        "Prioridade": _p_select(_norm_priority(cls.get("priority"))),
    }
    if cls.get("url"):
        props["GitHub"] = _p_url(cls["url"])
    return _create_page(db_id, props)


def create_integration(cls: dict[str, Any]) -> dict:
    """📋 Integrations Tracker — Name(title), Notes, Type, Integration, Priority, Due."""
    db_id = _require_db("INTEGRATION")
    props: dict[str, Any] = {
        "Name": _p_title(cls["title"]),
        "Notes": _p_rich(cls.get("summary", "")),
        "Priority": _p_select(_norm_priority(cls.get("priority"))),
    }
    if cls.get("due_date"):
        props["Due"] = _p_date(cls["due_date"])
    return _create_page(db_id, props)


_DISPATCH = {
    "LOG": create_log,
    "TASK": create_task,
    "DECISION": create_decision,
    "PROJECT": create_project,
    "INTEGRATION": create_integration,
}


# ---------------------------------------------------------------------------
# Helper: audit tolerante (Redis pode estar fora em dev local)
# ---------------------------------------------------------------------------


def _safe_audit(**kwargs: Any) -> None:
    """memory.create_audit_event com fallback silencioso se Redis indisponível.

    Usa sys.stderr diretamente (sem notifier) pra evitar recursão quando o
    próprio notifier tenta persistir algo no Redis e falha.
    """
    try:
        memory.create_audit_event(**kwargs)
    except Exception as exc:
        import sys
        print(
            f"[capture_agent] audit event não persistido: "
            f"{type(exc).__name__}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------


def capture(text: str, *, source: str = "manual") -> dict[str, Any]:
    """Classifica + salva um input livre. Retorna dict com result + metadata."""
    text = (text or "").strip()
    if not text:
        return {"status": "error", "error": "empty input"}

    cls = classify(text)
    category = cls["category"]

    try:
        page = _DISPATCH[category](cls)
        page_id = page.get("id", "")
        page_url = page.get("url", "")
        notifier.success(
            f"[{category}] '{cls['title'][:60]}' → {CATEGORIES[category]['label']}",
            AGENT_NAME,
        )
        # Audit local
        _safe_audit(
            event_type="capture",
            title=f"[{category}] {cls['title'][:100]}",
            details=cls.get("summary", ""),
            level="info",
            agent=AGENT_NAME,
            payload={"classification": cls, "source": source, "notion_page_id": page_id},
        )
        return {
            "status": "ok",
            "category": category,
            "destination": CATEGORIES[category]["label"],
            "title": cls["title"],
            "notion_page_id": page_id,
            "notion_url": page_url,
            "classification": cls,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        notifier.error(f"Falha ao salvar no Notion ({category}): {exc}", AGENT_NAME)
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

    Actions suportadas:
      - capture            → payload["text"] (sempre classifica)
      - capture_log        → payload["text"] (forçando LOG)
      - capture_task       → payload["text"] (forçando TASK)
      - capture_decision   → payload["text"] (forçando DECISION)
      - capture_project    → payload["text"] (forçando PROJECT)
      - capture_integration→ payload["text"] (forçando INTEGRATION)
      - classify           → payload["text"] (só classifica, não salva)
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
        "capture_log": "LOG",
        "capture_task": "TASK",
        "capture_decision": "DECISION",
        "capture_project": "PROJECT",
        "capture_integration": "INTEGRATION",
    }
    if action in forced_map:
        cls = classify(text)
        cls["category"] = forced_map[action]  # override
        try:
            page = _DISPATCH[forced_map[action]](cls)
            return _wrap(
                {
                    "status": "ok",
                    "category": forced_map[action],
                    "destination": CATEGORIES[forced_map[action]]["label"],
                    "title": cls["title"],
                    "notion_page_id": page.get("id", ""),
                    "notion_url": page.get("url", ""),
                    "forced": True,
                }
            )
        except Exception as exc:
            return {"status": "error", "result": str(exc)}

    return {"status": "error", "result": f"unknown action: {action}"}


def _wrap(result: dict) -> dict:
    """Normaliza result do capture() para o contrato de handoff."""
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
