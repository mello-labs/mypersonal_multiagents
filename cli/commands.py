# =============================================================================
# cli/commands.py — Comandos CLI do sistema de multiagentes
# =============================================================================
# Todos os cmd_* e o build_parser estão aqui.
# main.py apenas faz startup/shutdown e despacha para este módulo.

import argparse
import re
from datetime import date
from typing import Optional

from agents import (
    focus_guard,
    life_guard,
    notion_sync,
    orchestrator,
    scheduler,
    validator,
)
from core import memory, notifier

def cmd_status() -> None:
    """Exibe status completo do sistema."""
    summary = orchestrator.get_system_summary()

    notifier.separator("STATUS DO SISTEMA")
    t = summary["tasks"]
    notifier.info(
        f"Tarefas: {t['total']} total | {t['a_fazer']} a fazer | "
        f"{t['em_progresso']} em progresso | {t['concluido']} concluídas",
        "status",
    )

    a = summary["agenda_today"]
    notifier.info(
        f"Agenda hoje: {a['completed']}/{a['total_blocks']} blocos concluídos",
        "status",
    )

    f = summary["focus"]
    guard_status = "🟢 ativo" if f["guard_running"] else "🔴 inativo"
    notifier.info(f"Focus Guard: {guard_status}", "status")

    if f["active_session"]:
        s = f["active_session"]
        notifier.focus_alert(
            f"Sessão ativa: '{s['task_title']}' (iniciada: {s['started_at'][:16]})"
        )

    if f.get("last_check"):
        on_track = "✅ on track" if f["on_track"] else "⚠️ desvio detectado"
        notifier.info(f"Último check-in: {f['last_check'][:16]} — {on_track}", "status")

    al = summary["alerts"]
    if al["pending"] > 0:
        notifier.warning(f"Alertas pendentes: {al['pending']}", "status")

    notifier.separator()


def cmd_agenda() -> None:
    """Exibe a agenda do dia."""
    blocks = scheduler.get_today_schedule()
    if not blocks:
        notifier.info(
            "Nenhum bloco na agenda de hoje. Use 'add-task' ou 'sync' para popular.",
            "agenda",
        )
        return

    headers = ["ID", "Horário", "Tarefa", "Concluído"]
    rows = [
        [
            str(b["id"]),
            b.get("time_slot", "—"),
            b.get("task_title", "—")[:40],
            "✅" if b.get("completed") else "⬜",
        ]
        for b in blocks
    ]
    notifier.print_table(headers, rows, "AGENDA DE HOJE")

    load = scheduler.calculate_schedule_load(blocks)
    notifier.info(
        f"Total: {load['total_blocks']} blocos | "
        f"{load['completion_percent']}% concluído | "
        f"{load['total_minutes']} min agendados",
        "agenda",
    )


def cmd_tasks() -> None:
    """Lista todas as tarefas."""
    tasks = memory.list_all_tasks()
    if not tasks:
        notifier.info("Nenhuma tarefa cadastrada. Use 'add-task' para criar.", "tasks")
        return

    headers = ["ID", "Título", "Status", "Prioridade", "Horário"]
    rows = [
        [
            str(t["id"]),
            t["title"][:35],
            t["status"],
            t.get("priority", "—"),
            t.get("scheduled_time", "—") or "—",
        ]
        for t in tasks
    ]
    notifier.print_table(headers, rows, "TAREFAS")


def cmd_add_task() -> None:
    """Wizard interativo para adicionar uma nova tarefa."""
    notifier.separator("NOVA TAREFA")

    title = input("  Título da tarefa: ").strip()
    if not title:
        notifier.error("Título não pode ser vazio.", "add-task")
        return

    print("  Prioridade: [1] Alta  [2] Média  [3] Baixa (Enter = Média)")
    priority_map = {"1": "Alta", "2": "Média", "3": "Baixa", "": "Média"}
    priority_input = input("  Escolha: ").strip()
    priority = priority_map.get(priority_input, "Média")

    scheduled_time = input(
        "  Horário (HH:MM ou YYYY-MM-DD HH:MM, Enter para pular): "
    ).strip()

    # Cria localmente
    task_id = memory.create_task(
        title=title,
        priority=priority,
        scheduled_time=scheduled_time or None,
    )
    notifier.success(f"Tarefa criada localmente (ID: {task_id}).", "add-task")

    # Pergunta se quer sincronizar com Notion
    sync_notion = input("  Sincronizar com Notion? [s/N]: ").strip().lower()
    if sync_notion == "s":
        result = notion_sync.sync_local_task_to_notion(task_id)
        if result:
            notifier.success("Tarefa enviada ao Notion!", "add-task")

    # Pergunta se quer adicionar bloco de agenda
    add_block = input("  Adicionar bloco de agenda hoje? [s/N]: ").strip().lower()
    if add_block == "s":
        time_slot = input("  Bloco horário (ex: 09:00-10:00): ").strip()
        if time_slot:
            scheduler.add_schedule_block(time_slot, title, task_id)


