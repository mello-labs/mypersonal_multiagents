<!-- markdownlint-disable MD003 MD007 MD013 MD022 MD023 MD025 MD029 MD032 MD033 MD034 -->

```text
========================================
      MULTIAGENTES · PERSONAL CORE
========================================
```

![multiagentes banner](./docs/assets/multiagentes-banner.svg)

Sistema multiagentes para gestão pessoal
com orquestração por IA, agenda local
persistida em Redis, sync com Notion
como origem principal, Google Calendar
como capacidade opcional, Sanity.io
e monitoramento autônomo de foco.

> **Status:** Fase 2 operacional
> **Python:** >=3.11
> **Deploy:** Railway + Redis
> **Interface:** FastAPI + Jinja2 + HTMX (PWA)

────────────────────────────────────────

## What Is This?

A camada operacional de um sistema pessoal
que não trata produtividade como lista,
mas como fluxo entre intenção, agenda,
execução, validação e memória.

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ MULTIAGENTES CAPABILITIES           ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃
┃ Orchestrator
┃   └─ roteia intenções do usuário
┃      e consolida respostas
┃
┃ Focus Guard
┃   └─ monitora atraso, desvio,
┃      sessão de foco e reage
┃      com auto-reagendamento
┃      e escalada por tempo
┃
┃ Scheduler
┃   └─ cria, ordena e move blocos
┃      de agenda
┃
┃ Notion Sync
┃   └─ sincroniza tarefas e agenda
┃      com databases do Notion
┃
┃ Calendar Sync
┃   └─ integra Google Calendar
┃      como fonte opcional de
┃      importação e exportação
┃
┃ Validator
┃   └─ valida conclusão de tarefas
┃      com evidências cruzadas
┃
┃ Retrospective
┃   └─ gera relatório semanal com
┃      métricas e insights via LLM
┃
┃ Life Guard
┃   └─ rotinas pessoais: hidratação,
┃      exercício, refeições, finanças
┃
┃ Persona Manager
┃   └─ personas dinâmicas com
┃      injeção de system prompt
┃
┃ Ecosystem Monitor (planejado)
┃   └─ monitora GitHub, Railway,
┃      Vercel, on-chain em 6 orgs
┃
┃ Audit Trail
┃   └─ registra alertas, handoffs,
┃      desvios, logs e reações
┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

────────────────────────────────────────

## Operational Flow

```text
Usuário
  │
  ├─ Web UI (/)
  └─ CLI (main.py)
       │
       ▼
  Orchestrator
       │
       ├─ Scheduler
       ├─ Focus Guard
       │    └─ Life Guard (rotinas)
       ├─ Notion Sync
       ├─ Calendar Sync (opcional)
       ├─ Validator
       ├─ Retrospective
       └─ Persona Manager
             │
             ▼
          Redis
             │
             ├─ agenda
             ├─ tarefas
             ├─ alertas
             ├─ handoffs
             └─ auditoria
```

────────────────────────────────────────

## Quick Start

```bash
# 1. Criar ambiente e instalar dependências
make setup

# 2. Subir Redis local + app web
make dev-full

# 3. Acessar interface
open http://localhost:8000

# 4. Rodar testes
make test-q
```

> Se o Redis já estiver disponível, use `make dev`.

────────────────────────────────────────

## Core Surfaces

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ SURFACE              PURPOSE        ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Web UI               dashboard,
┃                      agenda, audit,
┃                      tasks, chat
┃ CLI                  operação local
┃                      e automação
┃ Redis                persistência
┃                      operacional
┃ Notion               fonte principal
┃                      de tarefas e agenda
┃ Google Calendar      capacidade
┃                      opcional de agenda
┃ Sanity Studio        prompts, personas
┃                      e configs externas
┃ macOS Push + Alexa   notificações de
┃                      foco e rotinas
┃ Railway              deploy web +
┃                      healthcheck
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

────────────────────────────────────────

## Repository Structure

