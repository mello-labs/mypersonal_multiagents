# =============================================================================
# Makefile — Multiagentes Personal System
# =============================================================================
# Uso: make <comando>
# Dica: make help  →  lista todos os comandos disponíveis

SHELL  := /bin/bash
PYTHON := python3
VENV   := .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

# Cores ANSI (via printf para compatibilidade)
BOLD   := $(shell printf '\033[1m')
CYAN   := $(shell printf '\033[36m')
GREEN  := $(shell printf '\033[32m')
YELLOW := $(shell printf '\033[33m')
RED    := $(shell printf '\033[31m')
RESET  := $(shell printf '\033[0m')

.DEFAULT_GOAL := help

# =============================================================================
# AJUDA
# =============================================================================

.PHONY: help
help: ## Exibe esta ajuda
	@echo ""
	@echo "  $(BOLD)$(CYAN)Multiagentes — Comandos disponíveis$(RESET)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { \
		printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

# =============================================================================
# SETUP
# =============================================================================

.PHONY: build
build: install ## Alias Railway-friendly: instala dependências (projeto Python, sem transpile)
	@echo "$(GREEN)✓ Build concluído — use 'make dev' para iniciar$(RESET)"

.PHONY: setup
setup: venv install env-copy redis-pull ## Configura tudo do zero (venv + deps + .env)
	@echo "$(GREEN)✓ Setup completo! Edite o .env e rode: make dev$(RESET)"

.PHONY: venv
venv: ## Cria o virtualenv
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@echo "$(GREEN)✓ Virtualenv em $(VENV)/$(RESET)"

.PHONY: install
install: venv ## Instala dependências Python
	@$(PIP) install --upgrade pip -q
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Dependências instaladas$(RESET)"

.PHONY: install-dev
install-dev: install ## Instala dependências + extras dev (ipython, ruff, etc.)
	@$(PIP) install ipython rich watchdog ruff pytest-cov pytest-watch -q
	@echo "$(GREEN)✓ Dev extras instalados$(RESET)"

.PHONY: redis-pull
redis-pull: ## Baixa imagem Redis Docker (uma vez só)
	@docker pull redis:7-alpine -q && echo "$(GREEN)✓ Redis image pronta$(RESET)"

# =============================================================================
# DESENVOLVIMENTO
# =============================================================================

