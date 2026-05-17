<!-- markdownlint-disable MD003 MD007 MD013 MD022 MD023 MD025 MD029 MD032 MD033 MD034 -->

# NEO PROTOCOL — ORGANIZATIONAL DESIGN
## File: AGENTS.md (Stateful Agent Roles)
## Version: v0.7.0
## Role: Chief Agent Architect (CAA)

```text
========================================
     MYPERSONAL MULTIAGENTS · AGENTS
========================================
Status: ACTIVE
Version: v0.7.0
Role: Personal OS Kernel
========================================
```

## ⟠ Objetivo

Este documento define a governança,
arquitetura e regras operacionais dos agentes
no sistema MyPersonal Multiagents.

────────────────────────────────────────

## ⨷ Vínculo do Workspace (NEO-PROTOCOL)

Este projeto é um **Repositório Filho Soberano**
vinculado ao hub de coordenação em:
`/Users/nettomello/neomello/NEO-PROTOCOL`.

**Diretrizes Globais:**
- Segue as políticas de segurança e topologia
  definidas no [neo-protocol-workspace](https://github.com/NEO-PROTOCOL/neo-protocol-workspace).
- A topologia canônica reside no Orchestrator global.
- Respeita os manifests de coordenação do root
  (`manifests/repos.json`).

────────────────────────────────────────

## ⧉ Arquitetura Core

O sistema opera em uma estrutura de fluxo:
**Intention -> Agenda -> Execution -> Audit.**

**LLM — cadeia de fallback (`core/openai_utils.py`):**
- **Azure OpenAI (NEOone)**: Provider primário — `gpt-oss-120b`
  via `https://neo-one.openai.azure.com/`.
- **OpenAI público**: Fallback cloud (`gpt-4o-mini` → `gpt-3.5-turbo`).
- **Local (Gemma3)**: Fallback dev opcional (`LOCAL_MODEL_ENABLED=true`).

**Persistência:**
- **Redis**: Fonte absoluta de verdade para estado operacional.

**Fontes de Dados:**
- **Linear**: Task store canônico — issues, sync e captura.
- **Redis**: Estado operacional em tempo real (fonte de verdade).
- **Notion**: Destino do espelho GitHub → Notion (`github_projects`).
  Não é fonte de captura humana.

**Removidos (não reintroduzir sem decisão explícita):**
- Sanity.io: Legado/Removido.
- Google Calendar: Removido.
- notion_sync bidirecional: Removido.
- Life Guard: Removido (candidato a reintrodução mínima via Telegram).
- Persona Manager: Removido (personas eram JSON locais + Sanity).
- Retrospective: Removido (candidato a reescrita para Linear).

────────────────────────────────────────

## ⍟ Matriz de Agentes (9 ativos)

| Agente | Arquivo | Roteável? | Destino |
|--------|---------|-----------|---------|
| Orchestrator | `orchestrator.py` | — | Redis |
| Focus Guard | `focus_guard.py` | ✓ | Redis |
| Scheduler | `scheduler.py` | ✓ | Redis |
| Validator | `validator.py` | ✓ | Redis |
| Capture Agent | `capture_agent.py` | ✓ | Linear |
| Linear Sync | `linear_sync.py` | ✓ | Redis ← Linear |
| Telegram Bot | `telegram_bot.py` | — | long-poll inbound |
| Ecosystem Monitor | `ecosystem_monitor.py` | ✗ | Redis (CLI/daemon) |
| GitHub Projects | `github_projects.py` | ✗ | Notion DB |

**Roteável:** exposto em `_AGENT_HANDLERS` do Orchestrator.
**✗:** acessível apenas via CLI ou daemon.

**Responsabilidades:**
- **Orchestrator**: Roteia intenções e sintetiza respostas via LLM.
- **Focus Guard**: Monitora sessões de foco, escalada e reagendamento.
- **Scheduler**: Cria, ordena e move blocos de agenda.
- **Validator**: Valida conclusão de tarefas com evidências cruzadas.
- **Capture Agent**: Classifica texto e cria issues no Linear.
- **Linear Sync**: Importa issues do Linear para Redis (agenda/tarefas).
- **Telegram Bot**: Inbound do segundo cérebro via long-poll HTTP.
- **Ecosystem Monitor**: Monitora GitHub, Railway e on-chain em múltiplas orgs.
- **GitHub Projects**: Espelha GitHub Projects v2 → Notion DB.

────────────────────────────────────────

## ◬ Regras Operacionais

1. **Ambiente**: Use sempre `.venv` (Python 3.12+)
   e comandos via `Makefile` (`make setup`, `make check`).
2. **Git Protocol (NΞØ)**: Todo commit deve seguir:
   `make check` -> **Conventional Commits** -> `git push`.
3. **Acesso à Memória**: Toda modificação de estado
   DEVE passar por `core/memory.py` usando schemas Redis.
4. **LLM**: Nunca passe `model=` direto — use sempre
   `core.openai_utils.chat_completions(**kwargs)`.

────────────────────────────────────────

## ⨀ Interfaces e Contratos

- **Linear**: Task store canônico — capture e sync.
- **Notion**: Destino do espelho GitHub → `NOTION_DB_TAREFAS`.
- **Telegram**: Superfície de entrada humana (inbound do segundo cérebro).
- **CLI**: Interface primária de operação (`main.py`).
- **Railway**: Deploy dos processos daemon e telegram.

────────────────────────────────────────

## ⚠️ Restrições Críticas

- NUNCA crie novos bancos SQLite.
- NUNCA crie notion_sync bidirecional — Notion é destino, não fonte.
- SEMPRE valide `config.py` antes de mudar lógica.
- Contexto: Prefira **[MEMORY.md](MEMORY.md)** para blueprints.

────────────────────────────────────────

```text
▓▓▓ NΞØ MELLØ
────────────────────────────────────────
Core Architect · NΞØ Protocol
neo@neoprotocol.space

"Code is law. Expand until
chaos becomes protocol."

Security by design.
Exploits find no refuge here.
────────────────────────────────────────
```
