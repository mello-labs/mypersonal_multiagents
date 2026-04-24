# Roadmap — Sistema de Multiagentes para Gestão Pessoal

**Atualizado em:** 24/04/2026
**Estado atual:** v0.5.1 — Fase 4 operacional (OpenAI Agents SDK + ChromaDB + OpenTelemetry + Redis Streams + Sprints Vida/Ecossistema + Sanity completo + UI renovada + Docker + K8s)

---

## Fase 0 — Ativação ✅ concluída

- [x] Configurar `.env` com `OPENAI_API_KEY`, `NOTION_TOKEN`, `NOTION_TASKS_DB_ID`, `NOTION_AGENDA_DB_ID`
- [x] Databases no Notion com estrutura exata (Tarefas + Agenda Diária)
- [x] Fluxo validado: `demo` → `status` → `sync` → modo interativo

---

## Fase 1 — Estabilização ✅ parcialmente concluída

### 1.1 Focus Guard persistente ⏳ pendente

**Problema:** o Focus Guard morre quando o terminal fecha.

**Solução — macOS (launchd):**
Criar `~/Library/LaunchAgents/com.multiagentes.focusguard.plist` apontando para `python main.py` com `KeepAlive = true`.

**Solução — Linux (systemd):**

```ini
[Unit]
Description=Multiagentes Focus Guard

[Service]
ExecStart=/usr/bin/python3 /caminho/main.py
Restart=always

[Install]
WantedBy=default.target
```

Script `scripts/install_launchd.sh` já existe no repo.

### 1.2 Logging estruturado ⏳ pendente

Trocar o logging atual por **structlog** ou **loguru** para:

- Filtrar logs por agente
- Exportar JSON para análise posterior
- Correlacionar handoffs pelo `handoff_id`

### 1.3 Testes automatizados ✅ concluída

Suite `tests/` com pytest cobrindo:

- `test_memory.py` — operações CRUD
- `test_focus_guard.py` — análise de progresso, escalada
- `test_notion_sync.py` — mock de requests
- `test_orchestrator.py` — roteamento e handoffs
- `test_web_chat.py` — rotas FastAPI

### 1.4 Tratamento de rate limit da Notion API ✅ concluída

Retry com backoff exponencial via `tenacity` aplicado em `notion_sync._request()`. Retrospective.py também usa o mesmo mecanismo (corrigido em auditoria A5).

---

## Fase 2 — Novas capacidades ✅ operacional

### 2.1 Sync bidirecional com Notion ✅ concluída

Polling diferencial implementado: `notion_sync.sync_differential()` com filtro `last_edited_time`. Rodando automaticamente no loop do Focus Guard a cada `NOTION_SYNC_INTERVAL` minutos.

### 2.2 Agente de Retrospectiva Semanal ✅ concluída

`agents/retrospective.py` — lê focus_sessions e handoffs da semana, calcula métricas (taxa de conclusão, tempo real vs. planejado), gera relatório via GPT-4o, cria página no Notion.

Acionado via `python main.py retrospective` ou `make retro`.

### 2.3 Interface Web (FastAPI + HTMX) ✅ concluída

PWA completa com 5 tabs:

| Rota | Função |
|------|--------|
| `/` | Dashboard (métricas, agenda do dia, tarefas) |
| `/agenda` | Agenda navegável com filtro de datas e importação |
| `/tasks-page` | Criar e gerenciar tarefas |
| `/chat-page` | Chat full-screen com Orchestrator |
| `/audit` | Eventos, alertas, handoffs, logs |

Detalhes em `docs/operacao/MANUAL_DEV.md` e `docs/operacao/MANUAL_USUARIO.md`.

### 2.4 Google Calendar opcional ✅ concluída

`agents/calendar_sync.py` — OAuth 2.0 completo, importa eventos como blocos de agenda, respeita timezone local. Mantido como integração opcional, com Notion Agenda como fonte primária de operação.

Acionado via `python main.py calendar auth|import|status` ou `make calendar-auth|calendar-import`.

### 2.5 SPRINT VIDA — Interrupção Cognitiva ✅ concluída

Implementado conforme `docs/planejamento/SPRINT_VIDA.md`:

- **`core/notifier.py`** — `mac_push()` (osascript) + `alexa_announce()` (Voice Monkey)
- **`agents/focus_guard.py`** — `ESCALATION_LEVELS` com 4 níveis (30min/60min/2h/4h), canais mac/alexa
- **`agents/life_guard.py`** — rotinas diárias (exercício, banho, almoço, jantar), hidratação cada 90min, alertas de finanças
- **`main.py`** — comandos `vida`, `fiz <rotina>`, `pagar <nome> dia <N> valor <V>`

### 2.6 Persona Selector ✅ concluída

