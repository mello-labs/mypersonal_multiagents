# =============================================================================
# NΞØ PROTOCOL — MULTIAGENTS KERNEL OS
# =============================================================================
# File: Makefile
# Version: 1.1.0 (Advanced Edition)
# Role: System Orchestration & Secure Delivery
# =============================================================================

# -----------------------------------------------------------------------------
# CONFIGURATION & VARIABLES
# -----------------------------------------------------------------------------
SHELL       := /bin/bash
PYTHON      := python3
VENV        := .venv
BIN         := $(VENV)/bin
PIP         := $(BIN)/pip
PY          := $(BIN)/python
UVICORN     := $(BIN)/uvicorn
RUFF        := $(BIN)/ruff
PYTEST      := $(BIN)/pytest
PIP_AUDIT   := $(BIN)/pip-audit

# Project Identity
PROJECT_NAME := mypersonal_multiagents
VERSION      := $(shell git describe --tags --always 2>/dev/null || echo "v0.5.1")
BRANCH       := $(shell git branch --show-current)

# Aesthetics (ANSI Colors)
BOLD   := $(shell printf '\033[1m')
CYAN   := $(shell printf '\033[36m')
GREEN  := $(shell printf '\033[32m')
YELLOW := $(shell printf '\033[33m')
RED    := $(shell printf '\033[31m')
RESET  := $(shell printf '\033[0m')
MAGENTA:= $(shell printf '\033[35m')

# Redis Config
REDIS_CONTAINER := multiagentes-redis
REDIS_PORT      := 6379
REDIS_HOST      := 127.0.0.1
REDIS_URL       := redis://$(REDIS_HOST):$(REDIS_PORT)/0

# -----------------------------------------------------------------------------
# DEFAULT GOAL
# -----------------------------------------------------------------------------
.DEFAULT_GOAL := help

# -----------------------------------------------------------------------------
# ⟠ CORE PROTOCOL (NΞØ FLOW)
# -----------------------------------------------------------------------------

.PHONY: help
help: ## Display this advanced help menu
	@printf "\n$(BOLD)$(MAGENTA)========================================$(RESET)\n"
	@printf "  $(BOLD)$(CYAN)NΞØ MULTIAGENTS KERNEL OS$(RESET)\n"
	@printf "  $(BOLD)Version:$(RESET) %s | $(BOLD)Branch:$(RESET) %s\n" "$(VERSION)" "$(BRANCH)"
	@printf "$(BOLD)$(MAGENTA)========================================$(RESET)\n\n"
	@printf "$(BOLD)Available Commands:$(RESET)\n\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@printf "\n$(YELLOW)Tip:$(RESET) Use 'make commit' for secure delivery.\n\n"

.PHONY: setup
setup: venv install env-init redis-ready ## Complete bootstrap (venv + deps + .env + redis)
	@printf "$(GREEN)✓ System bootstrap complete.$(RESET)\n"

.PHONY: commit
commit: check security ## [NΞØ] Secure commit & push flow (The Protocol)
	@printf "\n$(BOLD)$(CYAN)--- NΞØ SECURE COMMIT FLOW ---$(RESET)\n"
	@git status -s
	@printf "\n$(YELLOW)Conventional Commit Types: feat, fix, docs, style, refactor, test, chore$(RESET)\n"
	@read -p "Commit message: " msg; \
	if [ -z "$$msg" ]; then printf "$(RED)Aborted: Message required.$(RESET)\n"; exit 1; fi; \
	git add . && \
	git commit -m "$$msg" && \
	git push origin $(BRANCH) && \
	printf "$(GREEN)✓ Securely pushed to %s.$(RESET)\n" "$(BRANCH)"

# -----------------------------------------------------------------------------
# ⧉ AGENT RUNTIME
# -----------------------------------------------------------------------------

.PHONY: dev
dev: redis-ready ## Start Kernel Web UI (FastAPI + Hot Reload)
	@printf "$(CYAN)🚀 Launching UI at http://localhost:8000...$(RESET)\n"
	@REDIS_URL=$(REDIS_URL) $(UVICORN) web.app:app --host 127.0.0.1 --port 8000 --reload

.PHONY: dev-ui
dev-ui: redis-ready ## Start UI with deep watch for templates/CSS/JS
	@printf "$(CYAN)🎨 Launching UI with deep asset watch...$(RESET)\n"
	@REDIS_URL=$(REDIS_URL) $(UVICORN) web.app:app --host 127.0.0.1 --port 8000 --reload \
		--reload-include '*.py' \
		--reload-include 'web/templates/**/*.html' \
		--reload-include 'web/static/**/*.css' \
		--reload-include 'web/static/**/*.js'

.PHONY: guard
guard: redis-ready ## Start Focus Guard daemon (background loop)
	@printf "$(CYAN)🛡️ Focus Guard Active...$(RESET)\n"
	@$(PY) main.py daemon

.PHONY: sync
sync: redis-ready ## Synchronize Linear issues
	@$(PY) main.py sync

.PHONY: chat
chat: redis-ready ## Interactive Orchestrator Shell
	@$(PY) main.py chat

# -----------------------------------------------------------------------------
# ⨷ QUALITY ASSURANCE
# -----------------------------------------------------------------------------

