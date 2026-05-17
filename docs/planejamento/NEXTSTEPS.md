# NEXTSTEPS

Status: ativo  
Última atualização: 2026-05-17

## Como este documento deve ser usado

Este arquivo é o trilho de execução do projeto.

Nenhuma frente deve ser considerada concluída sem:

1. checkbox marcado
2. nota curta em `Log`
3. referência do commit em `Commit`

## Regra de Execução

- não pular etapa
- não abrir nova frente sem fechar a anterior ou registrar bloqueio
- sempre registrar o que foi decidido
- toda decisão estrutural precisa deixar rastro

────────────────────────────────────────

## Estado pós-refactor (2026-05-17)

A migração Linear foi concluída. O sistema está estável com:

- Azure OpenAI (NEOone / gpt-oss-120b) como LLM primário
- Linear como task store canônico (capture + sync)
- Telegram Bot como inbound principal
- Notion limitado ao espelho github_projects → NOTION_DB_TAREFAS
- Sanity, Calendar, Web UI, Life Guard, Persona Manager, Retrospective removidos
- adapters/notion.py recriado como cliente HTTP compartilhado
- property helpers centralizados em adapters/notion.py

────────────────────────────────────────

## Trilha de Execução

### Fase 1. Higiene pós-migração

- [ ] Verificar logs do Railway após deploy
  - Status: TODO
  - Log: confirmar que notion_sync não aparece mais nos logs de produção após o refactor
  - Commit: pendente

- [ ] Deletar railway.worker.json
  - Status: DONE
  - Log: arquivo deletado localmente (git status: D); aguarda commit
  - Commit: pendente

- [ ] Corrigir `capture_agent.py` — README/header ainda descreve fluxo para Notion
  - Status: DONE
  - Log: fluxo atual é capture → Linear; arquivo não tem mais imports Notion nem helpers _p_*
  - Commit: pendente

- [x] Recriar `adapters/__init__.py` e `adapters/notion.py`
  - Status: DONE
  - Log: adapters/notion.py recriado com request() + tenacity retry + property helpers (p_title, p_rich, p_select, p_date, p_url, p_relation)
  - Commit: pendente

- [x] Remover dead code de `focus_guard.py`
  - Status: DONE
  - Log: removidos _stop_event, _ecosystem_lock, _github_lock, _fire_and_forget,
  _run_ecosystem_check, _run_github_sync,_background_loop (nunca chamados;
  start_guard() delega ao scheduler/runner)
  - Commit: pendente

- [x] Remover `persona_id` de 5 funções do `orchestrator.py`
  - Status: DONE
  - Log: persona_manager foi removido; persona_id era parâmetro sem efeito nas 5 funções afetadas
  - Commit: pendente

- [x] Remover `auto_sync_notion` de `scheduler.apply_llm_suggestion`
  - Status: DONE
  - Log: parâmetro nunca usado no body da função
  - Commit: pendente

### Fase 2. Cobertura de testes

- [ ] Criar `tests/test_linear_sync.py`
  - Status: TODO
  - Log: substitui `tests/test_notion_sync.py` (deletado). Cobrir: create_from_classification, handle_handoff, sync_issues_to_memory
  - Commit: pendente

- [ ] Corrigir `tests/test_focus_guard.py` — falha pré-existente
  - Status: TODO
  - Log: `test_focus_guard_reagenda_bloco_atrasado_e_audita` falha com assert 1 == 2 (bloco não está sendo reagendado). Bug pré-existente não causado pelo refactor.
  - Commit: pendente

### Fase 3. Orchestrator — expandir registry

- [ ] Adicionar `handle_handoff` ao `ecosystem_monitor.py`
  - Status: TODO
  - Log: atualmente não é roteável pelo Orchestrator (não está em _AGENT_HANDLERS). Adicionar `handle_handoff(payload)` que expõe `health_check` e `daily_report`
  - Commit: pendente

- [ ] Adicionar `handle_handoff` ao `github_projects.py`
  - Status: TODO
  - Log: atualmente não é roteável. Adicionar `handle_handoff(payload)` que expõe `sync_all_orgs`, `notion_tarefas_diagnostic`, `reset_issue_map`
  - Commit: pendente

- [ ] Registrar ecosystem_monitor e github_projects em `_AGENT_HANDLERS` do orchestrator
  - Status: TODO
  - Log: depende das duas tarefas acima
  - Commit: pendente

### Fase 4. Procfile e Railway

- [ ] Confirmar estratégia de deploy Railway
  - Status: TODO
  - Log: Procfile atual tem `daemon` + `telegram` como dois serviços. Decidir se mantém dois processos no mesmo app Railway ou usa um `start.sh` que sobe os dois em background + foreground. Deletar railway.worker.json confirmado.
  - Commit: pendente

### Fase 5. Agentes removidos — reintrodução seletiva

- [ ] Avaliar reintrodução mínima de `life_guard`
  - Status: TODO
  - Log: Life Guard original monitorava água, postura, pausas. Candidato a reintrodução via Telegram (sem web UI). Escopo: apenas alertas Telegram agendados via cron interno.
  - Commit: pendente

- [ ] Reescrever `retrospective` para Linear
  - Status: TODO
  - Log: retrospective.py foi removido. Nova versão deve: ler issues concluídas no Linear dos últimos 7 dias, gerar síntese via LLM, criar Linear issue tipo "Retrospective" ou persistir no Redis
  - Commit: pendente

────────────────────────────────────────

## Higiene contínua

- Nunca commitar `.claude/settings.local.json` ou `dump.rdb`
- Redis local: `brew services start redis` (brew nativo, não Docker)
- Todo commit segue `make check` → Conventional Commits → `git push`

## Registros

### 2026-05-17

- Migração Linear completa: capture_agent → Linear (não Notion)
- Azure OpenAI (NEOone) como LLM primário
- Dead code removido: focus_guard, orchestrator, scheduler
- adapters/notion.py recriado com helpers centralizados
- github_projects: duplicatas de _p_* removidas, importa de adapters.notion
- Sanity, Calendar, Web UI, Life Guard, Persona Manager, Retrospective deletados
- AGENTS.md, MEMORY.md e NEXTSTEPS.md atualizados
