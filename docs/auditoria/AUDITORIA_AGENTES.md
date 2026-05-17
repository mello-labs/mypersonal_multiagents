# Auditoria de Código — Sistema Multiagentes

> **HISTÓRICO — Todas as issues foram corrigidas em 2026-03-28.**
> Este documento é registro de auditoria passada, não estado atual do código.
> Para governança atual dos agentes, consulte `../governanca/CONTRATO_AGENTES.md` e `../governanca/MATRIZ_GOVERNANCA_AGENTES.md`.

**Data:** 2026-03-28
**Status:** RESOLVIDO — ver seção "Registro de Correções" ao final
**Escopo:** `agents/` + `core/openai_utils.py` + `config.py`
**Metodologia:** Revisão estática cruzada — padrões, fluxo de dados, segurança

---

## Sumário Executivo

| Severidade   | Quantidade |
| ------------ | ---------- |
| CRÍTICO      | 0          |
| ALTO         | 6          |
| MÉDIO        | 7          |
| Arquitetural | 1          |

Nenhuma chamada direta à API OpenAI encontrada fora de `core/openai_utils.py` — padrão central respeitado em todos os agentes.

---

## Issues ALTO — Ação Imediata

### A1 · `focus_guard.py` ~383 — Triple LLM call em `force_check()`

`force_check()` chama `analyze_with_llm(progress)` diretamente (chamada 1), e em seguida chama `_run_focus_check()` que internamente executa `analyze_progress()` + `analyze_with_llm()` novamente (chamadas 2 e 3). Cada invocação via Orchestrator gera 3 chamadas à OpenAI — 2 delas desperdiçadas.

**Correção:** `_run_focus_check()` deve aceitar `progress` e `analysis` como parâmetros opcionais, ou `force_check()` deve delegar integralmente para `_run_focus_check()` e retornar seus resultados.

---

### A2 · `focus_guard.py` ~89 — Lógica de overdue incorreta

```python
# ERRADO — marca blocos em andamento como atrasados
if (end_t < now or start_t < now) and not block.get("completed"):
    overdue_blocks.append(block)
```

A condição `start_t < now` é verdadeira para qualquer bloco cujo início já passou, inclusive o bloco atual em execução. O `elif` de `current_block` (testado depois) nunca é alcançado para esse caso — o bloco em andamento entra em `overdue_blocks` antes. Resultado: Focus Guard emite falsos alertas de atraso para tarefas ativas.

**Correção:**

```python
# CORRETO — apenas blocos cujo FIM já passou
if end_t < now and not block.get("completed"):
    overdue_blocks.append(block)
```

---

### A3 · `scheduler.py` ~174 — `return` dentro do `for` torna busca multi-day inoperante

```python
for offset in range(max_days_ahead + 1):
    # ...
    return target_date, _format_slot(start_dt, duration_minutes)  # sempre retorna aqui

# Código abaixo nunca é alcançado:
fallback_date = ...
return fallback_date, ...
```

O `return` dentro do loop faz a função sempre retornar no `offset=0` (hoje), sem jamais verificar dias futuros. O parâmetro `max_days_ahead` é ignorado na prática.

**Correção:** mover o `return` para fora do `for`, retornando apenas após esgotar todos os offsets sem encontrar slot disponível.

---

### A4 · `validator.py` ~71 — Conexão SQLite direta bypassa `core.memory`

```python
import sqlite3
from config import MEMORY_DB_PATH
conn = sqlite3.connect(MEMORY_DB_PATH, check_same_thread=False)
```

`validator.py` abre conexão SQLite diretamente em `gather_evidence()` para consultar `focus_sessions` e `agenda_blocks`. Todos os outros agentes usam exclusivamente `core.memory` como camada de abstração. Se `core.memory` mudar de backend (pool de conexões, Redis, migração de schema), o `validator` quebra silenciosamente.

**Correção:** adicionar `get_focus_sessions_for_task(task_id)` e `get_agenda_blocks_for_task(task_id)` em `core/memory.py` e substituir o acesso direto.