def cmd_sync() -> None:
    """Sincroniza dados com o Notion."""
    notifier.separator("SINCRONIZAÇÃO NOTION")
    result = notion_sync.handle_handoff({"action": "sync_from_notion"})
    if result["status"] == "success":
        r = result["result"]
        notifier.success(
            f"Sincronização completa: {r.get('synced', 0)} tarefa(s) importada(s)."
        )
    else:
        notifier.error(f"Erro na sincronização: {result['result'].get('error', '?')}")


def cmd_focus_start(task_id: Optional[int] = None) -> None:
    """Inicia uma sessão de foco."""
    if task_id is None:
        # Mostra tarefas e pede escolha
        tasks = scheduler.get_prioritized_tasks()
        if not tasks:
            notifier.warning("Nenhuma tarefa pendente.", "focus")
            return
        headers = ["ID", "Título", "Prioridade"]
        rows = [[str(t["id"]), t["title"][:40], t.get("priority", "?")] for t in tasks]
        notifier.print_table(headers, rows, "TAREFAS PENDENTES")
        task_id_str = input("  ID da tarefa para focar: ").strip()
        if not task_id_str.isdigit():
            notifier.error("ID inválido.", "focus")
            return
        task_id = int(task_id_str)

    task = memory.get_task(task_id)
    if not task:
        notifier.error(f"Tarefa {task_id} não encontrada.", "focus")
        return

    minutes_str = input("  Duração em minutos (Enter = 25): ").strip()
    minutes = int(minutes_str) if minutes_str.isdigit() else 25

    memory.update_task_status(task_id, "Em progresso")
    focus_guard.start_focus_session(task_id, task["title"], minutes)

    notifier.success(
        f"Sessão de foco iniciada! Foco em: '{task['title']}' por {minutes} min.",
        "focus",
    )


def cmd_focus_end() -> None:
    """Encerra a sessão de foco ativa."""
    result = focus_guard.end_focus_session(status="completed")
    if "Nenhuma sessão" in result.get("message", ""):
        notifier.warning("Nenhuma sessão de foco ativa.", "focus")
    else:
        task_title = result.get("task_title", "?")
        # Pergunta se quer validar e marcar como concluída
        validate = (
            input(f"  Marcar '{task_title}' como concluída e validar? [s/N]: ")
            .strip()
            .lower()
        )
        if validate == "s":
            active_tasks = memory.get_tasks_by_status("Em progresso")
            matched = next((t for t in active_tasks if t["title"] == task_title), None)
            if matched:
                cmd_validate(matched["id"])


def cmd_validate(task_id: Optional[int] = None) -> None:
    """Valida e confirma conclusão de uma tarefa."""
    if task_id is None:
        task_id_str = input("  ID da tarefa para validar: ").strip()
        if not task_id_str.isdigit():
            notifier.error("ID inválido.", "validate")
            return
        task_id = int(task_id_str)

    result = validator.validate_task(task_id)
    verdict = result.get("verdict", {})
    v = verdict.get("verdict", "?")

    if v == "pending_confirmation":
        questions = verdict.get("questions", [])
        for q in questions:
            print(f"\n  ❓ {q}")
        confirm = input("  Confirmar conclusão? [s/N]: ").strip().lower()
        if confirm == "s":
            validator.validate_task(task_id, force_confirm=True)

    notifier.separator()


def cmd_suggest_agenda() -> None:
    """Sugere e opcionalmente aplica uma agenda otimizada via LLM."""
    context = input("  Contexto adicional (Enter para pular): ").strip()
    notifier.info("Gerando sugestão de agenda via LLM...", "scheduler")

    suggestion = scheduler.suggest_agenda_with_llm(context=context)
    schedule_items = suggestion.get("schedule", [])
    warnings = suggestion.get("warnings", [])

    if not schedule_items:
        notifier.warning(
            "LLM não gerou sugestões. Verifique se há tarefas cadastradas.", "scheduler"
        )
        return

    headers = ["Horário", "Tarefa", "Prioridade"]
    rows = [
        [
            item.get("time_slot", "?"),
            item.get("task_title", "?")[:40],
            item.get("priority", "?"),
        ]
        for item in schedule_items
    ]
    notifier.print_table(headers, rows, "AGENDA SUGERIDA")

    for w in warnings:
        notifier.warning(w, "scheduler")

    apply = input("  Aplicar esta agenda? [s/N]: ").strip().lower()
    if apply == "s":
        ids = scheduler.apply_llm_suggestion(suggestion)
        notifier.success(f"{len(ids)} bloco(s) criados na agenda.", "scheduler")


