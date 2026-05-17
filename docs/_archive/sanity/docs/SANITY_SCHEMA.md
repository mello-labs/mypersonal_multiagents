# SANITY.IO — Schema e Integração

> **HISTÓRICO — documento desatualizado.**
> Este arquivo registra o planejamento inicial dos 4 schemas originais (2026-03-30).
> O projeto evoluiu: hoje há 13 schemas deployed em `n4dgl02q/production`.
>
> Documentos atuais:
>
> - Schemas locais: `sanity/schemaTypes/` (13 tipos)
> - Governança: `../governanca/PLANO_SOBERANIA_SANITY.md`
> - Cobertura por agente: `../governanca/MATRIZ_GOVERNANCA_AGENTES.md`
> - Contratos: `../governanca/CONTRATO_AGENTES.md`

**Status:** HISTÓRICO — superado pela Fase 2 do Sanity (concluída em 2026-04-03, commit `679f390`)
**Projeto Sanity:** `n4dgl02q` (criado em sanity.io/manage)
**Dataset:** `production`
**Propósito:** externalizar prompts, personas e configs — sem redeploy para ajustes

### O que já está feito

- [x] Projeto Sanity criado (`n4dgl02q`)
- [x] API token configurado no `.env` (SANITY_API_TOKEN, SANITY_PROJECT_ID)
- [x] `core/sanity_client.py` — GROQ queries, cache 5min, fallback para hardcoded
- [x] `focus_guard.py` já consome prompt via `sanity_client.get_prompt()`
- [x] Sanity Studio scaffolding em `sanity/` (package.json, deps instaladas)

### O que falta

- [ ] Deploy dos 4 schemas abaixo no Sanity Studio
- [ ] Migrar prompts hardcoded para documentos no Studio (tabela no final)
- [ ] Endpoint `/admin/reload-config` para `invalidate_cache()`

---

## Por que Sanity aqui

O sistema hoje tem prompts hardcoded em cada agente:

- `ROUTING_PROMPT` em `orchestrator.py:108`
- `DEVIATION_PROMPT` em `focus_guard.py:42`
- `VALIDATOR_PROMPT` em `validator.py:28`
- Personas em `/personas/*.json`

Mudar qualquer um deles exige redeploy. Com Sanity:

- Editar no Studio → agente usa na próxima execução
- Histórico de versões built-in
- Rollback em 1 clique se o prompt degradou

---

## Schema a criar no Sanity Studio

### Document Type: `llm_prompt`

```javascript
// sanity/schemas/llm_prompt.js
export default {
  name: "llm_prompt",
  title: "LLM Prompt",
  type: "document",
  fields: [
    {
      name: "id",
      title: "ID único",
      type: "slug",
      options: { source: "name" },
      validation: (Rule) => Rule.required(),
    },
    {
      name: "name",
      title: "Nome",
      type: "string",
      validation: (Rule) => Rule.required(),
    },
    {
      name: "agent",
      title: "Agente",
      type: "string",
      options: {
        list: [
          "orchestrator",
          "focus_guard",
          "scheduler",
          "validator",
          "retrospective",
          "life_guard",
          "ecosystem_monitor",
        ],
      },
      validation: (Rule) => Rule.required(),
    },
    {
      name: "prompt_type",
      title: "Tipo",
      type: "string",
      options: {
        list: [
          "routing",
          "synthesis",
          "direct",
          "deviation",
          "validation",
          "retrospective",
        ],
      },
    },
    {
      name: "system_prompt",
      title: "System Prompt",
      type: "text",
      rows: 20,
      validation: (Rule) => Rule.required(),
    },
    {
      name: "temperature",
      title: "Temperatura",
      type: "number",
      validation: (Rule) => Rule.min(0).max(2),
    },
    {
      name: "active",
      title: "Ativo",
      type: "boolean",
      initialValue: true,
    },
    {
      name: "notes",
      title: "Notas / Changelog",
      type: "text",
      rows: 4,
    },
  ],
  preview: {
    select: { title: "name", subtitle: "agent" },
  },
};
```

### Document Type: `persona`

```javascript
// sanity/schemas/persona.js
export default {
  name: "persona",
  title: "Persona",
  type: "document",
  fields: [
    {
      name: "persona_id",
      title: "ID",
      type: "slug",
      options: { source: "name" },
    },
    {
      name: "name",
      title: "Nome",
      type: "string",
    },
    {
      name: "short_name",
      title: "Nome curto",
      type: "string",
    },
    {
      name: "description",
      title: "Descrição",
      type: "text",
      rows: 3,
    },
    {
      name: "tone",
      title: "Tom",
      type: "string",
      options: {
        list: [
          "warm",
          "professional",
          "direct",
          "casual",
          "technical",
          "strategic",
        ],
      },
    },
    {
      name: "system_prompt",
      title: "System Prompt base",
      type: "text",
      rows: 15,
    },
    {
      name: "temperature_routing",
      title: "Temperatura (roteamento)",
      type: "number",
    },
    {
      name: "temperature_synthesis",
      title: "Temperatura (síntese)",
      type: "number",
    },
    {
      name: "active",
      title: "Ativa",
      type: "boolean",
      initialValue: true,
    },
  ],
};
```

