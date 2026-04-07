#!/usr/bin/env python3
# =============================================================================
# scripts/diagnose.py — Diagnóstico read-only do estado do sistema
# =============================================================================
# Mostra lado a lado:
#   1. O schema real das DBs no Notion (propriedades + tipos)
#   2. O conteúdo parseado vindo do Notion
#   3. O conteúdo atual no Redis local
#   4. Diff e anomalias (títulos vazios, órfãos, travessão errado etc.)
#   5. O que o Focus Guard "enxerga" quando faz analyze_progress()
#
# Uso: python scripts/diagnose.py
# NÃO altera Notion nem Redis — apenas lê.

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import notion_sync
from agents.notion_sync import _request  # acesso direto para query bruta
from config import NOTION_AGENDA_DB_ID, NOTION_TASKS_DB_ID, NOTION_TOKEN
from core import memory, notifier

AGENT_NAME = "diagnose"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _header(title: str) -> None:
    print()
    notifier.separator(title)


def _raw_query_first(db_id: str) -> dict | None:
    """Pega 1 página bruta de um database — sem passar pelos parsers."""
    if not (NOTION_TOKEN and db_id):
        return None
    result = _request("POST", f"databases/{db_id}/query", {"page_size": 1})
    results = result.get("results", [])
    return results[0] if results else None


def _describe_property_schema(page: dict) -> list[list[str]]:
    """Extrai (nome, tipo, preview) de cada propriedade de uma página Notion."""
    rows = []
    for name, prop in (page.get("properties") or {}).items():
        ptype = prop.get("type", "?")
        raw = prop.get(ptype)
        if isinstance(raw, list) and raw:
            first = raw[0]
            preview = (
                first.get("plain_text")
                or first.get("name")
                or str(first)[:40]
            )
        elif isinstance(raw, dict):
            preview = raw.get("name") or raw.get("start") or str(raw)[:40]
        else:
            preview = str(raw)[:40] if raw is not None else ""
        rows.append([name, ptype, (preview or "")[:40]])
    return rows


def _check_schema(rows: list[list[str]], expected: dict[str, str], label: str) -> None:
    """Compara as propriedades reais com o que o parser espera."""
    present = {r[0]: r[1] for r in rows}
    mismatches: list[str] = []
    for name, etype in expected.items():
        if name not in present:
            mismatches.append(
                f"FALTA coluna '{name}' em {label} (esperada tipo '{etype}')"
            )
        elif present[name] != etype:
            mismatches.append(
                f"'{name}' em {label} é '{present[name]}', esperado '{etype}'"
            )
    if mismatches:
        for m in mismatches:
            notifier.error(m, AGENT_NAME)
    else:
        notifier.success(f"Schema de {label} bate com o esperado.", AGENT_NAME)


# ---------------------------------------------------------------------------
# Seções
# ---------------------------------------------------------------------------


def section_schema_check() -> None:
    _header("SEÇÃO 1 — SCHEMA REAL NO NOTION (primeira página de cada DB)")

    # Tarefas
    try:
        first_task = _raw_query_first(NOTION_TASKS_DB_ID)
    except Exception as e:
        notifier.error(f"Falhou ao ler DB de Tarefas: {e}", AGENT_NAME)
        first_task = None

    if not first_task:
        notifier.warning("Nenhuma tarefa encontrada no Notion (DB vazio ou sem acesso).", AGENT_NAME)
    else:
        rows = _describe_property_schema(first_task)
        notifier.print_table(
            ["Propriedade", "Tipo", "Valor (preview)"],
            rows,
            "TAREFAS — raw properties",
        )
        _check_schema(
            rows,
            {
                "Nome": "title",
                "Status": "select",
                "Prioridade": "select",
                "Horário previsto": "date",       # tipo date (suporta date picker nativo)
                "Horário real": "rich_text",
            },
            "Tarefas",
        )

    # Agenda
    try:
        first_block = _raw_query_first(NOTION_AGENDA_DB_ID)
    except Exception as e:
        notifier.error(f"Falhou ao ler DB de Agenda: {e}", AGENT_NAME)
        first_block = None

    if not first_block:
        notifier.warning("Nenhum bloco encontrado na Agenda (DB vazio ou sem acesso).", AGENT_NAME)
    else:
        rows = _describe_property_schema(first_block)
        notifier.print_table(
            ["Propriedade", "Tipo", "Valor (preview)"],
            rows,
            "AGENDA — raw properties",
        )
        _check_schema(
            rows,
            {
                "Data de entrega": "date",
                "Tarefa vinculada": "relation",
                "Concluído": "checkbox",
            },
            "Agenda",
        )