`agents/persona_manager.py` — carrega personas de `/personas/*.json`, injeta system prompt dinâmico no Orchestrator. 3 personas: architect, coordinator, taylor.

### 2.7 Sanity.io — Externalização de Prompts ✅ parcialmente concluída

- **`core/sanity_client.py`** — GROQ queries, cache 5min, fallback para hardcoded
- **Projeto Sanity** — `n4dgl02q`, dataset `production`, API token configurado
- **`agents/focus_guard.py`** — já consome prompt via `sanity_client.get_prompt()`
- **Sanity Studio** — scaffolding em `sanity/`, schemas pendentes de deploy
- **Pendente:** deploy dos 4 schemas (`llm_prompt`, `persona`, `agent_config`, `intervention_script`) e migração dos prompts hardcoded

Detalhes em `docs/arquitetura/SANITY_SCHEMA.md`.

### 2.8 Auditoria de Código ✅ concluída

13 issues identificadas e corrigidas (6 HIGH, 7 MEDIUM). Registro completo em `docs/auditoria/AUDITORIA_AGENTES.md`.

---

## Fase 3 — Arquitetura avançada (2–3 meses)

### 3.1 Migrar para o OpenAI Agents SDK oficial

O SDK `openai-agents` fornece:

- **Handoffs declarativos** — `handoff(agent, tool_choice="required")`
- **Guardrails** — validação de input/output por agente
- **Tracing integrado** — visualização do grafo de execução
- **Streaming de respostas**

```python
from agents import Agent, Runner, handoff, function_tool

orchestrator = Agent(
    name="Orchestrator",
    instructions="...",
    handoffs=[
        handoff(scheduler_agent),
        handoff(focus_guard_agent),
        handoff(notion_sync_agent),
    ],
)

result = await Runner.run(orchestrator, user_input)
```

### 3.2 Memória semântica de longo prazo

Embeddings + **ChromaDB** (local, sem servidor):

- Retrospectiva embeda resumo diário via `text-embedding-3-small`
- Orchestrator faz RAG no histórico dos últimos 30 dias
- Permite insights como "você é mais produtivo entre 9h e 11h"

### 3.3 Observabilidade com OpenTelemetry

- Cada handoff vira um **span** (agente origem, destino, latência, tokens)
- Export para **Jaeger** (local) ou **Honeycomb** (cloud)
- Dashboard de custo por agente

### 3.4 Comunicação via Redis Streams

Transição de orquestração síncrona para coreografia (push):

- Orchestrator publica eventos (`task.created`, `session.started`, `block.overdue`)
- Cada agente é consumer group que reage aos eventos relevantes
- Focus Guard reage em tempo real em vez de polling

---

## Fase 4 — Integrações externas (3–6 meses)

### 4.1 SPRINT ECOSSISTEMA — Monitoramento ativo ⏳ próximo

`agents/ecosystem_monitor.py` — spec completa em `docs/planejamento/SPRINT_ECOSSISTEMA.md`:

- GitHub: commits, PRs, issues por org (6 orgs)
- Railway: status de serviços via GraphQL
- Vercel: deploys recentes
- On-chain: NEOFLW token via DexScreener
- Relatório diário 20h via mac push
- Health check a cada 30min

### 4.2 Linear / Jira como fonte de tarefas profissionais

`agents/project_sync.py` — lê issues atribuídas e importa como tarefas locais.

### 4.3 Slack / Discord para alertas fora do terminal

Focus Guard envia via webhook quando detecta desvio severo.

### 4.4 Modelo local via Ollama

`llama3` / `mistral` / `qwen` para análises assíncronas de longo prazo sem egress para cloud.

---

## Referência rápida de decisões de arquitetura

| Decisão | Hoje | Próximo passo |
|---|---|---|
| Persistência | Redis (Railway) + SQLite fallback | + ChromaDB para memória semântica |
| Comunicação entre agentes | Handoffs síncronos via função | Redis Streams (async, pub/sub) |
| LLM | GPT-4o-mini (OpenAI API) | + modelo local (Ollama) |
| SDK de agentes | OpenAI client via `core/openai_utils.py` | `openai-agents` SDK oficial |
| Focus Guard | Thread daemon no processo web | Processo systemd/launchd dedicado |
| Interface | CLI + Web (FastAPI + HTMX + PWA) | PWA com push notifications |
| Fonte de agenda | Notion (principal) + Google Calendar (opcional) | + Linear/Jira |
| Observabilidade | Logs em arquivo + audit trail Redis | OpenTelemetry + Jaeger |
| Alertas | Terminal + macOS push + Alexa (Voice Monkey) | + Slack/Discord webhook |
| Testes | pytest (5 modules) | + integration tests + coverage gate |
| Config externa | Sanity.io (prompts, personas, agent config) | Deploy schemas + migrar todos os prompts |
| Notificações | macOS osascript + Voice Monkey | + Web Push + Telegram |