def cmd_demo() -> None:
    """Cria dados de demonstração para testar o sistema."""
    notifier.separator("MODO DEMO")
    notifier.info("Criando dados de demonstração...", "demo")

    # Cria algumas tarefas de exemplo
    today = date.today().isoformat()
    tasks = [
        {
            "title": "Revisar Pull Requests",
            "priority": "Alta",
            "scheduled_time": f"{today} 09:00",
        },
        {
            "title": "Reunião de alinhamento",
            "priority": "Alta",
            "scheduled_time": f"{today} 10:30",
        },
        {
            "title": "Implementar feature X",
            "priority": "Média",
            "scheduled_time": f"{today} 14:00",
        },
        {
            "title": "Responder emails",
            "priority": "Baixa",
            "scheduled_time": f"{today} 16:00",
        },
        {
            "title": "Revisão de código",
            "priority": "Média",
            "scheduled_time": f"{today} 17:00",
        },
    ]

    created_ids = []
    for t in tasks:
        task_id = memory.create_task(**t)
        created_ids.append(task_id)
        notifier.success(f"Tarefa criada: '{t['title']}' (ID: {task_id})", "demo")

    # Cria blocos de agenda
    blocks = [
        ("09:00-10:00", "Revisar Pull Requests", created_ids[0]),
        ("10:30-11:30", "Reunião de alinhamento", created_ids[1]),
        ("12:00-13:00", "Almoço — pausa", None),
        ("14:00-15:30", "Implementar feature X", created_ids[2]),
        ("16:00-16:30", "Responder emails", created_ids[3]),
        ("17:00-18:00", "Revisão de código", created_ids[4]),
    ]

    for time_slot, title, task_id in blocks:
        scheduler.add_schedule_block(time_slot, title, task_id)

    # Marca a primeira como "Em progresso"
    memory.update_task_status(created_ids[0], "Em progresso")

    notifier.success("Dados de demonstração criados!", "demo")
    notifier.info("Execute 'python main.py status' para ver o resumo.", "demo")
    notifier.separator()


# ---------------------------------------------------------------------------
# Modo interativo (REPL)
# ---------------------------------------------------------------------------