```text
multiagentes/
├── agents/
│   ├── orchestrator.py      roteador central
│   ├── focus_guard.py       monitor de foco, escalada e auto-reschedule
│   ├── scheduler.py         agenda e blocos
│   ├── notion_sync.py       sync com Notion (bidirecional)
│   ├── calendar_sync.py     integração opcional com Google Calendar
│   ├── validator.py         validação de conclusão
│   ├── retrospective.py     retrospectiva semanal
│   ├── life_guard.py        rotinas pessoais (hidratação, exercício, finanças)
│   ├── persona_manager.py   seletor de personas dinâmicas
│   └── ecosystem_monitor.py monitoramento de projetos (planejado)
├── core/
│   ├── memory.py            persistência Redis + SQLite fallback
│   ├── openai_utils.py      wrapper central para OpenAI API
│   ├── notifier.py          logs, terminal, macOS push, Alexa
│   └── sanity_client.py     cliente Sanity.io com cache e fallback
├── web/
│   ├── app.py               FastAPI app
│   ├── templates/           páginas e partials (Jinja2 + HTMX)
│   └── static/              manifest, service worker, ícones
├── docs/
│   ├── SPRINT_VIDA.md       spec de interrupção cognitiva (implementado)
│   ├── SPRINT_ECOSSISTEMA.md spec de monitoramento de ecossistema
│   ├── SANITY_SCHEMA.md     schemas e integração Sanity.io
│   ├── AUDITORIA_AGENTES.md auditoria de código (13 issues)
│   ├── MANUAL_USUARIO.md    guia do usuário (PWA)
│   ├── MANUAL_DEV.md        guia do desenvolvedor
│   └── GUIAS_REFERENCIA.json referências externas
├── personas/
│   ├── architect.json       persona arquiteto
│   ├── coordinator.json     persona coordenador
│   └── taylor.json          persona taylor
├── sanity/                  Sanity Studio (schemas e config)
├── scripts/                 macOS launchd plist + installer
├── tests/
│   ├── test_memory.py
│   ├── test_focus_guard.py
│   ├── test_notion_sync.py
│   ├── test_orchestrator.py
│   └── test_web_chat.py
├── main.py                  entrypoint CLI
├── config.py                configuração central
├── ROADMAP.md               roadmap e próximas frentes
├── Dockerfile               build Railway
├── Procfile                 entrypoint deploy
├── railway.json             healthcheck / restart policy
├── Makefile                 operação local
└── requirements.txt         dependências Python
```

────────────────────────────────────────

## Main Pages

```text
▓▓▓ WEB INTERFACE
────────────────────────────────────────
└─ /                         dashboard principal
└─ /agenda                   agenda navegável por intervalo
└─ /tasks-page               criar e gerenciar tarefas
└─ /chat-page                chat full-screen com orchestrator
└─ /audit                    alertas, eventos, handoffs e logs
└─ /health                   healthcheck para Railway

▓▓▓ INTERACTIONS
────────────────────────────────────────
└─ /chat                     conversa com orchestrator (HTMX)
└─ /task                     criação de tarefa
└─ /task/{id}/complete       conclusão de tarefa
└─ /block/{id}/complete      conclusão de bloco
└─ /agenda/import            importação de intervalo
└─ /sync                     sincronização com Notion
└─ /tasks                    lista de tarefas (partial)
```

────────────────────────────────────────

## Integrations

| Integração      | Papel                                | Variáveis principais                                                 |
| --------------- | ------------------------------------ | -------------------------------------------------------------------- |
| OpenAI          | roteamento e síntese do orchestrator | `OPENAI_API_KEY`, `OPENAI_MODEL`                                     |
| Notion          | fonte principal de tarefas e agenda  | `NOTION_TOKEN`, `NOTION_TASKS_DB_ID`, `NOTION_AGENDA_DB_ID`          |
| Google Calendar | integração opcional de agenda        | `GOOGLE_CREDENTIALS_FILE`, `GOOGLE_TOKEN_FILE`, `GOOGLE_CALENDAR_ID` |
| Sanity.io       | prompts, personas, configs externas  | `SANITY_PROJECT_ID`, `SANITY_API_TOKEN`, `SANITY_DATASET`            |
| Voice Monkey    | anúncios na Alexa (primário)         | `VOICE_MONKEY_TOKEN`, `VOICE_MONKEY_DEVICE`, `VOICE_MONKEY_VOICE`    |
| IFTTT           | anúncios na Alexa (fallback)         | `IFTTT_WEBHOOK_KEY`, `IFTTT_ALEXA_EVENT`                             |
| Redis           | memória e persistência               | `REDIS_URL`                                                          |
| Railway         | deploy do app web                    | `PORT`, `REDIS_URL`                                                  |

────────────────────────────────────────

## Environment Variables

```bash
# --- OBRIGATÓRIO ---
OPENAI_API_KEY=              # chave OpenAI
NOTION_TOKEN=                # integration token Notion
NOTION_TASKS_DB_ID=          # database "Tarefas"
NOTION_AGENDA_DB_ID=         # database "Agenda Diária"

# --- OPENAI (opcional) ---
OPENAI_MODEL=gpt-4o-mini
OPENAI_FALLBACK_MODEL=gpt-3.5-turbo
OPENAI_MAX_TOKENS=1500
OPENAI_TEMPERATURE=0.2

# --- NOTION (opcional) ---
NOTION_RETROSPECTIVE_PAGE_ID=
NOTION_SYNC_INTERVAL=5

# --- REDIS ---
REDIS_URL=redis://localhost:6379/0

# --- GOOGLE CALENDAR (opcional) ---
GOOGLE_CREDENTIALS_FILE=./credentials.json
GOOGLE_TOKEN_FILE=./token.json
GOOGLE_CALENDAR_ID=primary

# --- SANITY.IO (opcional) ---
SANITY_PROJECT_ID=           # project ID do sanity.io/manage
SANITY_DATASET=production
SANITY_API_TOKEN=            # token com permissão Viewer
SANITY_USE_CDN=false

# --- NOTIFICAÇÕES — VOICE MONKEY (opcional) ---
VOICE_MONKEY_TOKEN=          # api-v2.voicemonkey.io
VOICE_MONKEY_DEVICE=eco-room
VOICE_MONKEY_VOICE=Ricardo

# --- NOTIFICAÇÕES — IFTTT FALLBACK (opcional) ---
IFTTT_WEBHOOK_KEY=           # ifttt.com/maker_webhooks/settings
IFTTT_ALEXA_EVENT=neo_alert

# --- LIFE GUARD (opcional) ---
LIFE_GUARD_ACTIVE_HOUR_START=8
LIFE_GUARD_ACTIVE_HOUR_END=22
LIFE_GUARD_WATER_INTERVAL=90

# --- FOCUS GUARD ---
FOCUS_CHECK_INTERVAL=15

# --- LOGGING ---
LOG_FILE=./logs/agent_system.log
LOG_LEVEL=INFO

# --- WEB ---
WEB_HOST=127.0.0.1
WEB_PORT=8000
```

