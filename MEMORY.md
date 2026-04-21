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
como verdade estável sobre **interface**, **Notion**, **Railway** e
**rotinas**, sem depender só do chat.

────────────────────────────────────────

## ⧉ Superfícies: Notion vs web

- **Notion** (NEOBOT / workspace): fonte legítima de tarefas e agenda
  enquanto o `/sync` alimentar a memória local. Abrir Notion **não é
  falha de produto** — é uso esperado até o painel web fechar o circuito
  com o mesmo conforto.
- **Web (FastAPI + HTMX)** no Railway: **alvo de superfície principal**
  quando estiver “oficial” e sem ruído; o operador prefere **não** depender
  de planilha manual no dia a dia.
- **Regra prática para código:** ao propor fluxos, assume **sync
  Notion → `core/memory`** como caminho existente; melhorias devem
  **reduzir** trabalho duplicado, não exigir gravação espalhada.

────────────────────────────────────────

## ⨷ Agenda no dashboard (verdade técnica)

```text
Notion (DB Agenda / TO-DO)
        │  sync_agenda_range_to_local + sync_tasks_to_local
        ▼
  core/memory (local + Redis onde aplicável)
        │  get_today_agenda()
        ▼
  Card "Agenda hoje" na home
```

- **“Sem blocos hoje”** indica falta de dados na pipeline **após** o
  último sync ou datas fora da janela — não necessariamente “operador
  ignorou o Notion”.
- Evolução desejável: agentes e captura gerarem blocos sem exigir
  edição estilo planilha.

────────────────────────────────────────

## ◭ Life Guard · notificações (macOS)

- Recurso **valioso** (água, refeições, rotinas vitais).
- **Refinamento em curso:** volume, repetição (ex.: vários “Beber água”
  seguidos), horários — tratar como **melhoria contínua**, não como bug
  de conceito.

────────────────────────────────────────

## ⧇ GitHub Projects → Notion (âncora de escopo)

- Direção acordada: **ler roadmap/Gantt no GitHub Projects** e
  **materializar em tasks** no Notion; conclusão forte no **eixo
  GitHub/commits**; agenda fina no ritmo humano.
- Espelho bidirecional completo **não** é pré-requisito para v1.
- CLI: `python main.py github discover [--root PATH]` compara manifests
  em `NEOMELLO_WORKSPACES_ROOT` com `GITHUB_PROJECTS` em `config`;
  `python main.py github sync [--org SLUG] [--dry-run]` importa boards
  para `NOTION_DB_TAREFAS`. Mapa issue→página: Redis
  `state:github_projects:issue_notion_map`.
- **Onde ver no Notion:** o database configurado em `NOTION_DB_TAREFAS`
  (ex.: **Tarefas & Ações** no Command Center), **não** a página “Gestão
  de tempo” nem blocos TO-DO antigos — são superfícies diferentes.
- Diagnóstico: `python main.py github notion-check` (schema do DB,
  amostra de linhas, tamanho do mapa Redis).
- Reimportar do zero (novos POST): `python main.py github reset-map`
  (limpa Redis; páginas antigas no Notion não são apagadas).

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
Kernel memory · interface truth
────────────────────────────────────────
```
