# Manual do Desenvolvedor — Multiagentes PWA

## Stack

- **Backend**: Python 3.11+ / FastAPI / Uvicorn
- **Frontend**: Jinja2 templates + HTMX 1.9 (zero JS framework)
- **Persistencia**: Redis (Railway em produção, localhost em dev) — sem SQLite
- **Agentes**: OpenAI GPT via orchestrator, Focus Guard, Scheduler, Notion Sync, Calendar Sync, Validator, Retrospective, Life Guard, Persona Manager
- **Config externa**: Sanity.io (prompts, personas, agent config) via `core/sanity_client.py`
- **Notificações**: macOS push (osascript), Alexa (Voice Monkey)
- **Deploy**: Railway (Dockerfile) ou local

## Estrutura de arquivos relevantes

```
web/
  app.py                    # FastAPI app — todas as rotas
  templates/
    base.html               # Layout base: header, content, tab bar, PWA meta
    index.html              # Home/dashboard
    agenda.html             # Agenda com filtro de datas
    audit.html              # Audit trail completo
    tasks_page.html         # Pagina dedicada de tarefas
    chat_page.html          # Chat full-screen com orchestrator
    partials/
      agenda.html           # Lista de blocos (include)
      block_row.html        # Linha individual de bloco
      tasks.html            # Lista de tarefas (include)
      task_row.html         # Linha individual de tarefa
      chat_message.html     # Par user/bot de mensagem
      status.html           # Status partial (legacy, pode remover)
  static/
    manifest.json           # PWA manifest
    sw.js                   # Service worker (cache + push handler)
    icon-192.png            # Icone PWA 192x192
    icon-512.png            # Icone PWA 512x512
    favicon.ico             # Favicon
```

## Rotas

| Metodo | Path | Template | Descricao |
|--------|------|----------|-----------|
| GET | `/` | index.html | Dashboard principal |
| GET | `/agenda` | agenda.html | Agenda com filtro (tambem responde HTMX partial) |
| GET | `/tasks-page` | tasks_page.html | Pagina de tarefas |
| GET | `/chat-page` | chat_page.html | Chat full-screen |
| GET | `/audit` | audit.html | Audit trail |
| POST | `/chat` | partials/chat_message.html | HTMX — envia mensagem ao orchestrator |
| POST | `/sync` | HTMLResponse inline | HTMX — sync com Notion |
| POST | `/task` | partials/tasks.html | HTMX — cria tarefa |
| POST | `/task/{id}/complete` | partials/task_row.html | HTMX — completa tarefa |
| POST | `/block/{id}/complete` | partials/block_row.html | HTMX — completa bloco |
| POST | `/agenda/import` | agenda.html | Importa blocos de Notion/Calendar |
| GET | `/tasks` | partials/tasks.html | HTMX partial — lista de tarefas |
| GET | `/health` | JSON | Health check |

## Design system

Todas as variaveis CSS estao em `base.html` no `:root`. Principais:

```css
--bg: #000           /* fundo principal */
--s1: #0a0a0a        /* surface 1 (header/footer bg) */
--s2: #141414        /* surface 2 (cards) */
--s3: #1c1c1e        /* surface 3 (inputs, pills) */
--s4: #2c2c2e        /* surface 4 (avatars) */
--s5: #3a3a3c        /* surface 5 (borders fortes) */
--blue: #0a84ff      /* accent primario */
--green: #30d158     /* sucesso / ativo */
--red: #ff453a       /* erro / alerta */
--yell: #ffd60a      /* warning / prioridade media */
--cyan: #64d2ff      /* timestamps */
--font: SF Pro        /* texto */
--mono: SF Mono       /* numeros, timestamps, logs */
```

## Componentes CSS

| Classe | Uso |
|--------|-----|
| `.card` | Container com borda e border-radius |
| `.card-hd` | Header do card com label + action |
| `.metrics` | Grid 2x2 de metric cards |
| `.metric` | Card individual de metrica com barra colorida no topo |
| `.blk` | Linha de bloco de agenda |
| `.tsk` | Linha de tarefa |
| `.ls-item` | Item generico de lista (audit events, alertas, handoffs) |
| `.badge-ok/warn/err/def` | Badges semanticos |
| `.toast` | Toast de feedback |
| `.section-title` | Titulo de secao (22px bold) |
| `.form-row` | Linha de formulario com flex wrap |
| `.add-bar` | Barra de criacao de tarefa |

