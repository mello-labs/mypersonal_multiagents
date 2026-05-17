# Audit Report — Sistema de Multiagentes

**Data:** 25/03/2026
**Escopo:** Análise completa do código entregue (v0.1 MVP)
**Método:** Code review estático + análise de arquitetura

---

## Sumário executivo

O sistema está funcional como MVP e a arquitetura central (SQLite compartilhado + handoffs via função + Focus Guard em thread) está correta. Há porém **11 bugs reais** (alguns silenciosos), **8 code smells** estruturais e **5 gaps de segurança/resiliência** que precisam ser resolvidos antes de qualquer uso em produção. Nenhum deles é crítico o suficiente para impedir testes, mas dois deles causam comportamento incorreto visível hoje.

---

## Bugs reais (ordenados por impacto)

### 🔴 BUG 1 — `notifier.py`: output duplicado no console

**Arquivo:** `core/notifier.py`
**Impacto:** Todo print aparece duas vezes no terminal.

`notify()` chama `print()` diretamente E depois chama `_logger.info/warning/error()`, que por sua vez dispara o `StreamHandler` do logger que também escreve no console. O comentário no código diz "sem o logging.StreamHandler duplicar", mas o handler ainda está registrado.

**Fix:**

```python
# Remover o console_handler do logger — o print() já cuida do terminal
logger.addHandler(file_handler)
# NÃO adicionar console_handler
```

---

### 🔴 BUG 2 — `focus_guard.py` e `validator.py`: violação da abstração de memória

**Arquivos:** `agents/focus_guard.py` (função `analyze_progress`), `agents/validator.py` (função `gather_evidence`)
**Impacto:** Ambos abrem conexões SQLite diretas, ignorando o lock de thread do `memory.py`. Se o Focus Guard e o Validator rodarem ao mesmo tempo, podem gerar corrupção de dados em escritas concorrentes.

```python
# Ambos fazem isso — ERRADO:
import sqlite3
conn = sqlite3.connect(MEMORY_DB_PATH, check_same_thread=False)
```

**Fix:** Expor as queries necessárias como funções públicas em `memory.py` e usar apenas elas.

---

### 🟠 BUG 3 — `notion_sync.py`: sem paginação

**Arquivo:** `agents/notion_sync.py`, função `fetch_notion_tasks()`
**Impacto:** Silencioso. A Notion API retorna no máximo 100 resultados por chamada. Com mais de 100 tarefas, as mais antigas nunca são sincronizadas — e o sistema não avisa.

```python
# O campo has_more e next_cursor nunca são verificados:
result = _request("POST", f"databases/{NOTION_TASKS_DB_ID}/query", payload)
# result["has_more"] pode ser True — ignorado
```

**Fix:** Adicionar loop de paginação usando `result["next_cursor"]` enquanto `result["has_more"] == True`.

---

### 🟠 BUG 4 — `scheduler.py`: detecção de conflitos não detecta sobreposição

**Arquivo:** `agents/scheduler.py`, função `detect_schedule_conflicts()`
**Impacto:** Blocos "09:00-10:00" e "09:30-10:30" passam sem conflito detectado. A função só verifica se dois blocos têm exatamente o mesmo horário de início.

**Fix:** Comparar intervalos: conflito existe quando `start_A < end_B AND start_B < end_A`.

---

### 🟠 BUG 5 — `main.py`: `Optional` importado no lugar errado

**Arquivo:** `main.py`
**Impacto:** `Optional` é usado nos tipos de `cmd_focus_start()` e `cmd_validate()` mas é importado dentro da função `main()` no final do arquivo. Qualquer chamada a essas funções antes de `main()` executar levanta `NameError`.

```python
# Hoje está assim (ERRADO — importado só quando main() roda):
if __name__ == "__main__":
    from typing import Optional
    main()

# Além disso, dentro de funções individuais:
def cmd_focus_start(task_id: Optional[int] = None):  # NameError se main() não rodou
    from typing import Optional as Opt  # importação duplicada e desnecessária
```

**Fix:** Mover `from typing import Optional` para o topo do arquivo.

---

### 🟠 BUG 6 — `focus_guard.py`: acúmulo de jobs no scheduler