.PHONY: dev
dev: ## Inicia servidor FastAPI com hot-reload (porta 8000)
	@echo "$(CYAN)→ http://localhost:8000$(RESET)"
	@REDIS_URL=$${REDIS_URL:-redis://localhost:6379/0} \
		$(VENV)/bin/uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload

.PHONY: dev-full
dev-full: redis-up ## Sobe Redis local + FastAPI com hot-reload
	@sleep 1
	@$(MAKE) dev

.PHONY: guard
guard: redis-ensure ## Inicia Focus Guard no terminal
	@$(PY) main.py

# =============================================================================
# REDIS LOCAL (Docker)
# =============================================================================

REDIS_CONTAINER := multiagentes-redis

.PHONY: brew-redis
brew-redis: ## Instala Redis via Homebrew e inicia como serviço
	@brew install redis
	@brew services start redis
	@echo "$(GREEN)✓ Redis instalado e rodando via brew$(RESET)"

.PHONY: redis-up
redis-up: ## Sobe Redis local via Docker (porta 6379)
	@docker run -d --rm \
		--name $(REDIS_CONTAINER) \
		-p 6379:6379 \
		redis:7-alpine \
		> /dev/null 2>&1 || true
	@sleep 0.5
	@echo "$(GREEN)✓ Redis rodando em localhost:6379$(RESET)"

.PHONY: redis-ensure
redis-ensure: ## Garante que Redis está rodando (brew → Docker → erro)
	@redis-cli ping > /dev/null 2>&1 && exit 0; \
	if command -v redis-server > /dev/null 2>&1; then \
		redis-server --daemonize yes --loglevel warning > /dev/null 2>&1; \
		sleep 0.6; \
		echo "$(GREEN)✓ Redis iniciado (redis-server)$(RESET)"; \
	elif command -v docker > /dev/null 2>&1; then \
		docker run -d --rm --name $(REDIS_CONTAINER) -p 6379:6379 redis:7-alpine > /dev/null 2>&1 || true; \
		sleep 0.8; \
		echo "$(GREEN)✓ Redis iniciado (Docker)$(RESET)"; \
	else \
		echo "$(RED)✗ Redis não encontrado. Instale com: brew install redis$(RESET)"; \
		exit 1; \
	fi

.PHONY: redis-down
redis-down: ## Para o Redis local Docker
	@docker stop $(REDIS_CONTAINER) 2>/dev/null || true
	@echo "$(YELLOW)✓ Redis parado$(RESET)"

.PHONY: redis-cli
redis-cli: ## Abre Redis CLI interativo
	@docker exec -it $(REDIS_CONTAINER) redis-cli

.PHONY: redis-keys
redis-keys: ## Lista todas as chaves no Redis (ordenadas)
	@docker exec $(REDIS_CONTAINER) redis-cli KEYS '*' | sort

.PHONY: redis-stats
redis-stats: ## Exibe estatísticas do Redis (memória, conexões, etc.)
	@docker exec $(REDIS_CONTAINER) redis-cli INFO stats | grep -E "connected|commands|memory|keys"

.PHONY: redis-flush
redis-flush: ## ⚠️  Apaga TODOS os dados do Redis local
	@echo "$(RED)⚠️  Isso apaga TODOS os dados locais!$(RESET)"
	@read -p "Confirma? [s/N] " c && [ "$$c" = "s" ] && \
		docker exec $(REDIS_CONTAINER) redis-cli FLUSHALL && \
		echo "$(YELLOW)✓ Redis limpo$(RESET)" || echo "Cancelado."

.PHONY: redis-ping
redis-ping: ## Testa conexão Redis
	@docker exec $(REDIS_CONTAINER) redis-cli PING

# =============================================================================
# AGENTES
# =============================================================================

.PHONY: sync
sync: redis-ensure ## Sincronização diferencial com Notion
	@$(PY) main.py sync

.PHONY: agenda
agenda: redis-ensure ## Exibe agenda de hoje
	@$(PY) main.py agenda

.PHONY: tasks
tasks: redis-ensure ## Lista todas as tarefas
	@$(PY) main.py tasks

.PHONY: retro
retro: redis-ensure ## Gera retrospectiva semanal (local, sem push)
	@$(PY) main.py retrospective

.PHONY: retro-push
retro-push: redis-ensure ## Gera retrospectiva e envia ao Notion
	@$(PY) main.py retrospective --push

.PHONY: calendar-auth
calendar-auth: ## Autentica Google Calendar (OAuth2)
	@$(PY) main.py calendar auth

.PHONY: calendar-import
calendar-import: redis-ensure ## Importa eventos de hoje do Google Calendar
	@$(PY) main.py calendar import

.PHONY: calendar-status
calendar-status: redis-ensure ## Status da integração Google Calendar
	@$(PY) main.py calendar status

.PHONY: chat
chat: redis-ensure ## Modo chat interativo com o Orchestrator
	@$(PY) main.py chat

.PHONY: status
status: redis-ensure ## Exibe status atual do sistema
	@$(PY) main.py status

# =============================================================================
# TESTES
# =============================================================================

.PHONY: test
test: ## Roda todos os testes
	@$(VENV)/bin/pytest tests/ -v --tb=short

.PHONY: test-q
test-q: ## Roda testes modo silencioso
	@$(VENV)/bin/pytest tests/ -q

.PHONY: test-cov
test-cov: ## Testes com relatório de cobertura (abre htmlcov/)
	@$(VENV)/bin/pytest tests/ --cov=. --cov-report=term-missing --cov-report=html
	@echo "$(CYAN)→ Relatório em htmlcov/index.html$(RESET)"

.PHONY: test-watch
test-watch: ## Roda testes automaticamente ao salvar (watch mode)
	@$(VENV)/bin/ptw tests/ -- -v

# =============================================================================
# QUALIDADE DE CÓDIGO
# =============================================================================

.PHONY: lint
lint: ## Verifica estilo com ruff
	@$(VENV)/bin/ruff check . || true

.PHONY: fmt
fmt: ## Formata código com ruff
	@$(VENV)/bin/ruff format .
	@echo "$(GREEN)✓ Código formatado$(RESET)"

.PHONY: check
check: lint test ## lint + testes (CI local completo)

# =============================================================================
# GIT & DEPLOY
# =============================================================================

.PHONY: push
push: ## add + commit interativo + push
	@read -p "$(CYAN)Mensagem do commit: $(RESET)" msg && \
		git add -A && \
		git commit -m "$$msg" && \
		git push origin main && \
		echo "$(GREEN)✓ Push feito$(RESET)"

.PHONY: push-fix
push-fix: ## Commit rápido de fix + push
	@read -p "$(YELLOW)Fix: $(RESET)" msg && \
		git add -A && \
		git commit -m "fix: $$msg" && \
		git push origin main

.PHONY: push-feat
push-feat: ## Commit rápido de feat + push
	@read -p "$(CYAN)Feature: $(RESET)" msg && \
		git add -A && \
		git commit -m "feat: $$msg" && \
		git push origin main

.PHONY: log
log: ## Git log compacto (últimos 10 commits)
	@git log --oneline --graph --decorate -10

.PHONY: diff
diff: ## Git diff staged
	@git diff --staged

# =============================================================================
# DIAGNÓSTICO & AMBIENTE
# =============================================================================

.PHONY: env-check
env-check: ## Verifica variáveis de ambiente obrigatórias
	@$(PY) -c "from config import validate_config; w = validate_config(); \
		[print('⚠ ', x) for x in w] or print('✓ Config OK')"

.PHONY: env-copy
env-copy: ## Copia .env.example → .env (se não existir)
	@test -f .env && echo ".env já existe" || \
		(cp .env.example .env && echo "$(YELLOW)✓ .env criado — preencha as chaves!$(RESET)")

.PHONY: health
health: ## Checa o endpoint /health (app local)
	@curl -s http://localhost:8000/health | $(PYTHON) -m json.tool

.PHONY: logs
logs: ## Exibe últimas linhas dos logs
	@ls logs/*.log 2>/dev/null | xargs tail -n 50 || echo "Sem logs em logs/."

.PHONY: info
info: ## Exibe info do ambiente
	@echo ""
	@echo "  $(BOLD)Python:$(RESET)      $$($(PY) --version)"
	@echo "  $(BOLD)Pip:$(RESET)         $$($(PIP) --version | cut -d' ' -f1-2)"
	@echo "  $(BOLD)Uvicorn:$(RESET)     $$($(VENV)/bin/uvicorn --version 2>/dev/null || echo 'não instalado')"
	@echo "  $(BOLD)Redis:$(RESET)       $$(docker exec $(REDIS_CONTAINER) redis-cli PING 2>/dev/null || echo 'container parado')"
	@echo "  $(BOLD)Branch:$(RESET)      $$(git branch --show-current)"
	@echo "  $(BOLD)Último commit:$(RESET) $$(git log --oneline -1)"
	@echo ""

.PHONY: clean
clean: ## Remove cache Python e arquivos temporários
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true
	@rm -rf .ruff_cache htmlcov .coverage 2>/dev/null || true
	@echo "$(GREEN)✓ Cache limpo$(RESET)"

.PHONY: clean-all
clean-all: clean redis-down ## Remove cache + venv + para Redis (reset total)
	@rm -rf $(VENV)
	@echo "$(YELLOW)✓ Reset completo — rode: make setup$(RESET)"