## Tab bar

A tab bar usa SVG icons inline (24x24, stroke-based). Cada tab e um `<a>` com classe `.tab`. A tab ativa recebe `.active` (cor azul).

O badge de notificacao (`.tab-badge`) e renderizado server-side com base em `summary.alerts.pending`.

## PWA

### manifest.json

- `display: standalone` — abre sem barra do browser
- `orientation: portrait`
- Icons 192 e 512

### Service worker (sw.js)

- **Cache**: precache de `/` e manifest. Static files = cache-first, HTML/API = network-first com fallback
- **Push**: handler pronto em `self.addEventListener('push', ...)` — aceita JSON com `{title, body, tag, url}`
- **Notification click**: abre/foca a URL do payload

### Para ativar push notifications no futuro:

1. Gerar par de chaves VAPID (`npx web-push generate-vapid-keys`)
2. Adicionar endpoint no backend para subscription (`POST /push/subscribe`)
3. No frontend, pedir permissao e enviar subscription ao backend
4. No scheduler/notifier, usar `pywebpush` para enviar

## HTMX

- Todas as interacoes usam HTMX (hx-post, hx-get, hx-target, hx-swap)
- Swap cirurgico: completar tarefa troca so a linha (`hx-swap="outerHTML"`)
- Indicadores de loading via `hx-indicator`
- Erros capturados globalmente via `htmx:responseError` e `htmx:sendError`

## Rodar local

```bash
# Ativar venv
source .venv/bin/activate

# Rodar servidor
python -m web.app
# ou
uvicorn web.app:app --reload --port 8000

# Acessar
open http://localhost:8000
```

## Variáveis de ambiente necessarias

Referência completa em `.env.example` na raiz do projeto. Resumo:

```
# Obrigatório
OPENAI_API_KEY=          # Para o orchestrator (chat)
NOTION_TOKEN=            # Para sync com Notion
NOTION_TASKS_DB_ID=      # Database de tarefas no Notion
NOTION_AGENDA_DB_ID=     # Database de agenda no Notion

# Infraestrutura
REDIS_URL=               # Redis (Railway ou local)
LOG_FILE=                # Arquivo de log
LOG_LEVEL=               # DEBUG/INFO/WARNING/ERROR
WEB_HOST=                # Host do FastAPI (default: 127.0.0.1)
WEB_PORT=                # Porta do FastAPI (default: 8000)

# Google Calendar opcional
GOOGLE_CREDENTIALS_FILE= # OAuth credentials para integração opcional
GOOGLE_TOKEN_FILE=       # Token OAuth para integração opcional

# Sanity.io
SANITY_PROJECT_ID=       # Project ID
SANITY_API_TOKEN=        # Token Viewer
SANITY_DATASET=          # Dataset (default: production)

# Notificações
VOICE_MONKEY_TOKEN=      # Alexa via Voice Monkey

# Life Guard
LIFE_GUARD_ACTIVE_HOUR_START=  # Hora início (default: 8)
LIFE_GUARD_ACTIVE_HOUR_END=    # Hora fim (default: 22)
LIFE_GUARD_WATER_INTERVAL=     # Minutos entre lembretes de água (default: 90)
```

## Deploy (Railway)

O projeto tem `Dockerfile`, `Procfile` e `railway.json` configurados. O deploy e automatico via push no branch main.

## Adicionar nova pagina/tab

1. Criar template em `web/templates/nova_page.html` extendendo `base.html`
2. Adicionar rota GET em `web/app.py` passando `page_name` e `summary` no contexto
3. Adicionar tab no `base.html` (dentro de `<nav class="tabs">`) com SVG icon
4. Adicionar condicional `{% if page_name == 'nova' %} active{% endif %}` na tab

## Adicionar novo metric card

No template desejado, dentro de `.metrics`:
```html
<div class="metric m-blue">
  <div class="metric-lbl">Label</div>
  <div class="metric-val v-blue">42</div>
  <div class="metric-sub">descricao</div>
</div>
```

Classes de cor: `m-blue`, `m-green`, `m-red`, `m-dim` (barra top) e `v-blue`, `v-green`, `v-red`, `v-dim` (valor).