def section_notion_contents() -> tuple[list[dict], list[dict]]:
    _header("SEÇÃO 2 — CONTEÚDO PARSEADO VINDO DO NOTION")

    try:
        notion_tasks = notion_sync.fetch_notion_tasks()
    except Exception as e:
        notifier.error(f"Erro ao buscar tarefas: {e}", AGENT_NAME)
        notion_tasks = []

    notifier.info(f"Tarefas retornadas pelo parser: {len(notion_tasks)}", AGENT_NAME)
    if notion_tasks:
        rows = [
            [
                (t.get("title") or "<vazio>")[:35],
                t.get("status") or "<vazio>",
                t.get("priority") or "<vazio>",
                (t.get("scheduled_time") or "—")[:15],
                (t.get("notion_page_id") or "")[:8],
            ]
            for t in notion_tasks[:15]
        ]
        notifier.print_table(
            ["Título", "Status", "Prioridade", "Horário", "ID"],
            rows,
            "Tarefas Notion (até 15)",
        )

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    try:
        notion_agenda = notion_sync.fetch_agenda_range_from_notion(today, tomorrow)
    except Exception as e:
        notifier.error(f"Erro ao buscar agenda: {e}", AGENT_NAME)
        notion_agenda = []

    notifier.info(
        f"Blocos de agenda retornados pelo parser (hoje + amanhã): {len(notion_agenda)}",
        AGENT_NAME,
    )
    if notion_agenda:
        rows = [
            [
                b.get("date", "—"),
                b.get("time_slot") or "<vazio>",
                (b.get("task_title") or "<vazio>")[:35],
                "✅" if b.get("completed") else "⬜",
                (b.get("raw_block") or "")[:40],
            ]
            for b in notion_agenda[:20]
        ]
        notifier.print_table(
            ["Data", "Horário", "Tarefa", "Done", "Raw"],
            rows,
            "Agenda Notion (até 20)",
        )

    return notion_tasks, notion_agenda


def section_redis_contents() -> tuple[list[dict], list[dict]]:
    _header("SEÇÃO 3 — CONTEÚDO NO REDIS LOCAL")

    try:
        local_tasks = memory.list_all_tasks()
    except Exception as e:
        notifier.error(f"Erro ao listar tarefas locais: {e}", AGENT_NAME)
        local_tasks = []

    notifier.info(f"Tarefas no Redis: {len(local_tasks)}", AGENT_NAME)
    if local_tasks:
        rows = [
            [
                str(t.get("id", "")),
                (t.get("title") or "<vazio>")[:35],
                t.get("status") or "<vazio>",
                (t.get("notion_page_id") or "—")[:8],
            ]
            for t in local_tasks[:15]
        ]
        notifier.print_table(
            ["ID", "Título", "Status", "Notion"],
            rows,
            "Tarefas Redis (até 15)",
        )

    try:
        local_agenda = memory.get_today_agenda(include_rescheduled=True)
    except Exception as e:
        notifier.error(f"Erro ao listar agenda local: {e}", AGENT_NAME)
        local_agenda = []

    notifier.info(f"Blocos de agenda hoje no Redis: {len(local_agenda)}", AGENT_NAME)
    if local_agenda:
        rows = [
            [
                str(b.get("id", "")),
                b.get("time_slot") or "<vazio>",
                (b.get("task_title") or "<vazio>")[:35],
                "✅" if b.get("completed") else "⬜",
                (b.get("notion_page_id") or "—")[:8],
            ]
            for b in local_agenda
        ]
        notifier.print_table(
            ["ID", "Horário", "Tarefa", "Done", "Notion"],
            rows,
            "Agenda Redis (hoje)",
        )

    return local_tasks, local_agenda