### Document Type: `agent_config`

```javascript
// sanity/schemas/agent_config.js
export default {
  name: "agent_config",
  title: "Configuração de Agente",
  type: "document",
  fields: [
    {
      name: "agent_name",
      title: "Agente",
      type: "string",
      options: {
        list: [
          "focus_guard",
          "scheduler",
          "life_guard",
          "ecosystem_monitor",
          "notion_sync",
        ],
      },
    },
    {
      name: "enabled",
      title: "Habilitado",
      type: "boolean",
      initialValue: true,
    },
    {
      name: "check_interval_minutes",
      title: "Intervalo de check (minutos)",
      type: "number",
    },
    {
      name: "parameters",
      title: "Parâmetros adicionais (JSON)",
      type: "text",
      rows: 8,
      description: "JSON com parâmetros específicos do agente",
    },
  ],
};
```

### Document Type: `intervention_script`

```javascript
// sanity/schemas/intervention_script.js
export default {
  name: "intervention_script",
  title: "Script de Intervenção",
  type: "document",
  description:
    "Mensagens que o sistema envia quando detecta hiperfoco prolongado",
  fields: [
    {
      name: "trigger_minutes",
      title: "Disparar após (minutos)",
      type: "number",
      description: "Minutos de sessão ativa para disparar",
    },
    {
      name: "channel",
      title: "Canal",
      type: "string",
      options: { list: ["mac", "alexa", "mac+alexa"] },
    },
    {
      name: "urgency",
      title: "Urgência",
      type: "string",
      options: { list: ["gentle", "firm", "loud"] },
    },
    {
      name: "title",
      title: "Título (Mac push)",
      type: "string",
    },
    {
      name: "message",
      title: "Mensagem",
      type: "text",
      rows: 3,
      description:
        "Use {task} para nome da tarefa, {minutes} para tempo decorrido",
    },
    {
      name: "active",
      title: "Ativo",
      type: "boolean",
      initialValue: true,
    },
  ],
  orderings: [
    {
      title: "Por tempo (crescente)",
      name: "triggerAsc",
      by: [{ field: "trigger_minutes", direction: "asc" }],
    },
  ],
};
```

---

## Client Python: `core/sanity_client.py`

```python
"""
core/sanity_client.py — Cliente Sanity.io com cache em memória

Usa a Content API do Sanity para buscar prompts, personas e configs.
Cache de 5 minutos evita requests repetitivos.
Fallback para valores hardcoded se Sanity estiver indisponível.
"""

import os
import json
import time
import requests
from typing import Any, Optional

SANITY_PROJECT_ID = os.getenv("SANITY_PROJECT_ID", "")
SANITY_DATASET    = os.getenv("SANITY_DATASET", "production")
SANITY_API_TOKEN  = os.getenv("SANITY_API_TOKEN", "")  # token com permissão read
SANITY_CDN        = os.getenv("SANITY_USE_CDN", "false").lower() == "true"

_CACHE: dict[str, tuple[Any, float]] = {}
CACHE_TTL = 300  # 5 minutos


def _query(groq: str) -> Any:
    """Executa uma query GROQ na Content API do Sanity."""
    if not SANITY_PROJECT_ID:
        return None

    cache_key = groq
    if cache_key in _CACHE:
        value, ts = _CACHE[cache_key]
        if time.time() - ts < CACHE_TTL:
            return value

    host = "apicdn.sanity.io" if SANITY_CDN else "api.sanity.io"
    url = f"https://{host}/v2021-10-21/data/query/{SANITY_DATASET}"
    headers = {}
    if SANITY_API_TOKEN:
        headers["Authorization"] = f"Bearer {SANITY_API_TOKEN}"

    try:
        resp = requests.get(
            url,
            params={"query": groq},
            headers=headers,
            timeout=5
        )
        if resp.ok:
            result = resp.json().get("result")
            _CACHE[cache_key] = (result, time.time())
            return result
    except Exception:
        pass  # nunca quebra o sistema por Sanity indisponível

    return None


def get_prompt(agent: str, prompt_type: str, fallback: str = "") -> str:
    """
    Busca system prompt de um agente no Sanity.
    Retorna fallback se Sanity não estiver configurado ou indisponível.

    Uso:
        prompt = sanity_client.get_prompt("focus_guard", "deviation", DEVIATION_PROMPT)
    """
    result = _query(
        f'*[_type == "llm_prompt" && agent == "{agent}" && prompt_type == "{prompt_type}" && active == true][0].system_prompt'
    )
    return result if result else fallback


def get_persona(persona_id: str) -> Optional[dict]:
    """Busca uma persona completa pelo ID."""
    result = _query(
        f'*[_type == "persona" && persona_id.current == "{persona_id}" && active == true][0]'
    )
    return result


def get_all_personas() -> list[dict]:
    """Lista todas as personas ativas."""
    result = _query('*[_type == "persona" && active == true]')
    return result or []


def get_agent_config(agent_name: str) -> Optional[dict]:
    """Busca configuração de um agente."""
    result = _query(
        f'*[_type == "agent_config" && agent_name == "{agent_name}"][0]'
    )
    return result


def get_intervention_scripts() -> list[dict]:
    """Lista scripts de intervenção ordenados por trigger_minutes."""
    result = _query(
        '*[_type == "intervention_script" && active == true] | order(trigger_minutes asc)'
    )
    return result or []


def invalidate_cache() -> None:
    """Limpa o cache — usar após editar no Studio."""
    _CACHE.clear()
```

