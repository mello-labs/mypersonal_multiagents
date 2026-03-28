# Roadmap — Sistema de Multiagentes para Gestão Pessoal
**Atualizado em:** 25/03/2026
**Estado atual:** v0.1 — MVP funcional (CLI + 5 agentes + SQLite + Notion REST)

---

## Fase 0 — Ativação (agora)

Antes de qualquer evolução, o sistema precisa estar rodando de verdade.

**1. Configurar o ambiente**
- Copiar `.env.example` para `.env` e preencher `OPENAI_API_KEY`, `NOTION_TOKEN`, `NOTION_TASKS_DB_ID`, `NOTION_AGENDA_DB_ID`
- `pip install -r requirements.txt`

**2. Criar os databases no Notion com a estrutura exata**

Database **Tarefas**:
| Campo | Tipo |
|---|---|
| Nome | Title |
| Status | Select → "A fazer", "Em progresso", "Concluído" |
| Prioridade | Select → "Alta", "Média", "Baixa" |
| Horário previsto | Rich Text |
| Horário real | Rich Text |

Database **Agenda Diária**:
| Campo | Tipo |
|---|---|
| Data | Date |
| Bloco horário | Rich Text |
| Tarefa vinculada | Relation → Tarefas |
| Concluído | Checkbox |

**3. Validar o fluxo completo**
```bash
python main.py demo       # popula dados de teste
python main.py status     # verifica se tudo está lendo o SQLite
python main.py sync       # valida conexão com o Notion
python main.py            # entra no modo interativo e testa um comando natural
```

---

## Fase 1 — Estabilização (próximas 1–2 semanas)

### 1.1 Tornar o Focus Guard um processo persistente

**Problema atual:** o Focus Guard morre quando o terminal fecha.

**Solução — macOS (launchd):**
Criar `~/Library/LaunchAgents/com.multiagentes.focusguard.plist` apontando para `python main.py` com `KeepAlive = true`. O sistema operacional reinicia automaticamente se o processo cair.

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

**Alternativa mais simples:** extrair o Focus Guard para um `focus_guard_service.py` standalone que só roda o loop, e chamar via `nohup python focus_guard_service.py &` num script de startup.

### 1.2 Logging estruturado

Trocar o logging simples por **structlog** ou **loguru**. Isso permite:
- Filtrar logs por agente
- Exportar para JSON para análise posterior
- Correlacionar handoffs pelo `handoff_id`

### 1.3 Testes automatizados

Criar `tests/` com pytest cobrindo pelo menos:
- `memory.py` — todas as operações CRUD (rodar com banco in-memory `:memory:`)
- `scheduler.py` — detecção de conflitos e cálculo de carga
- `validator.py` — lógica de `check_data_consistency` sem LLM
- `notion_sync.py` — mockar o `requests` com `responses` ou `httpx` para não chamar a API real

### 1.4 Tratamento de rate limit da Notion API

A Notion API tem limite de 3 req/s. Adicionar retry com backoff exponencial em `notion_sync._request()`:
```python
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
```

---

## Fase 2 — Novas capacidades (próximo mês)

### 2.1 Sync bidirecional em tempo real com Notion

**Hoje:** sync é manual (você chama `sync`).
**Próximo:** polling periódico no Focus Guard (a cada N minutos, verifica mudanças no Notion e atualiza o SQLite local).

Notion não tem webhooks nativos por integração (apenas via automations internas), então a abordagem mais prática é um **polling diferencial**: guardar o timestamp da última sync em `system_state` e usar o filtro `last_edited_time` na query do database.

```python
# Em notion_sync.py
def fetch_tasks_modified_since(last_sync_iso: str) -> list[dict]:
    payload = {
        "filter": {
            "timestamp": "last_edited_time",
            "last_edited_time": {"after": last_sync_iso}
        }
    }
```

### 2.2 Agente de Retrospectiva Semanal

Novo agente `agents/retrospective.py` que:
1. Lê todas as `focus_sessions` e `agent_handoffs` da semana
2. Calcula métricas: taxa de conclusão, tempo médio real vs. planejado, horários mais produtivos
3. Gera um relatório via GPT-4o com insights e sugestões para a semana seguinte
4. Cria uma página de retrospectiva no Notion automaticamente

Acionado via:
```bash
python main.py retrospective   # ou automatizado todo domingo às 18h via systemd
```

### 2.3 Interface Web leve (FastAPI + HTMX)

Em vez de só CLI, expor o Orchestrator via HTTP:

```
POST /chat          → orchestrator.process(user_input)
GET  /status        → orchestrator.get_system_summary()
GET  /agenda        → scheduler.get_today_schedule()
POST /task          → criar tarefa
PATCH /task/{id}    → atualizar status
```

Frontend: **HTMX** + templates Jinja2 — sem build step, sem Node, abre no browser. O Focus Guard continua rodando em background thread dentro do mesmo processo FastAPI via `lifespan`.

### 2.4 Google Calendar como fonte de verdade do Scheduler

Integrar a **Google Calendar API** para:
- Importar eventos do calendário como blocos de agenda (reuniões já agendadas criam blocos automaticamente)
- Bloquear horários ocupados antes de sugerir agenda
- Exportar blocos criados pelo Scheduler de volta ao calendário

```python
# agents/calendar_sync.py (novo agente)
from googleapiclient.discovery import build
```

O Orchestrator passaria a acionar `calendar_sync` antes do `scheduler` para ter contexto completo do dia.

