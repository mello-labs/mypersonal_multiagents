<!-- markdownlint-disable MD003 MD007 MD013 MD022 MD023 MD025 MD029 MD032 MD033 MD034 -->
# NEØ HANDOFF

```text
========================================
      NEØ HANDOFF · SESSÃO 20/04/2026
========================================
```

> **Doc:** NEØ Handoff — 20/04/2026 (fim de sessão Opus)

────────────────────────────────────────

## ⟠ TL;DR

**Capture Agent end-to-end FUNCIONANDO.** Classify via OpenAI
(gpt-4o-mini) + gravação no Notion testada 3 vezes com sucesso.
Integração NEOBOT conectada à pasta pai
"NΞØ Protocol >_ main cave" está cascateando pras 5 DBs do Command
Center.

Links dos testes gravados no Notion (Work Log + Tarefas):

- https://www.notion.so/Teste-do-capture-agent-end-to-end-3488c6e83be08177bfdde2ce3eb6f065
- https://www.notion.so/Realizar-teste-final-ap-s-corre-o-de-audit-recursion-3488c6e83be081d1a90ddb690f68b355
- https://www.notion.so/Realizar-valida-o-final-do-audit-sem-recurs-o-3488c6e83be08163be35e4749b98a17b

────────────────────────────────────────

## ⧉ Estado do repo (não pushado)

### Commits já feitos nesta sessão

```text
9536d7d chore: archive sanity stack
0b00628 feat: enhance configuration and command handling for NEØ Command Center
```

### Pendente — 1 commit staged, aguardando você rodar

Os 4 arquivos do Azure-cleanup estão **staged** mas o
`.git/index.lock` travou meu sandbox. Pra fechar:

```bash
cd /Users/nettomello/CODIGOS/mypersonal_multiagents && \
rm -f .git/index.lock && \
git commit -m "refactor(llm): remove Azure OpenAI from chain, keep OpenAI + Local only

- Remove _AzureProvider class and all AZURE_OPENAI_* config vars
- Simplify LLMChain from 3-provider to 2-provider (Cloud -> Local)
- Clean Azure refs from .env.example and capture_agent comments
- Add _safe_audit helper in capture_agent: tolerates Redis unavailability
  in dev (ConnectionError is swallowed, print to stderr) so capture
  end-to-end works locally without Redis running

Smoke-tested end-to-end: classify + Notion write + NEOBOT integration
connected to all 5 Command Center DBs. Net -60 lines."
```

### Push (tua decisão)

Não pushei nada por regra. Quando quiser subir os 3 commits
(`9536d7d` + o novo + `0b00628`):

```bash
git push origin main
```

────────────────────────────────────────

## ⨷ O que mudou no código (changelog)

### Stack final: **OpenAI público → Gemma3 local**

Azure foi 100% removido. Três arquivos tocados:

1. **`config.py`** — removidas
   `AZURE_OPENAI_ENDPOINT/API_KEY/DEPLOYMENT/API_VERSION/FALLBACK_DEPLOYMENT`.
   `LLM_CONFIGURED` agora só checa
   `OPENAI_API_KEY or LOCAL_MODEL_ENABLED`.
2. **`core/openai_utils.py`** — classe `_AzureProvider` deletada (22
   linhas). `LLMChain` agora tem apenas 2 providers (cloud + local).
   `describe_chain()` simplificado. Import de `AzureOpenAI` removido.
3. **`agents/capture_agent.py`** — comentário atualizado. Novo helper
   `_safe_audit(**kwargs)` envolve `memory.create_audit_event` e engole
   `ConnectionError` do Redis (emite 1 linha stderr em vez de
   crashar). Crucial pra dev local sem Redis rodando.
4. **`.env.example`** — seção Azure removida.

### Task list final

- [x] #1 capture_agent.py (router 5 Notion DBs)
- [x] #2 Telegram bot worker
- [x] #3 Arquivar /sanity/
- [x] #5 Verificação sintática + smoke test classify
- [x] #6 Remover código Azure do codebase
- [x] #7 Conectar Notion Integration nas 5 DBs (via NEOBOT na pasta
      pai)