**Arquivo:** `agents/focus_guard.py`, função `start_guard()`
**Impacto:** Se `start_guard()` for chamado mais de uma vez (ex: restart manual), o `schedule.every(X).minutes.do(...)` adiciona um novo job sem remover o anterior. O Focus Guard passa a disparar em dobro, triplo, etc.

```python
# Sem limpeza dos jobs anteriores antes de registrar novo:
schedule.every(FOCUS_CHECK_INTERVAL_MINUTES).minutes.do(_run_focus_check)
```

**Fix:** Chamar `schedule.clear()` antes de registrar o job em `start_guard()`.

---

### 🟡 BUG 7 — `memory.py`: `get_today_tasks()` com LIKE frágil

**Arquivo:** `core/memory.py`, função `get_today_tasks()`
**Impacto:** A query usa `scheduled_time LIKE "%:%"` como segundo filtro — isso retorna TODAS as tarefas que têm dois-pontos no campo, não só as de hoje. Tarefas de outros dias agendadas como "HH:MM" (sem data) aparecem sempre.

---

### 🟡 BUG 8 — `validator.py`: tarefa rejeitada vai para "Em progresso" sem perguntar

**Arquivo:** `agents/validator.py`, função `apply_verdict()`
**Impacto:** Se o Validator rejeita uma tarefa que estava "Concluído", ela volta automaticamente para "Em progresso" sem confirmação do usuário. Em um cenário de validação em lote (`validate_all`), isso pode reverter múltiplas tarefas silenciosamente.

---

### 🟡 BUG 9 — `orchestrator.py`: falha de LLM degrada para chatbot genérico sem aviso

**Arquivo:** `agents/orchestrator.py`, função `process()`
**Impacto:** Se o LLM retorna `handoffs: []` (não entendeu o comando ou falhou), o sistema chama `_direct_response()` e responde como chatbot genérico, sem avisar que nenhum agente foi acionado. O usuário não sabe que a ação não foi executada.

---

### 🟡 BUG 10 — `main.py`: `_shutdown()` chamado duas vezes

**Arquivo:** `main.py`
**Impacto:** `atexit.register(_shutdown)` e o handler `SIGINT` ambos chamam `_shutdown()`. Em saída normal (usuário digita `/quit`), `atexit` dispara e chama `focus_guard.stop_guard()`. Se o usuário der Ctrl+C, o handler chama `_shutdown()` E depois o `atexit` chama de novo. Duplo stop é inofensivo mas gera log duplicado.

---

### 🟡 BUG 11 — `notion_sync.py`: `HandoffPayload` é dead code

**Arquivo:** `agents/notion_sync.py`
**Impacto:** A classe `HandoffPayload` com seus métodos estáticos é definida mas nunca importada ou usada em nenhum outro arquivo. Código morto que confunde quem lê.

---

## Code smells estruturais

### SMELL 1 — `sys.path.insert(0, ...)` em todos os agentes

Cada arquivo de agente tem:

```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

Isso é um hack para compensar a falta de um `pyproject.toml` ou instalação como pacote. Funciona, mas é frágil (quebra se você rodar de um diretório diferente) e polui o `sys.path`.

**Solução correta:** adicionar um `pyproject.toml` mínimo com `pip install -e .` ou simplesmente sempre rodar `main.py` da raiz.

---

### SMELL 2 — Circular import disfarçado

`validator.py` importa `notion_sync` **dentro de uma função** para evitar circular import:

```python
def apply_verdict(...):
    from agents import notion_sync  # gambiarra
