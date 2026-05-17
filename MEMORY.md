<!-- markdownlint-disable MD003 MD007 MD013 MD022 MD023 MD025 MD029 MD032 MD033 MD034 -->
# MEMORY

```text
========================================
     MEMORY · BLUEPRINTS PARA AGENTES
========================================
```

> **Função:** memória latente + contratos operacionais curtos  
> **Par:** [AGENTS.md](./AGENTS.md) (contexto de workspace)  
> **Atualizar:** quando decisão de produto ou pipeline mudar

────────────────────────────────────────

## ⟠ Objetivo

Este arquivo guarda **blueprints diretos**: o que agentes e humanos tratam
como verdade estável sobre **LLM**, **interface**, **Railway** e
**pipelines de dados**, sem depender só do chat.

────────────────────────────────────────

## ⧉ Superfícies: CLI, Telegram e integrações

- **CLI** (`main.py`): superfície primária de operação — REPL, agenda,
  tarefas, focus, sync, capture e diagnóstico.
- **Telegram Bot**: inbound do segundo cérebro via long-poll HTTP.
  Captura texto livre → Capture Agent classifica → Linear issue.
- **Linear**: task store canônico de engenharia e captura.
  `python main.py sync` importa issues do Linear para Redis.
  Agente: `linear_sync.py`. `capture_agent.py` cria issues no Linear.
- **Notion**: destino **apenas** do `github_projects.py`
  (GitHub Projects v2 → `NOTION_DB_TAREFAS`). Não é fonte de captura.
- **Regra prática:** ao propor fluxos de tarefa, assuma
  **Linear → `core/memory`** como caminho canônico;
  Notion é exclusivo do espelho GitHub → Notion, não de captura humana.

────────────────────────────────────────

## ⨷ Pipeline de agenda (verdade técnica)

```text
Linear (issues) ──── linear_sync.py ──── core/memory (Redis)
                                                │  get_today_agenda()
                                                ▼
                                          CLI / Focus Guard

Telegram (captura) ── capture_agent.py ── Linear (issue)
                            │
                            └── classify() → categoria LOG/TASK/DECISION/PROJECT/INTEGRATION

GitHub (projects) ── github_projects.py ── Notion (NOTION_DB_TAREFAS)
                          │                     └── mapa issue↔page em Redis
                          └── GraphQL → sync_all_orgs()
```

- **"Sem blocos hoje"** indica falta de dados em Redis — rode
  `python main.py sync` para importar do Linear.
- Blocos são gerados pelos agentes; edição manual não é necessária.

────────────────────────────────────────

## ⟁ LLM — NEOone (Azure OpenAI)

- **Provider primário:** Azure OpenAI, deployment `gpt-oss-120b`,
  endpoint `https://neo-one.openai.azure.com/`.
- **Cadeia de fallback:** Azure → `gpt-4o-mini` (OpenAI público) →
  `gpt-3.5-turbo` → Gemma3 local (se `LOCAL_MODEL_ENABLED=true`).
- **Configurado via:** `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`
  no `.env`. Railway: Dashboard → Variables.
- **Regra prática:** nunca passe `model=` direto — use sempre
  `core.openai_utils.chat_completions(**kwargs)`. A chain gerencia
  provider, fallback e logging automaticamente.
- **max_tokens mínimo:** gpt-oss-120b requer `≥200` — com menos o modelo
  retorna string vazia (`finish_reason: length`).

────────────────────────────────────────

## ⧇ GitHub Projects → Notion (âncora de escopo)

- Direção única: **GitHub Projects v2 → Notion** (`NOTION_DB_TAREFAS`).
- CLI: `python main.py github sync [--org SLUG] [--dry-run]`
- Diagnóstico: `python main.py github notion-check`
- Reimportar do zero: `python main.py github reset-map`
  (limpa Redis; páginas antigas no Notion não são apagadas).
- Mapa issue→página: Redis `state:github_projects:issue_notion_map`.
- **Nota:** `ecosystem_monitor` e `github_projects` ainda não têm
  `handle_handoff` — não são roteáveis pelo Orchestrator.
  Expostos apenas via CLI e daemon.

────────────────────────────────────────

## ◬ Como manter este arquivo

- Uma entrada nova por **decisão** ou **pipeline** que deva sobreviver
  a sprints.
- Curto, **hard wrap** ~80 colunas, sem texto institucional vazio.
- Quem alterar o comportamento no código **atualiza** o trecho
  correspondente aqui.

```text
▓▓▓ NΞØ MELLØ
────────────────────────────────────────
The Archtect · NEØ PROTOCOL
────────────────────────────────────────
```