def section_diff(
    notion_tasks: list[dict],
    notion_agenda: list[dict],
    local_tasks: list[dict],
    local_agenda: list[dict],
) -> None:
    _header("SEÇÃO 4 — DIFF E ANOMALIAS")

    # Tarefas: Notion vs Redis
    notion_ids = {t["notion_page_id"] for t in notion_tasks if t.get("notion_page_id")}
    local_ids = {t["notion_page_id"] for t in local_tasks if t.get("notion_page_id")}

    in_notion_not_redis = notion_ids - local_ids
    in_redis_not_notion = local_ids - notion_ids

    if in_notion_not_redis:
        notifier.warning(
            f"{len(in_notion_not_redis)} tarefa(s) NO NOTION mas AUSENTES no Redis "
            "(sync ainda não importou):",
            AGENT_NAME,
        )
        for t in notion_tasks:
            if t.get("notion_page_id") in in_notion_not_redis:
                notifier.warning(
                    f"  • '{t.get('title') or '<vazio>'}' (page {t['notion_page_id'][:8]})",
                    AGENT_NAME,
                )
    else:
        notifier.success(
            "Todas as tarefas do Notion estão refletidas no Redis.", AGENT_NAME
        )

    if in_redis_not_notion:
        notifier.warning(
            f"{len(in_redis_not_notion)} tarefa(s) NO REDIS mas AUSENTES do Notion "
            "(órfãs — próximo sync_tasks_to_local vai apagar):",
            AGENT_NAME,
        )
        for t in local_tasks:
            if t.get("notion_page_id") in in_redis_not_notion:
                notifier.warning(
                    f"  • '{t.get('title') or '<vazio>'}' (local id {t.get('id')})",
                    AGENT_NAME,
                )

    # Tarefas: títulos vazios / sentinela
    empty_notion = [t for t in notion_tasks if not (t.get("title") or "").strip()]
    if empty_notion:
        notifier.error(
            f"{len(empty_notion)} tarefa(s) no Notion com título VAZIO — serão "
            "persistidas como 'Sem título' e apagadas pela reconciliação do sync.",
            AGENT_NAME,
        )
        for t in empty_notion:
            notifier.error(
                f"  • page {t['notion_page_id'][:8]} | status='{t.get('status')}'",
                AGENT_NAME,
            )

    sentinel_local = [
        t for t in local_tasks if (t.get("title") or "").strip() in ("Sem título", "")
    ]
    if sentinel_local:
        notifier.warning(
            f"{len(sentinel_local)} tarefa(s) no Redis com título vazio/sentinela.",
            AGENT_NAME,
        )

    # Agenda: raw_block sem em-dash (causa "Sem título")
    bad_dash = [
        b
        for b in notion_agenda
        if "—" not in (b.get("raw_block") or "")
        and (b.get("raw_block") or "").strip()
    ]
    if bad_dash:
        notifier.error(
            f"{len(bad_dash)} bloco(s) no Notion SEM o travessão '—' — o parser "
            "coloca task_title='Sem título'. Causa comum: você digitou '-' (hífen) "
            "em vez de '—' (em-dash).",
            AGENT_NAME,
        )
        for b in bad_dash[:5]:
            notifier.error(
                f"  • raw='{(b.get('raw_block') or '')[:50]}' → "
                f"time_slot='{b.get('time_slot')}' task='{b.get('task_title')}'",
                AGENT_NAME,
            )

    # Agenda: time_slot vazio — esperado no schema date-only
    empty_slot = [b for b in notion_agenda if not (b.get("time_slot") or "").strip()]
    if empty_slot:
        notifier.info(
            f"{len(empty_slot)} bloco(s) de agenda sem horário (date-only) — comportamento esperado.",
            AGENT_NAME,
        )

    # Agenda de HOJE: Notion vs Redis
    today = date.today().isoformat()
    notion_today_ids = {
        b["notion_page_id"]
        for b in notion_agenda
        if b.get("date") == today and b.get("notion_page_id")
    }
    local_today_ids = {
        b["notion_page_id"] for b in local_agenda if b.get("notion_page_id")
    }
    missing_blocks = notion_today_ids - local_today_ids
    if missing_blocks:
        notifier.warning(
            f"{len(missing_blocks)} bloco(s) de HOJE no Notion mas ausentes no "
            "Redis. Rode `python main.py sync` para importar (ou a rota de agenda "
            "range no web).",
            AGENT_NAME,
        )

    notifier.separator()


def section_focus_guard_view() -> None:
    _header("SEÇÃO 5 — O QUE O FOCUS GUARD 'ENXERGA' AGORA")
    try:
        from agents import focus_guard as fg

        progress = fg.analyze_progress()
    except Exception as e:
        notifier.error(f"Falha ao rodar analyze_progress: {e}", AGENT_NAME)
        return

    load = progress.get("load", {})
    notifier.info(
        f"Total blocos hoje: {load.get('total')} | concluídos: {load.get('completed')} | "
        f"atrasados: {load.get('overdue')} | upcoming: {load.get('upcoming')}",
        AGENT_NAME,
    )
    notifier.info(
        f"on_track (heurístico, sem LLM): {progress.get('on_track')}",
        AGENT_NAME,
    )

    current = progress.get("current_block")
    if current:
        notifier.info(
            f"Bloco CORRENTE (bateu com o relógio): "
            f"{current.get('time_slot')} — {current.get('task_title')}",
            AGENT_NAME,
        )
    else:
        notifier.warning(
            "Nenhum bloco corresponde ao horário atual. Focus Guard não vai "
            "cobrar nada agora.",
            AGENT_NAME,
        )

    active = progress.get("active_focus_session")
    if active:
        notifier.info(
            f"Sessão de foco ativa: '{active.get('task_title')}' desde "
            f"{(active.get('started_at') or '')[:16]}",
            AGENT_NAME,
        )
    else:
        notifier.info(
            "Nenhuma sessão de foco ativa (start_focus_session nunca foi chamado "
            "hoje ou foi encerrado).",
            AGENT_NAME,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    notifier.banner()
    notifier.info(
        "Diagnóstico READ-ONLY — não altera Notion nem Redis.", AGENT_NAME
    )
    memory.init_db()

    if not NOTION_TOKEN:
        notifier.error(
            "NOTION_TOKEN não configurado — seções do Notion serão puladas.",
            AGENT_NAME,
        )

    section_schema_check()
    notion_tasks, notion_agenda = section_notion_contents()
    local_tasks, local_agenda = section_redis_contents()
    section_diff(notion_tasks, notion_agenda, local_tasks, local_agenda)
    section_focus_guard_view()

    notifier.separator("FIM DO DIAGNÓSTICO")
    notifier.info(
        "Nada foi alterado. Use as seções acima para ver onde o sync perde coisa.",
        AGENT_NAME,
    )


if __name__ == "__main__":
    main()