---

## Fase 3 — Arquitetura avançada (2–3 meses)

### 3.1 Migrar para o OpenAI Agents SDK oficial

O SDK `openai-agents` (lançado em março de 2025) fornece primitivas nativas de:
- **Handoffs declarativos** — `handoff(agent, tool_choice="required")`
- **Guardrails** — validação de input/output por agente
- **Tracing integrado** — visualização do grafo de execução no OpenAI dashboard
- **Streaming de respostas** — o Orchestrator streama enquanto os agentes processam

A migração do `orchestrator.py` atual (que faz roteamento manual via JSON) para o SDK reduz código e adiciona observabilidade nativa. O restante dos agentes (`scheduler`, `focus_guard`, etc.) vira `@function_tool` registrado no agente orquestrador.

```python
from agents import Agent, Runner, handoff, function_tool

scheduler_agent = Agent(
    name="Scheduler",
    instructions="...",
    tools=[get_today_schedule, add_schedule_block, suggest_agenda],
)

orchestrator = Agent(
    name="Orchestrator",
    instructions="...",
    handoffs=[
        handoff(scheduler_agent),
        handoff(focus_guard_agent),
        handoff(notion_sync_agent),
        handoff(validator_agent),
    ],
)

result = await Runner.run(orchestrator, user_input)
```

### 3.2 Memória semântica de longo prazo

**Problema:** o Orchestrator não aprende com o histórico. Hoje ele só tem acesso ao SQLite estruturado — não "lembra" que você sempre atrasa tarefas de sexta à tarde, ou que reuniões de 2h te deixam sem foco.

**Solução:** adicionar uma camada de **embeddings + vector store**:

1. Ao fim de cada dia, o agente de Retrospectiva gera um resumo textual e o embeda via `text-embedding-3-small`
2. Guarda em **ChromaDB** (local, sem servidor) ou **Qdrant** (self-hosted)
3. O Orchestrator faz RAG no histórico antes de rotear: "baseado nos seus padrões dos últimos 30 dias, você costuma ser mais produtivo entre 9h e 11h — vou priorizar as tarefas de alta prioridade neste bloco"

```python
# core/long_term_memory.py
import chromadb
from openai import OpenAI

def embed_and_store(text: str, metadata: dict) -> None: ...
def retrieve_relevant_history(query: str, n=5) -> list[str]: ...
```

### 3.3 Observabilidade com OpenTelemetry

Adicionar tracing distribuído para ver o grafo completo de execução:
- Cada handoff vira um **span** com atributos (agente origem, destino, latência, tokens usados)
- Exportar para **Jaeger** (local) ou **Honeycomb** (cloud)
- Dashboard de custo por agente (tokens × preço GPT-4o)

Isso é crítico quando o sistema crescer: você vai querer saber qual agente está mais lento, qual chain tem mais falhas, e quanto está gastando por dia de uso.

### 3.4 Comunicação entre agentes via message queue

**Problema atual:** os agentes se comunicam de forma síncrona (o Orchestrator espera cada handoff terminar antes de chamar o próximo).

**Evolução:** introduzir **Redis Streams** como bus de mensagens:
- O Orchestrator publica eventos (`task.created`, `session.started`, `block.overdue`)
- Cada agente é um consumer group que reage aos eventos de seu interesse
- O Focus Guard não precisa mais de polling — ele reage ao evento `block.overdue` em tempo real
- Permite paralelismo real: Notion Sync e Scheduler processam simultaneamente

Esse padrão transforma o sistema de "orquestrado" (pull) para "coreografado" (push), o que é mais resiliente e escalável.

---

## Fase 4 — Integrações externas (3–6 meses)

### 4.1 Linear / Jira como fonte de tarefas profissionais

Novo agente `agents/project_sync.py` que lê issues atribuídas a você no Linear ou Jira e as importa como tarefas locais. O Scheduler considera deadlines de sprint ao priorizar.

### 4.2 Slack / Discord para alertas fora do terminal

O Focus Guard, além de imprimir no terminal, envia mensagem no Slack/Discord via webhook quando detecta desvio severo. Funciona mesmo com o terminal fechado (desde que o processo esteja rodando como serviço).

### 4.3 Análise de padrões com modelo local (Ollama)

Para operações de análise de histórico e retrospectiva (sem dados sensíveis saindo para a OpenAI), rodar um modelo local via **Ollama** (`llama3`, `mistral`, `qwen`). O sistema passa a ter dois clientes LLM: GPT-4o para decisões em tempo real e modelo local para análises assíncronas de longo prazo.

---

## Referência rápida de decisões de arquitetura

| Decisão | Hoje | Próximo passo |
|---|---|---|
| Persistência | SQLite local | SQLite + ChromaDB para memória semântica |
| Comunicação entre agentes | Handoffs síncronos via função | Redis Streams (async, pub/sub) |
| LLM | GPT-4o (OpenAI API) | GPT-4o + modelo local (Ollama) |
| SDK de agentes | OpenAI client manual | `openai-agents` SDK oficial |
| Focus Guard | Thread daemon | Processo systemd/launchd |
| Interface | CLI (argparse) | CLI + Web (FastAPI + HTMX) |
| Fonte de agenda | Notion manual | Notion + Google Calendar |
| Observabilidade | Logs em arquivo | OpenTelemetry + Jaeger |
| Alertas | Terminal | Terminal + Slack/Discord webhook |
| Testes | Nenhum | pytest + mocks para APIs externas |