---

## Como usar nos agentes (exemplo focus_guard)

```python
# agents/focus_guard.py
from core import sanity_client

# Antes (hardcoded):
DEVIATION_PROMPT = """Você é o Focus Guard..."""

# Depois (com Sanity + fallback):
DEVIATION_PROMPT = """Você é o Focus Guard..."""  # mantém como fallback

def _get_deviation_prompt() -> str:
    return sanity_client.get_prompt("focus_guard", "deviation", DEVIATION_PROMPT)

# Na chamada LLM:
# prompt = _get_deviation_prompt()
# openai_utils.chat_completions(prompt, ...)
```

---

## Variáveis de ambiente

```bash
SANITY_PROJECT_ID=          # ex: abc123de (encontrado em sanity.io/manage)
SANITY_DATASET=production
SANITY_API_TOKEN=            # sanity.io/manage → API → Tokens → Add API token (Read)
SANITY_USE_CDN=false         # true em produção, false em dev (para dados frescos)
```

---

## Setup no Sanity (passo a passo)

```
1. sanity.io/manage → New Project → "Blank project"
2. Nome: "neomello-agents"
3. Dataset: production (default)
4. Copiar Project ID

5. Instalar CLI:
   npm install -g @sanity/cli

6. No terminal (qualquer pasta):
   sanity init --project <PROJECT_ID> --dataset production

7. Substituir schemas/ pelos 4 schemas acima

8. sanity deploy (sobe o Studio para sanity.io/manage/<PROJECT_ID>/studio)

9. sanity.io/manage → API → Tokens → Add API Token
   - Label: multiagentes-read
   - Permission: Viewer
   - Copiar token

10. Adicionar no .env:
    SANITY_PROJECT_ID=<PROJECT_ID>
    SANITY_API_TOKEN=<TOKEN>
```

---

## Migração dos prompts existentes

Após o Studio estar no ar, criar os seguintes documentos:

| Agente        | Tipo          | Arquivo fonte                                  |
| ------------- | ------------- | ---------------------------------------------- |
| orchestrator  | routing       | `orchestrator.py:108` → `ROUTING_PROMPT`       |
| orchestrator  | synthesis     | `orchestrator.py` → `_SYNTHESIS_BASE`          |
| orchestrator  | direct        | `orchestrator.py` → `_DIRECT_BASE`             |
| focus_guard   | deviation     | `focus_guard.py:42` → `DEVIATION_PROMPT`       |
| validator     | validation    | `validator.py:28` → `VALIDATOR_PROMPT`         |
| scheduler     | scheduling    | `scheduler.py:24` → `SYSTEM_PROMPT`            |
| retrospective | retrospective | `retrospective.py:22` → `RETROSPECTIVE_PROMPT` |

Migrar um por vez. Testar com Sanity. Só remover o hardcode quando validado.

---

## Critérios de aceite

- [ ] Studio acessível em sanity.io/manage
- [ ] `sanity_client.get_prompt("focus_guard", "deviation")` retorna string do Studio
- [ ] Cache funciona: segunda chamada em 1s não faz request HTTP
- [ ] Fallback funciona: com `SANITY_PROJECT_ID` vazio, retorna string hardcoded
- [ ] `invalidate_cache()` chamável via endpoint `/admin/reload-config`
- [ ] Pelo menos 1 prompt migrado e funcionando em produção