---

### A5 · `retrospective.py` ~230 — HTTP ao Notion sem retry

`retrospective.py` reimplementa sua própria pilha HTTP para o Notion (`_notion_headers()` + `requests.post` direto), sem qualquer lógica de retry. `notion_sync.py` possui `_request()` com retry automático via `tenacity` para erros 429 (rate-limit) e 5xx. Em caso de rate-limit da Notion API, a criação da página de retrospectiva falha silenciosamente (retorna `None`).

**Correção:** extrair `_request` e `_notion_headers` de `notion_sync.py` para `core/notion_client.py` e importar de lá em ambos os agentes. Ou fazer `retrospective.py` importar diretamente de `notion_sync`.

---

### A6 · `calendar_sync.py` ~81 — `token.json` gravado sem permissões restritas

```python
with open(GOOGLE_TOKEN_FILE, "w") as f:
    f.write(creds.to_json())
```

O OAuth refresh token do Google é gravado com as permissões padrão do sistema (tipicamente `0o644` — legível por todos os usuários). Em ambientes multiusuário, qualquer usuário local pode ler e reutilizar o token.

**Correção:**

```python
import stat
fd = os.open(GOOGLE_TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(creds.to_json())
```

---

## Issues MÉDIO

### M1 · `persona_manager.py` ~37 — `print()` em vez de `notifier`

Único agente que usa `print()` diretamente para reportar erros. Todos os demais usam `notifier.error()` / `notifier.warning()`. O erro não é registrado no `LOG_FILE` configurado.

**Correção:** `notifier.error(f"Erro ao carregar {filepath.name}: {e}", "persona_manager")`

---

### M2 · `agents/__init__.py` — `__all__` desatualizado

```python
__all__ = ["orchestrator", "scheduler", "focus_guard", "notion_sync", "validator"]
```

`calendar_sync`, `retrospective` e `persona_manager` estão ausentes, embora sejam importados e usados pelo Orchestrator. `__all__` fica enganoso para ferramentas de análise estática e IDEs.

**Correção:** incluir todos os agentes ativos ou remover a declaração.

---

### M3 · `scheduler.py` ~159 — Código morto no `find_next_available_slot`

Consequência direta do A3: o fallback de data e o código abaixo do `for` são código morto e nunca executados. Podem ser removidos após a correção do A3.

---

### M4 · `validator.py` — Import dinâmico de `notion_sync` dentro de função

```python
def gather_evidence(task_id):
    from agents import notion_sync   # import dentro da função
    notion_tasks = notion_sync.fetch_notion_tasks()
```

Padrão inconsistente com o restante do projeto. Mascara erros de importação até o momento da execução. O mesmo import se repete em `apply_verdict()`.

**Correção:** mover para o topo do arquivo junto com os demais imports.

---

### M5 · `calendar_sync.py` ~315 — Timezone hardcoded sem aviso

```python
except ImportError:
    tz_str = "America/Sao_Paulo"  # sem log, sem aviso
```

Fallback silencioso que causa comportamento errado para qualquer usuário fora do fuso `America/Sao_Paulo`.

**Correção:** `notifier.warning("tzlocal não disponível — usando America/Sao_Paulo como fallback de timezone.", AGENT_NAME)`

---

### M6 · `orchestrator.py` e `notion_sync.py` — Imports não utilizados

- `orchestrator.py:18` — `Any` importado de `typing`, nunca usado
- `notion_sync.py:24` — `List` importado de `typing`, nunca usado (o arquivo usa `list[...]` moderno do Python 3.10+)
- `orchestrator.py:543` — f-string sem interpolação: `f"Resultado das ações executadas:"` → remover o `f`

---

### M7 · `config.py` ~17 — `validate_config()` nunca é chamada

`OPENAI_API_KEY` é lida com fallback para string vazia. O client OpenAI é instanciado com essa string vazia no nível de módulo — o erro só aparece na primeira chamada à API, sem mensagem clara. A função `validate_config()` existe mas não é invocada em nenhum ponto do código.