.PHONY: check
check: lint test ## Run full local CI (Lint + Test)
	@printf "$(GREEN)✓ Local CI passed.$(RESET)\n"

.PHONY: lint
lint: ## Code style check & auto-fix
	@printf "$(CYAN)Linting with Ruff...$(RESET)\n"
	@$(RUFF) check . --fix || true

.PHONY: fmt
fmt: ## Code formatting
	@printf "$(CYAN)Formatting with Ruff...$(RESET)\n"
	@$(RUFF) format .

.PHONY: test
test: ## Run test suite
	@printf "$(CYAN)Executing Pytest...$(RESET)\n"
	@$(PYTEST) tests/ -v --tb=short

.PHONY: security
security: ## Vulnerability audit for dependencies
	@printf "$(CYAN)Auditing dependencies...$(RESET)\n"
	@$(PIP_AUDIT) || (printf "$(RED)⚠ Vulnerabilities found!$(RESET)\n"; exit 1)
	@printf "$(GREEN)✓ Security audit passed.$(RESET)\n"

# -----------------------------------------------------------------------------
# ⨀ REDIS MANAGEMENT
# -----------------------------------------------------------------------------

.PHONY: redis-ready
redis-ready: ## Ensure Redis is responsive (Local/Docker)
	@if redis-cli ping > /dev/null 2>&1; then exit 0; fi; \
	if docker ps | grep -q $(REDIS_CONTAINER); then exit 0; fi; \
	printf "$(YELLOW)Starting Redis Stack...$(RESET)\n"; \
	docker run -d --rm --name $(REDIS_CONTAINER) -p $(REDIS_PORT):6379 redis:7-alpine > /dev/null 2>&1 || \
	brew services start redis > /dev/null 2>&1 || \
	(printf "$(RED)✗ Failed to start Redis.$(RESET)\n"; exit 1)
	@sleep 1

.PHONY: redis-stats
redis-stats: ## Display Redis memory and command stats
	@redis-cli INFO stats | grep -E "connected|commands|memory|keys" || \
	docker exec $(REDIS_CONTAINER) redis-cli INFO stats | grep -E "connected|commands|memory|keys"

.PHONY: redis-keys
redis-keys: ## List all keys in Redis
	@redis-cli KEYS '*' | sort || docker exec $(REDIS_CONTAINER) redis-cli KEYS '*'

.PHONY: redis-flush
redis-flush: ## ⚠️  Wipe ALL Redis data
	@printf "$(RED)⚠️  Wipe local database? [y/N]$(RESET) " && read ans && [ $${ans:-N} = y ] && \
	(redis-cli FLUSHALL || docker exec $(REDIS_CONTAINER) redis-cli FLUSHALL) && \
	printf "$(YELLOW)✓ Database purged.$(RESET)\n"

# -----------------------------------------------------------------------------
# ◬ SYSTEM & DIAGNOSTICS
# -----------------------------------------------------------------------------

.PHONY: doctor
doctor: ## Deep system diagnostic
	@printf "$(CYAN)Running Kernel Doctor...$(RESET)\n"
	@printf "  $(BOLD)Python:$(RESET)   %s\n" "$$($(PY) --version)"
	@printf "  $(BOLD)Redis:$(RESET)    %s\n" "$$(redis-cli PING 2>/dev/null || echo 'DOWN')"
	@printf "  $(BOLD)Venv:$(RESET)     %s\n" "$$([ -d $(VENV) ] && echo 'OK' || echo 'MISSING')"
	@$(PY) -c "import agents.orchestrator, agents.focus_guard, agents.linear_sync; print('  \033[32mAgents:\033[0m   OK')" 2>&1 || printf "  $(RED)Agents:$(RESET)   import error\n"

.PHONY: logs
logs: ## Show recent logs
	@tail -f logs/*.log 2>/dev/null || printf "$(RED)No logs found.$(RESET)\n"

.PHONY: health
health: ## Check FastAPI /health endpoint
	@curl -s http://localhost:8000/health | $(PYTHON) -m json.tool

# -----------------------------------------------------------------------------
# ⌬ DOCKER MAINTENANCE
# -----------------------------------------------------------------------------

.PHONY: docker-clean
docker-clean: ## Deep Docker cleanup (Cache + Images)
	@docker system prune -f && docker image prune -af

.PHONY: docker-df
docker-df: ## Docker disk usage
	@docker system df

# -----------------------------------------------------------------------------
# 🛠️ UTILS
# -----------------------------------------------------------------------------

.PHONY: venv
venv:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)

.PHONY: install
install: venv
	@$(PIP) install --upgrade pip -q
	@$(PIP) install -r requirements.txt -q
	@$(PIP) install ruff pytest pip-audit ipython -q

.PHONY: env-init
env-init:
	@test -f .env || cp .env.example .env

.PHONY: clean
clean: ## Remove temporary build files
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@rm -rf .ruff_cache .pytest_cache .coverage htmlcov
	@printf "$(YELLOW)✓ Temp files removed.$(RESET)\n"

.PHONY: shell
shell: ## Drop into iPython shell with project context
	@$(BIN)/ipython