def cmd_chat() -> None:
    """
    Modo de chat interativo com o Orchestrator.
    O usuário escreve em linguagem natural e o sistema delega aos agentes.
    """
    # Inicia o Focus Guard em background automaticamente
    if not focus_guard.is_running():
        focus_guard.start_guard()

    notifier.separator("MODO INTERATIVO")
    notifier.info("Digite sua solicitação em linguagem natural.", "chat")
    notifier.info(
        "Comandos especiais: /status | /agenda | /tasks | /sync | /demo | /quit", "chat"
    )
    notifier.separator()

    conversation_history = []

    while True:
        try:
            user_input = input(
                f"\n{notifier.Color.CYAN}Você:{notifier.Color.RESET} "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # Comandos especiais com /
        if user_input.startswith("/"):
            cmd = user_input.lstrip("/").lower()
            if cmd in ("quit", "exit", "sair"):
                break
            elif cmd == "status":
                cmd_status()
            elif cmd == "agenda":
                cmd_agenda()
            elif cmd == "tasks":
                cmd_tasks()
            elif cmd == "sync":
                cmd_sync()
            elif cmd == "demo":
                cmd_demo()
            elif cmd.startswith("focus start"):
                parts = cmd.split()
                task_id = (
                    int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
                )
                cmd_focus_start(task_id)
            elif cmd == "focus end":
                cmd_focus_end()
            elif cmd.startswith("validate"):
                parts = cmd.split()
                task_id = (
                    int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                )
                cmd_validate(task_id)
            else:
                notifier.warning(f"Comando desconhecido: /{cmd}", "chat")
            continue

        # Processa via Orchestrator
        response = orchestrator.process(
            user_input, context={"conversation_history": conversation_history}
        )

        print(
            f"\n{notifier.Color.GREEN}{notifier.Color.BOLD}Assistente:{notifier.Color.RESET} {response}\n"
        )

        # Mantém histórico resumido (últimas 10 trocas)
        conversation_history.append({"user": user_input, "assistant": response[:200]})
        if len(conversation_history) > 10:
            conversation_history.pop(0)

    notifier.info("Saindo do modo interativo.", "chat")


# ---------------------------------------------------------------------------
# Comandos Life Guard
# ---------------------------------------------------------------------------


def cmd_vida() -> None:
    """Exibe status das rotinas pessoais do dia e dispara checks."""
    notifier.separator("LIFE GUARD — ROTINAS DO DIA")
    result = life_guard.run_all_checks()
    notifier.info(
        f"Rotinas disparadas: {result['routines'] or 'nenhuma pendente'}", "life_guard"
    )
    notifier.info(
        f"Hidratação: {'lembrete enviado' if result['hydration'] else 'ok'}",
        "life_guard",
    )
    notifier.info(
        f"Financas alertadas: {result['finances'] or 'nenhuma vencendo'}", "life_guard"
    )
    notifier.separator()


def cmd_pagar(args_str: str) -> None:
    """Registra uma conta a pagar. Uso: pagar <nome> dia <N> valor <V>"""
    # ex: "Cartao XP dia 15 valor 1200"
    match = re.match(r"(.+?)\s+dia\s+(\d+)\s+valor\s+([\d.,]+)", args_str.strip())
    if not match:
        notifier.error(
            "Formato: pagar <nome> dia <N> valor <V>  (ex: pagar Cartao XP dia 15 valor 1200)",
            "life_guard",
        )
        return
    name = match.group(1).strip()
    due_day = int(match.group(2))
    amount = float(match.group(3).replace(",", "."))
    life_guard.add_finance(name, due_day, amount)
    notifier.success(
        f"Registrado: {name} — vence dia {due_day} — R$ {amount:.2f}", "life_guard"
    )


def cmd_fiz(rotina: str) -> None:
    """Confirma que uma rotina foi feita. Uso: fiz <exercicio|banho|almoco|jantar>"""
    routine_map = {
        "exercicio": "exercise",
        "banho": "shower",
        "almoco": "lunch",
        "jantar": "dinner",
    }
    routine_id = routine_map.get(rotina.strip().lower())
    if not routine_id:
        notifier.error(
            f"Rotina desconhecida: '{rotina}'. Opcoes: {', '.join(routine_map)}",
            "life_guard",
        )
        return
    life_guard.confirm_routine(routine_id)
    notifier.success(f"Rotina '{rotina}' confirmada para hoje.", "life_guard")


# ---------------------------------------------------------------------------
# Novos comandos Phase 2
# ---------------------------------------------------------------------------


def cmd_retrospective() -> None:
    """Gera a retrospectiva semanal."""
    from agents import retrospective as retro

    notifier.separator("RETROSPECTIVA SEMANAL")

    push = input("  Criar página no Notion? [s/N]: ").strip().lower() == "s"
    result = retro.run_retrospective(push_to_notion=push)

    m = result["metrics"]
    notifier.success(
        f"Retrospectiva gerada! Foco: {m['total_focus_hours']}h | "
        f"Tarefas: {m['tasks_completed']} | Taxa: {m['completion_rate_pct']}%"
    )
    notifier.info(f"Salvo em: {result['local_path']}", "retrospective")

    print(f"\n{result['report_preview']}")


def cmd_web() -> None:
    """Inicia a interface web."""
    import uvicorn

    from config import WEB_HOST, WEB_PORT

    notifier.info(f"Iniciando interface web em http://{WEB_HOST}:{WEB_PORT}", "web")
    uvicorn.run("web.app:app", host=WEB_HOST, port=WEB_PORT, reload=False)


def cmd_calendar_auth() -> None:
    """Autoriza a integração opcional com Google Calendar."""
    from agents import calendar_sync

    notifier.info(
        "Iniciando fluxo de autorização da integração opcional com Google Calendar...",
        "calendar",
    )
    notifier.info("O browser será aberto para autorização.", "calendar")
    if calendar_sync.authorize():
        notifier.success(
            "Autorização concluída! Use 'calendar import' para importar eventos."
        )
    else:
        notifier.error("Autorização falhou. Verifique o credentials.json.")


def cmd_calendar_import() -> None:
    """Importa eventos de hoje da integração opcional com Google Calendar."""
    from agents import calendar_sync

    count = calendar_sync.import_today_as_blocks()
    notifier.success(f"{count} evento(s) importados como blocos de agenda.")


def cmd_calendar_status() -> None:
    """Status da integração opcional com o Google Calendar."""
    from agents import calendar_sync

    notifier.separator("GOOGLE CALENDAR STATUS")
    notifier.info(f"Autorizado: {calendar_sync.is_authorized()}", "calendar")
    notifier.info(f"Calendário: {calendar_sync.GOOGLE_CALENDAR_ID}", "calendar")
    if calendar_sync.is_authorized():
        events = calendar_sync.fetch_today_events()
        notifier.info(f"Eventos hoje: {len(events)}", "calendar")
        for ev in events[:5]:
            notifier.info(f"  {ev['time_slot']} — {ev['title']}", "calendar")
    notifier.separator()


# ---------------------------------------------------------------------------
# Parser CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="multiagentes",
        description="Gate with nodes multiagents to archtect NEØ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python main.py                     # Modo interativo
  python main.py status              # Status do sistema
  python main.py agenda              # Agenda de hoje
  python main.py tasks               # Lista de tarefas
  python main.py add-task            # Wizard para nova tarefa
  python main.py sync                # Sincroniza com Notion
  python main.py suggest             # Sugestão de agenda via LLM
  python main.py focus start 3       # Foca na tarefa ID 3
  python main.py focus end           # Encerra sessão de foco
  python main.py validate 3          # Valida tarefa ID 3
  python main.py demo                # Cria dados de demonstração
        """,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMANDO")

    # chat / interativo
    subparsers.add_parser("chat", help="Modo interativo com o Orchestrator")

    # status
    subparsers.add_parser("status", help="Status completo do sistema")

    # agenda
    subparsers.add_parser("agenda", help="Exibe agenda de hoje")

    # tasks
    subparsers.add_parser("tasks", help="Lista todas as tarefas")

    # add-task
    subparsers.add_parser("add-task", help="Wizard para adicionar nova tarefa")

    # sync
    subparsers.add_parser("sync", help="Sincroniza com Notion")

    # suggest
    subparsers.add_parser("suggest", help="Sugere agenda otimizada via LLM")

    # focus
    focus_parser = subparsers.add_parser("focus", help="Gerencia sessões de foco")
    focus_sub = focus_parser.add_subparsers(dest="focus_action", metavar="AÇÃO")
    focus_start = focus_sub.add_parser("start", help="Inicia sessão de foco")
    focus_start.add_argument("task_id", type=int, nargs="?", help="ID da tarefa")
    focus_sub.add_parser("end", help="Encerra sessão de foco ativa")

    # validate
    validate_parser = subparsers.add_parser(
        "validate", help="Valida conclusão de tarefa"
    )
    validate_parser.add_argument("task_id", type=int, nargs="?", help="ID da tarefa")

    # demo
    subparsers.add_parser("demo", help="Cria dados de demonstração")

    # retrospective
    subparsers.add_parser("retrospective", help="Gera retrospectiva semanal")

    # web
    subparsers.add_parser("web", help="Inicia interface web (FastAPI)")

    # vida / life guard
    subparsers.add_parser("vida", help="Status das rotinas pessoais do dia")
    subparsers.add_parser("life", help="Status das rotinas pessoais do dia (alias)")

    pagar_parser = subparsers.add_parser(
        "pagar", help="Registra conta a pagar (ex: pagar Cartao XP dia 15 valor 1200)"
    )
    pagar_parser.add_argument("args", nargs=argparse.REMAINDER)

    fiz_parser = subparsers.add_parser(
        "fiz", help="Confirma rotina feita (ex: fiz banho)"
    )
    fiz_parser.add_argument("rotina", nargs="?", default="")

    # ecosistema
    subparsers.add_parser(
        "ecosistema", help="Health check e relatório do ecossistema externo"
    )

    # github projects → Notion (Command Center)
    github_parser = subparsers.add_parser(
        "github",
        help="GitHub Projects v2: discover (manifests) e sync para NOTION_DB_TAREFAS",
    )
    gh_sub = github_parser.add_subparsers(
        dest="github_action",
        metavar="AÇÃO",
        required=True,
    )
    gh_disc = gh_sub.add_parser(
        "discover",
        help="Compara manifests neomello/*/manifests com GITHUB_PROJECTS em config",
    )
    gh_disc.add_argument(
        "--root",
        default=None,
        help="Pasta raiz dos org workspaces (default: NEOMELLO_WORKSPACES_ROOT)",
    )
    gh_sync = gh_sub.add_parser(
        "sync",
        help="Importa issues/PRs dos boards configurados para o Notion",
    )
    gh_sync.add_argument(
        "--org",
        default=None,
        help="Sincroniza só esta org (ex: flowpay-system). Default: todas em config.",
    )
    gh_sync.add_argument(
        "--dry-run",
        action="store_true",
        help="Só lista o que seria criado/atualizado (sem Notion/Redis)",
    )
    gh_sub.add_parser(
        "reset-map",
        help="Limpa mapa issue→Notion no Redis (próximo sync recria linhas)",
    )
    gh_sub.add_parser(
        "notion-check",
        help="Mostra schema do NOTION_DB_TAREFAS + amostra de páginas (diagnóstico)",
    )

    # capture (segundo cérebro)
    capture_parser = subparsers.add_parser(
        "capture",
        help="Classifica texto livre e salva no database Notion correto (NEØ Command Center)",
    )
    capture_parser.add_argument("text", nargs=argparse.REMAINDER)

    capture_classify_parser = subparsers.add_parser(
        "classify",
        help="Mostra como o classificador categorizaria um texto (dry-run)",
    )
    capture_classify_parser.add_argument("text", nargs=argparse.REMAINDER)

    # telegram bot (long-poll — bloqueante)
    subparsers.add_parser(
        "telegram", help="Inicia o bot do Telegram em long-poll (worker mode)"
    )

    # calendar
    calendar_parser = subparsers.add_parser(
        "calendar", help="Gerencia integração opcional com Google Calendar"
    )
    cal_sub = calendar_parser.add_subparsers(dest="calendar_action", metavar="AÇÃO")
    cal_sub.add_parser("auth", help="Autoriza acesso opcional ao Google Calendar")
    cal_sub.add_parser(
        "import", help="Importa eventos opcionais de hoje como blocos de agenda"
    )
    cal_sub.add_parser("status", help="Status da integração opcional com o Calendar")

    return parser


# ---------------------------------------------------------------------------
# Capture (segundo cérebro → NEØ Command Center)
# ---------------------------------------------------------------------------


def cmd_capture(text: str) -> None:
    text = (text or "").strip()
    if not text:
        notifier.error("Uso: python main.py capture <texto livre>", "main")
        return
    from agents import capture_agent
    import json as _json

    result = capture_agent.capture(text, source="cli")
    if result.get("status") == "ok":
        notifier.success(
            f"[{result['category']}] → {result['destination']}", "capture"
        )
        if result.get("notion_url"):
            print(f"  {result['notion_url']}")
    else:
        notifier.error(f"Falhou: {result.get('error')}", "capture")
        print(_json.dumps(result, indent=2, ensure_ascii=False))


def cmd_github(args) -> None:
    """GitHub Projects v2: discover local manifests ou sync → Notion."""
    from pathlib import Path

    from agents import github_projects

    if args.github_action == "discover":
        root = Path(args.root).expanduser() if args.root else None
        text = github_projects.discover_compare_with_config(
            root_override=root,
        )
        print(text)
    elif args.github_action == "sync":
        if args.org:
            c, u = github_projects.sync_org_to_notion(
                args.org.strip(),
                dry_run=args.dry_run,
            )
            notifier.separator("GITHUB → NOTION")
            notifier.info(f"{args.org}: criadas={c} atualizadas={u}", "github")
            notifier.separator()
        else:
            res = github_projects.sync_all_orgs(dry_run=args.dry_run)
            notifier.separator("GITHUB → NOTION (todas as orgs)")
            for org, (c, u) in res.items():
                notifier.info(f"{org}: criadas={c} atualizadas={u}", "github")
            notifier.separator()
    elif args.github_action == "reset-map":
        github_projects.clear_issue_notion_map()
        notifier.success(
            "Mapa GitHub→Notion limpo no Redis. Próximo sync cria páginas novamente "
            "(páginas antigas no Notion continuam lá — evita duplicar se não limpares o DB).",
            "github",
        )
    elif args.github_action == "notion-check":
        print(github_projects.notion_tarefas_diagnostic())


def cmd_classify(text: str) -> None:
    text = (text or "").strip()
    if not text:
        notifier.error("Uso: python main.py classify <texto livre>", "main")
        return
    from agents import capture_agent
    import json as _json

    cls = capture_agent.classify(text)
    print(_json.dumps(cls, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
