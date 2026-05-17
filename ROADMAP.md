# Roadmap — mypersonal_multiagents

**Atualizado em:** 16/05/2026  
**Estado atual:** v0.6.0 — core estabilizado, Notion removido, Linear operacional

---

## Stack atual

| Camada | Tecnologia |

| Task store | Linear (GraphQL API) |
| Hot state | Redis (Railway) |
| Entrada | Telegram bot (inline keyboard) |
| Loop central | focus_guard daemon (Railway) |
| LLM | GPT-4o-mini via core/openai_utils.py |
| Config | Env vars + hardcoded fallbacks |
| Deploy | Railway — 2 processos via Procfile |

**Agentes ativos:** capture_agent, ecosystem_monitor, focus_guard, github_projects, linear_sync, orchestrator, scheduler, telegram_bot, validator

---

## Histórico de fases

### Fase 0 — Ativação ✅

Configuração inicial, fluxo demo → status → sync validado.

### Fase 1 — Estabilização ✅

- Focus Guard persistente via Procfile Railway (daemon process)
- Testes automatizados com pytest
- Retry com backoff via tenacity

### Fase 2 — Capacidades core ✅ / ⚠️ parcial

| Item | Estado | Nota |

| Captura de tarefas | ✅ | Linear em vez de Notion |
| Telegram bot | ✅ | Inline keyboard com 4 ações |
| Focus guard check-in | ✅ | Notificação bidirecional |
| Ecosystem monitor | ✅ | GitHub + Railway + DexScreener |
| GitHub sync | ✅ | GraphQL GitHub Projects v2 |
| Orchestrator | ✅ | Roteamento por linguagem natural |
| Interface web | ❌ removida | Fora do escopo atual |
| Google Calendar | ❌ removida | Fora do escopo atual |
| Retrospectiva semanal | ❌ removida | Dependia do Notion |
| Persona selector | ❌ removida | Sem runtime ativo |
| life_guard | ❌ removida | Re-adicionar quando core estiver estável |
| Sanity.io | ❌ removida | Shim substituído por fallbacks hardcoded |

### Refactor v0.6.0 ✅ — 16/05/2026

- Notion removido integralmente (token, DBs, notion_sync, capture Notion)
- Linear integrado: linear_sync.py com createIssue / updateIssue via GraphQL
- capture_agent reescrito para Linear
- Telegram inline keyboard: Concluído / Fase seguinte / +1h / Bloqueado
- focus_guard dispara check-in com keyboard a cada ciclo
- Procfile consolidado: daemon + telegram (Procfile.worker removido)
- Sanity shim removido: prompts hardcoded diretamente nos agentes
- Testes órfãos deletados (Notion, Calendar, Persona, Web, Retrospectiva)

---

## Próximas fases

### Fase 3 — Completar o loop (prioridade alta)

#### 3.1 linear_sync → orchestrator registry

`ecosystem_monitor` e `github_projects` não têm `handle_handoff`. Adicionar wrapper com contrato `{status, result}` para que sejam acionáveis por linguagem natural via Telegram.

#### 3.2 life_guard — reintrodução mínima

Rotinas diárias (hidratação, refeições) como job no loop do focus_guard, sem dependência externa. Notificação via Telegram, não via mac push.

#### 3.3 Retrospectiva → Linear

Reescrever `retrospective.py` para agregar dados do Redis e criar Issues no Linear em vez de páginas Notion. Agendar toda segunda às 21h no loop do focus_guard.

#### 3.4 Testes — atualizar suite

Reescrever `test_notion_sync.py` → `test_linear_sync.py`. Adicionar testes para inline keyboard e handle_callback.

---

### Fase 4 — Arquitetura (2–3 meses)

#### 4.1 Redis Streams — coreografia assíncrona

Transição de handoffs síncronos para eventos:

- `task.created`, `session.started`, `block.overdue`
- Cada agente como consumer group
- focus_guard reage em tempo real

#### 4.2 Memória semântica

ChromaDB local + embeddings `text-embedding-3-small`:

- Retrospectiva embeda resumo diário
- Orchestrator faz RAG nos últimos 30 dias
- Insights: "você é mais produtivo entre 9h e 11h"

#### 4.3 Observabilidade

OpenTelemetry: cada handoff vira span (agente, latência, tokens).  
Export para Honeycomb ou Jaeger.

#### 4.4 Modelo local

Ollama (`llama3` / `qwen`) para análises assíncronas sem egress cloud.

---

### Fase 5 — Expansão (3–6 meses)

#### 5.1 Slack / Discord

Webhook quando ecosystem_monitor detecta falha crítica ou focus_guard detecta desvio severo.

#### 5.2 OpenAI Agents SDK

Migrar de handoffs manuais para SDK oficial com tracing integrado e guardrails por agente.

#### 5.3 Ciclo privado → público

Política documentada: artefatos promovidos do kernel privado para nettomello.eth.limo via Sanity → IPFS. Nenhum agente publica sem eclusa explícita.

---

## Decisões de arquitetura vigentes

| Decisão | Atual | Próximo |

| Task store | Linear (GraphQL) | — |
| Hot state | Redis Railway | + Redis Streams |
| Entrada | Telegram inline keyboard | + Slack webhook |
| LLM | GPT-4o-mini | + modelo local Ollama |
| Deploy | Railway Procfile 2 processos | — |
| Config externa | Env vars + hardcoded fallbacks | — |
| Alertas | Telegram | + Slack/Discord |
| Memória | Redis | + ChromaDB semântico |
| Testes | pytest parcial | + cobertura linear_sync |
| Publicação pública | Não implementada | Sanity → IPFS |
