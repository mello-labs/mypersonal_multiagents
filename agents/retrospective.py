# =============================================================================
# agents/retrospective.py — Agente de Retrospectiva Semanal
# =============================================================================
# Analisa a semana, calcula métricas e gera relatório via LLM.
# Opcionalmente cria página no Notion com os resultados.

import json
import os
from datetime import datetime, timedelta
from typing import Optional


from agents import notion_sync as _notion_sync
from config import NOTION_RETROSPECTIVE_PAGE_ID
from core import memory, notifier
from core.openai_utils import chat_completions

AGENT_NAME = "retrospective"

_RETROSPECTIVE_PROMPT_FALLBACK = """Você é um coach de produtividade pessoal.
Analise os dados da semana e gere uma retrospectiva clara com:

1. **Resumo Executivo** — 2-3 frases sobre a semana
2. **Pontos Positivos** — o que funcionou bem (bullet points)
3. **Pontos de Atenção** — o que pode melhorar (bullet points)
4. **Padrões Identificados** — insights sobre comportamento e produtividade
5. **Recomendações para a Próxima Semana** — 3-5 ações concretas

Seja direto, honesto e encorajador. Baseie-se apenas nos dados fornecidos.
Responda em markdown formatado."""


def _get_retrospective_prompt() -> str:
    return _RETROSPECTIVE_PROMPT_FALLBACK


# ---------------------------------------------------------------------------
# Coleta de dados
# ---------------------------------------------------------------------------


def _get_week_start() -> str:
    """Retorna ISO datetime de 7 dias atrás."""
    return (datetime.now() - timedelta(days=7)).isoformat()


def collect_week_data() -> dict:
    """Coleta todos os dados relevantes da semana."""
    since = _get_week_start()

    # Sessões de foco
    sessions = memory.get_sessions_since(since)
    total_focus_min = sum(s.get("actual_minutes") or 0 for s in sessions)
    completed_sessions = [s for s in sessions if s.get("status") == "completed"]
    abandoned_sessions = [s for s in sessions if s.get("status") == "abandoned"]

    # Tarefas
    all_tasks = memory.list_all_tasks()
    completed_tasks = memory.get_completed_tasks_since(since)
    pending_tasks = [t for t in all_tasks if t["status"] == "A fazer"]
    in_progress_tasks = [t for t in all_tasks if t["status"] == "Em progresso"]

    # Handoffs (atividade dos agentes)
    handoffs = memory.get_handoffs_since(since)
    handoffs_by_agent: dict = {}
    for h in handoffs:
        ag = h.get("target_agent", "unknown")
        handoffs_by_agent[ag] = handoffs_by_agent.get(ag, 0) + 1

    # Taxa de conclusão
    total_tasks_worked = len(completed_tasks) + len(in_progress_tasks)
    completion_rate = (
        round(len(completed_tasks) / total_tasks_worked * 100, 1)
        if total_tasks_worked > 0
        else 0.0
    )

    # Tempo médio por sessão
    avg_session_min = (
        round(total_focus_min / len(completed_sessions), 1)
        if completed_sessions
        else 0.0
    )

    return {
        "period": {
            "start": since[:10],
            "end": datetime.now().strftime("%Y-%m-%d"),
        },
        "metrics": {
            "total_focus_minutes": total_focus_min,
            "total_focus_hours": round(total_focus_min / 60, 1),
            "sessions_completed": len(completed_sessions),
            "sessions_abandoned": len(abandoned_sessions),
            "avg_session_minutes": avg_session_min,
            "tasks_completed": len(completed_tasks),
            "tasks_pending": len(pending_tasks),
            "tasks_in_progress": len(in_progress_tasks),
            "completion_rate_pct": completion_rate,
            "agent_activity": handoffs_by_agent,
        },
        "completed_tasks": [
            {"title": t["title"], "priority": t.get("priority", "Média")}
            for t in completed_tasks[:20]  # limita para não estourar o contexto LLM
        ],
        "focus_sessions": [
            {
                "task": s.get("task_title", "?"),
                "minutes": s.get("actual_minutes", 0),
                "status": s.get("status"),
                "date": (s.get("started_at") or "")[:10],
            }
            for s in sessions[:30]
        ],
    }


# ---------------------------------------------------------------------------
# Geração do relatório via LLM
# ---------------------------------------------------------------------------