**Correção:** chamar `validate_config()` na inicialização da aplicação (`main.py` ou equivalente).

---

## Issue Arquitetural — Boilerplate `handle_handoff` duplicado

O bloco de log/update/return do protocolo de handoff é copiado literalmente em **6 arquivos**:
`scheduler`, `focus_guard`, `validator`, `retrospective`, `notion_sync`, `calendar_sync`.

```python
handoff_id = memory.log_handoff("orchestrator", AGENT_NAME, action, payload)
# ...
memory.update_handoff_result(handoff_id, result, "success")
return {"status": "success", "result": result}
# ...
except Exception as exc:
    memory.update_handoff_result(handoff_id, {"error": str(exc)}, "error")
    return {"status": "error", "result": {"error": str(exc)}}
```

Qualquer mudança no protocolo (ex: adicionar campo `"agent"` na resposta, mudar o esquema de log) exige edição em 6 arquivos com risco de divergência.

**Proposta:** decorator `@handoff_handler` em `core/handoff_utils.py` que envolve a função do agente com o boilerplate de log/update/return.

---

## Status de Conformidade — Padrão Central OpenAI

| Agente             | Usa `chat_completions` | Chamada direta       |
| ------------------ | ---------------------- | -------------------- |
| orchestrator.py    | ✅                     | —                    |
| scheduler.py       | ✅                     | corrigido 2026-03-28 |
| focus_guard.py     | ✅                     | —                    |
| validator.py       | ✅                     | —                    |
| retrospective.py   | ✅                     | —                    |
| notion_sync.py     | não usa LLM            | —                    |
| calendar_sync.py   | não usa LLM            | —                    |
| persona_manager.py | não usa LLM            | —                    |

---

## Registro de Correções — 2026-03-28

| ID  | Arquivo              | O que foi feito                                                                                                                                                                             |
| --- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | `focus_guard.py`     | `_run_focus_check` aceita `progress`/`analysis` opcionais; `force_check` os computa uma vez e repassa — 3 LLM calls → 1                                                                     |
| A2  | `focus_guard.py`     | Condição overdue: `end_t < now or start_t < now` → `end_t < now`                                                                                                                            |
| A3  | `scheduler.py`       | `return` dentro do `for` condicionado a `start_dt.date().isoformat() == target_date` — multi-day search agora funciona                                                                      |
| A4  | `validator.py`       | `sqlite3.connect` direto removido; adicionados `get_focus_sessions_for_task` e `get_agenda_blocks_for_task` em `core/memory.py` com índices Redis `sessions:task:{id}` e `blocks:task:{id}` |
| A5  | `retrospective.py`   | HTTP direto para Notion substituído por `_notion_sync._request` (retry via tenacity); `_notion_headers()` local removida                                                                    |
| A6  | `calendar_sync.py`   | `open(token_file, "w")` → `os.open(..., 0o600)` + `os.fdopen`                                                                                                                               |
| M1  | `persona_manager.py` | `print()` → `notifier.error()`; adicionado import de `notifier`                                                                                                                             |
| M2  | `agents/__init__.py` | `__all__` atualizado com todos os 8 agentes                                                                                                                                                 |
| M3  | `scheduler.py`       | Código morto após o loop tornado acessível pela correção A3                                                                                                                                 |
| M4  | `validator.py`       | Imports dinâmicos de `notion_sync` movidos para o topo do arquivo                                                                                                                           |
| M5  | `calendar_sync.py`   | Fallback de timezone emite `notifier.warning`                                                                                                                                               |
| M6  | `orchestrator.py`    | `Any` removido do import `typing`; f-string sem interpolação corrigida                                                                                                                      |
| M6  | `notion_sync.py`     | `List` removido do import `typing`                                                                                                                                                          |
| M7  | `config.py`          | `validate_config()` já chamada em `main.py:45` — sem alteração necessária                                                                                                                   |