────────────────────────────────────────

## Make Commands

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ COMMAND                ACTION                          ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ make setup             setup inicial (venv + deps)
┃ make dev               FastAPI local
┃ make dev-full          FastAPI + Redis
┃ make guard             Focus Guard CLI
┃ make sync              sync Notion
┃ make agenda            agenda do dia
┃ make tasks             lista tarefas
┃ make vida              status rotinas pessoais
┃ make retro             retrospectiva semanal
┃ make calendar-auth     OAuth Google Calendar opcional
┃ make calendar-import   importa eventos opcionais
┃ make test-q            testes rápidos
┃ make check             lint + testes
┃ make web               inicia interface web
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

────────────────────────────────────────

## CLI Commands

```text
python main.py                     # Modo interativo (REPL)
python main.py status              # Status do sistema
python main.py agenda              # Agenda de hoje
python main.py tasks               # Lista de tarefas
python main.py add-task            # Wizard nova tarefa
python main.py sync                # Sync com Notion
python main.py suggest             # Sugestão de agenda via LLM
python main.py focus start [id]    # Inicia sessão de foco
python main.py focus end           # Encerra sessão de foco
python main.py validate [id]       # Valida tarefa
python main.py demo                # Dados de demonstração
python main.py retrospective       # Retrospectiva semanal
python main.py web                 # Inicia interface web
python main.py vida                # Status das rotinas pessoais
python main.py fiz <rotina>        # Confirma rotina (exercicio|banho|almoco|jantar)
python main.py pagar <args>        # Registra conta a pagar
python main.py calendar auth       # Autoriza Google Calendar opcional
python main.py calendar import     # Importa eventos opcionais de hoje
python main.py calendar status     # Status da integração opcional
```

────────────────────────────────────────

## Persistence Model

- Estado operacional principal vive em Redis via [core/memory.py](./core/memory.py)
- Alertas, handoffs, agenda, sessões e auditoria são persistidos por chave
- Logs locais são gravados em arquivo configurado por `LOG_FILE`
- A interface `/audit` expõe a trilha de eventos e a cauda do log
- A agenda pode ser consultada e importada por intervalo em `/agenda`
- Prompts e configs externos gerenciados via Sanity.io com cache de 5min e fallback para hardcoded

────────────────────────────────────────

## Documentation

```text
▓▓▓ CORE DOCS
────────────────────────────────────────
└─ ROADMAP.md                  roadmap e próximas frentes
└─ docs/MANUAL_USUARIO.md      uso do sistema (PWA)
└─ docs/MANUAL_DEV.md          stack, rotas, design system

▓▓▓ SPRINTS
────────────────────────────────────────
└─ docs/SPRINT_VIDA.md         interrupção cognitiva e rotinas (implementado)
└─ docs/SPRINT_ECOSSISTEMA.md  monitoramento de ecossistema (planejado)

▓▓▓ INTEGRATIONS
────────────────────────────────────────
└─ docs/SANITY_SCHEMA.md       schemas e integração Sanity.io
└─ docs/AUDITORIA_AGENTES.md   auditoria de código

▓▓▓ OPERATIONS
────────────────────────────────────────
└─ Makefile                    comandos locais
└─ railway.json                política de deploy
└─ Dockerfile                  build de produção
```

────────────────────────────────────────

## Deploy

O deploy de produção está preparado para Railway:

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ DEPLOY STACK                        ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Builder        Dockerfile           ┃
┃ Entrypoint      uvicorn web.app:app ┃
┃ Healthcheck     /health             ┃
┃ Persistence     Redis service       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

Fluxo mínimo:

1. configurar variáveis de ambiente
2. anexar serviço Redis ao app
3. garantir que `REDIS_URL` aponte para o Redis do projeto
4. fazer deploy do branch `main`

────────────────────────────────────────

## Tests

```bash
# suíte completa
make test

# modo silencioso
make test-q

# cobertura
make test-cov
```

────────────────────────────────────────

## Authorship

- **Architecture & Lead:** NEO MELLO
- **Project Type:** sistema pessoal multiagentes para operação, foco e agenda
- **Direction:** transformar tarefas em sistema observável, reagente e persistente

────────────────────────────────────────

```text
▓▓▓ MULTIAGENTES
────────────────────────────────────────
Orchestration, memory and execution
for a personal operating system.
────────────────────────────────────────
```