def generate_report(data: dict) -> str:
    """Gera o relatório markdown via GPT-4o-mini."""
    data_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    try:
        response = chat_completions(
            messages=[
                {"role": "system", "content": _get_retrospective_prompt()},
                {
                    "role": "user",
                    "content": f"Dados da semana:\n\n{data_str}\n\nGere a retrospectiva.",
                },
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        notifier.error(f"Erro ao gerar relatório: {e}", AGENT_NAME)
        m = data["metrics"]
        return f"""# Retrospectiva {data["period"]["start"]} → {data["period"]["end"]}

## Métricas
- Foco total: {m["total_focus_hours"]}h ({m["total_focus_minutes"]} min)
- Sessões concluídas: {m["sessions_completed"]}
- Sessões abandonadas: {m["sessions_abandoned"]}
- Tarefas concluídas: {m["tasks_completed"]}
- Taxa de conclusão: {m["completion_rate_pct"]}%

*(Relatório gerado sem LLM — erro: {e})*"""


# ---------------------------------------------------------------------------
# Criação de página no Notion
# ---------------------------------------------------------------------------


def _markdown_to_notion_blocks(text: str) -> list[dict]:
    """Converte markdown simples em blocos Notion."""
    blocks = []
    for line in text.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            blocks.append(
                {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}
            )
        elif line_stripped.startswith("# "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [
                            {"type": "text", "text": {"content": line_stripped[2:]}}
                        ]
                    },
                }
            )
        elif line_stripped.startswith("## "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [
                            {"type": "text", "text": {"content": line_stripped[3:]}}
                        ]
                    },
                }
            )
        elif line_stripped.startswith("### "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [
                            {"type": "text", "text": {"content": line_stripped[4:]}}
                        ]
                    },
                }
            )
        elif line_stripped.startswith("- ") or line_stripped.startswith("* "):
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [
                            {"type": "text", "text": {"content": line_stripped[2:]}}
                        ]
                    },
                }
            )
        elif line_stripped.startswith("**") and line_stripped.endswith("**"):
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": line_stripped.strip("*")},
                                "annotations": {"bold": True},
                            }
                        ]
                    },
                }
            )
        else:
            # Paragraph — strip inline markdown markers simply
            clean = line_stripped.replace("**", "").replace("*", "").replace("`", "")
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": clean}}]
                    },
                }
            )
    return blocks[:100]  # Notion limita children por request


def create_notion_retrospective_page(title: str, content_md: str) -> Optional[str]:
    """Cria uma página de retrospectiva no Notion. Retorna o page_id ou None."""
    if not NOTION_RETROSPECTIVE_PAGE_ID:
        notifier.warning(
            "NOTION_RETROSPECTIVE_PAGE_ID não configurado — página não criada.",
            AGENT_NAME,
        )
        return None

    blocks = _markdown_to_notion_blocks(content_md)
    payload = {
        "parent": {"page_id": NOTION_RETROSPECTIVE_PAGE_ID},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children": blocks,
    }

    try:
        result = _notion_sync._request("POST", "pages", data=payload)
        page_id = result["id"]
        notifier.success(
            f"Retrospectiva criada no Notion: {page_id[:8]}...", AGENT_NAME
        )
        return page_id
    except Exception as e:
        notifier.error(f"Erro ao criar página no Notion: {e}", AGENT_NAME)
        return None


# ---------------------------------------------------------------------------
# Salva relatório localmente
# ---------------------------------------------------------------------------


def save_report_locally(title: str, content: str) -> str:
    """Salva o relatório como .md na pasta reports/."""
    from pathlib import Path
    from config import BASE_DIR

    reports_dir = Path(BASE_DIR) / "reports"
    reports_dir.mkdir(exist_ok=True)

    filename = f"{title.replace(' ', '_').replace('/', '-')}.md"
    filepath = reports_dir / filename
    filepath.write_text(content, encoding="utf-8")
    notifier.success(f"Relatório salvo em: {filepath}", AGENT_NAME)
    return str(filepath)


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


def run_retrospective(push_to_notion: bool = True) -> dict:
    """
    Executa o pipeline completo de retrospectiva.
    Retorna dict com métricas, relatório e localização do arquivo.
    """
    notifier.separator("RETROSPECTIVA SEMANAL")
    notifier.info("Coletando dados da semana...", AGENT_NAME)

    data = collect_week_data()
    m = data["metrics"]

    # Exibe métricas no terminal
    notifier.info(
        f"Foco: {m['total_focus_hours']}h | Sessões: {m['sessions_completed']} concluídas "
        f"| Tarefas: {m['tasks_completed']} concluídas ({m['completion_rate_pct']}%)",
        AGENT_NAME,
    )

    notifier.info("Gerando relatório via LLM...", AGENT_NAME)
    report_md = generate_report(data)

    period = data["period"]
    title = f"Retrospectiva {period['start']} → {period['end']}"

    # Salva localmente sempre
    local_path = save_report_locally(title, report_md)

    # Envia ao Notion se solicitado
    notion_page_id = None
    if push_to_notion:
        notion_page_id = create_notion_retrospective_page(title, report_md)

    result = {
        "title": title,
        "period": period,
        "metrics": m,
        "local_path": local_path,
        "notion_page_id": notion_page_id,
        "report_preview": report_md[:500] + "..."
        if len(report_md) > 500
        else report_md,
    }

    notifier.separator()
    return result


# ---------------------------------------------------------------------------
# Handoff entry point
# ---------------------------------------------------------------------------


def handle_handoff(payload: dict) -> dict:
    action = payload.get("action", "")
    notifier.agent_event(f"Recebendo handoff: action='{action}'", AGENT_NAME)
    handoff_id = memory.log_handoff("orchestrator", AGENT_NAME, action, payload)

    try:
        result: dict = {}

        if action == "run":
            push = payload.get("push_to_notion", True)
            result = run_retrospective(push_to_notion=push)

        elif action == "metrics_only":
            data = collect_week_data()
            result = data["metrics"]

        else:
            raise ValueError(f"Ação desconhecida: '{action}'")

        memory.update_handoff_result(handoff_id, result, "success")
        return {"status": "success", "result": result}

    except Exception as exc:
        error_msg = str(exc)
        notifier.error(f"Erro no handoff '{action}': {error_msg}", AGENT_NAME)
        memory.update_handoff_result(handoff_id, {"error": error_msg}, "error")
        return {"status": "error", "result": {"error": error_msg}}