- [x] #8 Smoke test end-to-end capture
- [x] #4 `agents/github_projects.py` — entregue: GraphQL v2, CLI
      `github discover|sync`, destino `NOTION_DB_TAREFAS`, mapa Redis
      `github_projects:issue_notion_map`. Direção v1: GH → Notion.

────────────────────────────────────────

## ◭ Proxima pra retomar

### GitHub Projects (pós-v1 — opcional)

**#4** concluído no código; operar com:

```bash
python main.py github discover --root /Users/nettomello/neomello
python main.py github sync --dry-run
python main.py github sync
```

Vars no `config.py` / `.env`:

```python
GITHUB_TOKEN  # env: GITHUB_TOKEN
GITHUB_PROJECTS = {
    "flowpay-system":   GH_PROJECT_FLOWPAY,
    "NEO-FlowOFF":      GH_PROJECT_FLOWOFF,
    "NEO-PROTOCOL":     GH_PROJECT_NEO,
    "neo-smart-factory": GH_PROJECT_FACTORY,
}
```

Melhorias futuras (se quiseres): cron no Railway; webhook GitHub;
espelho Notion → GH (não é v1).

### Antes de deployar no Railway

1. **Atualizar `REDIS_URL`** no Railway Variables:
   - Local atual: `redis://localhost:6379/0`
   - Railway:
     `redis://default:<PASS>@redis.railway.internal:6379`

2. **Setar OPENAI_MODEL no Railway Variables** (atualmente só local,
   no `.env`):
   - `OPENAI_MODEL=gpt-4o-mini`
   - `OPENAI_API_KEY=<key do project FLOWOFF/multiagentes>`

3. **Telegram bot worker** (`Procfile.worker` + `railway.worker.json`
   prontos):
   - Criar segundo serviço no Railway, apontando pro mesmo repo
   - Start command: `python -m agents.telegram_bot` (já setado no
     railway.worker.json)
   - Compartilhar mesmas env vars + `TELEGRAM_BOT_TOKEN` e
     `TELEGRAM_ALLOWED_CHAT_IDS`

### Bug conhecido (não-crítico)

Quando Redis está indisponível, o capture ainda funciona mas exibe
**uma** linha stderr
`[capture_agent] audit event não persistido: ConnectionError`. Isso
desaparece sozinho quando o Redis do Railway estiver online. Em dev
local, pode subir Redis com:

```bash
brew services start redis
# ou
docker run -d --name redis-neo -p 6379:6379 redis:7-alpine
```

────────────────────────────────────────

## ⧇ Comandos úteis pra próxima sessão

```bash
# Classify rápido (sem gravar no Notion)
python main.py classify "texto de teste"

# Capture end-to-end (classifica + grava no Notion)
python main.py capture "texto para classificação e gravação"

# Ver cadeia LLM ativa
python -c "from core.openai_utils import describe_chain; print(describe_chain())"

# Subir bot Telegram local (long-poll)
python -m agents.telegram_bot
```

────────────────────────────────────────

## ◬ Contexto importante pra próxima sessão

- **OpenAI project ativo**: `proj_jfc8gj4XKYvjLHYHi3iQCaPt` (FLOWOFF /
  multiagentes)
- **OPENAI_MODEL**: `gpt-4o-mini` (gpt-5.4-mini não liberado neste
  project)
- **Notion Integration**: **NEOBOT**, conectada em
  "NΞØ Protocol >_ main cave" (pasta pai → cascateia)
- **Azure**: 100% removido do código, mas o recurso `neo-one` no
  Azure Foundry continua lá (usado pra outro projeto teu, R$1046 de
  crédito disponível)
- **Branch**: `main`, sincronizada com `origin/main` exceto pelos
  commits pendentes desta sessão

Boa sessão de domingo.

```text
▶ seguir em frente

────────────────────────────────────────
▓▓▓ FIM DO HANDOFF
────────────────────────────────────────
20/04/2026 · continuidade domingo
────────────────────────────────────────
```