```

Isso indica que a dependência entre agentes não foi bem separada. O Validator não deveria chamar diretamente o NotionSync — deveria retornar o veredicto e deixar o Orchestrator fazer a atualização.

---

### SMELL 3 — Nova conexão SQLite por operação

`memory.py` chama `_get_connection()` em cada função, criando e destruindo uma conexão a cada operação. Para SQLite local isso é aceitável em performance, mas desperdiça o benefício do WAL mode que é mais eficiente com conexões de longa duração.

---

### SMELL 4 — LLM routing com ~800 tokens fixos por mensagem

O `ROUTING_PROMPT` do Orchestrator inclui o JSON completo do `AGENTS_REGISTRY` em cada chamada. São ~800 tokens de overhead constante. Para uso pessoal (baixo volume) não dói financeiramente, mas é possível mover para `system` message com cache ou comprimir a representação.

---

### SMELL 5 — Sem retry em nenhuma chamada LLM ou HTTP

Nenhuma das chamadas `_client.chat.completions.create()` ou `_request()` tem retry. Um erro 429 (rate limit) ou 503 transitório mata a operação sem tentativa de recuperação.

---

### SMELL 6 — `execute_handoffs()` é puramente síncrono

O Orchestrator executa agentes em série mesmo quando são independentes (ex: `scheduler` + `notion_sync` para criar uma tarefa). Não há paralelismo — cada agente espera o anterior terminar.

---

### SMELL 7 — Sem validação do schema JSON retornado pelo LLM

`scheduler.py`, `focus_guard.py` e `validator.py` fazem `json.loads()` no output do LLM e acessam campos diretamente. Se o modelo "alucinar" um campo com nome diferente, o código levanta `KeyError` ou retorna `None` silenciosamente.

---

### SMELL 8 — `sync_tasks_to_local()` é O(n²)

```python
for nt in notion_tasks:              # n tarefas do Notion
    all_local = memory.list_all_tasks()  # query completa a cada iteração!
    for lt in all_local:             # n tarefas locais
```

A query ao banco é feita dentro do loop externo. Com 100 tarefas: 100 queries desnecessárias.

**Fix:** Mover `memory.list_all_tasks()` para fora do loop e construir um dict de lookup por `notion_page_id`.

---

## Gaps de segurança / resiliência

| # | Gap | Onde | Risco |
|---|---|---|---|
| S1 | `NOTION_TOKEN` e `OPENAI_API_KEY` aparecem em traceback se a request falhar (incluídos no header) | `notion_sync._request()` | Vazamento em logs |
| S2 | `memory.db` sem criptografia | `core/memory.py` | Dados pessoais em plaintext no disco |
| S3 | Sem timeout nas chamadas LLM | todos os agentes | Processo trava indefinidamente se a API não responder |
| S4 | Sem sanitização do input do usuário antes de passar ao LLM | `orchestrator.process()` | Prompt injection via input CLI |
| S5 | `validate_config()` é chamada mas os warnings são apenas `print` — o sistema roda mesmo sem chaves configuradas, falhando silenciosamente mais tarde | `main._startup()` | UX ruim; erros difíceis de rastrear |

---

## O que está bem (pontos positivos)

- **Arquitetura de memória compartilhada via SQLite** é a escolha certa para um sistema local single-user. Simples, sem dependências externas, e funciona offline.
- **Separação de responsabilidades** entre os agentes está clara — cada um tem um `handle_handoff()` bem definido como ponto de entrada.
- **Auditoria de handoffs** na tabela `agent_handoffs` é excelente — permite reconstruir qualquer sequência de execução depois do fato.
- **Fallback sem LLM** em `focus_guard.analyze_with_llm()` e `validator.validate_with_llm()` — o sistema degrada graciosamente se a API OpenAI estiver fora.
- **Focus Guard com thread daemon** é a abordagem correta para não bloquear o CLI.
- **`response_format: json_object`** em todas as chamadas LLM que esperam JSON — elimina boa parte dos erros de parsing.
- **Configuração centralizada** em `config.py` com `validate_config()` é uma boa prática.

---

## Prioridade de correção

| Prioridade | Item | Esforço |
|---|---|---|
| 🔴 Agora | BUG 1: output duplicado no terminal | 2 linhas |
| 🔴 Agora | BUG 2: conexões SQLite paralelas (race condition) | médio |
| 🟠 Esta semana | BUG 3: paginação Notion | pequeno |
| 🟠 Esta semana | BUG 4: detecção de sobreposição na agenda | pequeno |
| 🟠 Esta semana | BUG 5: import Optional | 1 linha |
| 🟠 Esta semana | BUG 6: acúmulo de jobs no scheduler | 1 linha |
| 🟠 Esta semana | SMELL 8: O(n²) no sync | pequeno |
| 🟡 Próxima fase | SMELL 2: circular import / Validator → NotionSync | refactor médio |
| 🟡 Próxima fase | SMELL 5: retry em LLM e HTTP | médio |
| 🟡 Próxima fase | S3: timeout nas chamadas LLM | pequeno |
| 🟢 Futuro | S2: criptografia do memory.db | grande |
| 🟢 Futuro | SMELL 6: paralelismo nos handoffs | grande |
