# =============================================================================
# NΞØ PROTOCOL — MULTIAGENTS KERNEL OS
# =============================================================================
# File: Makefile
# Version: 1.2.5 (Resilient Edition)
# Role: System Orchestration, Environment Repair & Secure Delivery
# =============================================================================

# -----------------------------------------------------------------------------
# CONFIGURATION & VARIABLES
# -----------------------------------------------------------------------------
SHELL       := /bin/bash
VENV        := .venv
BIN         := $(VENV)/bin
PIP         := $(BIN)/pip
PY          := $(BIN)/python
RUFF        := $(BIN)/ruff
PYTEST      := $(BIN)/pytest
PIP_AUDIT   := $(BIN)/pip-audit

# Automatically find a working python interpreter that is not blocked by macOS sandboxing
PYTHON := $(shell \
	for cmd in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.13 /usr/local/bin/python3 /usr/bin/python3 python3; do \
		if command -v $$cmd >/dev/null 2>&1 && $$cmd -c "import sys" >/dev/null 2>&1; then \
			echo $$cmd; \
			exit 0; \
		fi; \
	done; \
	echo "python3" \
)

# Project Identity
PROJECT_NAME := mypersonal_multiagents
VERSION      := $(shell git describe --tags --always 2>/dev/null || echo "v1.2.5")
BRANCH       := $(shell git branch --show-current 2>/dev/null || echo "main")

# Aesthetics (ANSI Colors)
BOLD   := $(shell printf '\033[1m')
CYAN   := $(shell printf '\033[36m')
GREEN  := $(shell printf '\033[32m')
YELLOW := $(shell printf '\033[33m')
RED    := $(shell printf '\033[31m')
RESET  := $(shell printf '\033[0m')
MAGENTA:= $(shell printf '\033[35m')

# Redis Config (local dev only — main.py/web use REDIS_URL from .env)
REDIS_CONTAINER := multiagentes-redis
REDIS_PORT      := 6379
REDIS_HOST      := 127.0.0.1
REDIS_LOCAL_URL := redis://$(REDIS_HOST):$(REDIS_PORT)/0

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
	@printf "  $(BOLD)Python Discovery:$(RESET) %s\n" "$(PYTHON)"
	@printf "$(BOLD)$(MAGENTA)========================================$(RESET)\n\n"
	@printf "$(BOLD)Available Commands:$(RESET)\n\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@printf "\n$(YELLOW)Tip:$(RESET) Use 'make commit' for secure delivery.\n\n"

.PHONY: setup
setup: venv install env-init redis-ready ## Complete bootstrap (venv + deps + .env + redis)
	@printf "$(GREEN)✓ System bootstrap complete. Run 'make doctor' to verify.$(RESET)\n"

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

.PHONY: guard
guard: venv ## Start Focus Guard daemon (uses REDIS_URL from .env)
	@printf "$(CYAN)🛡️ Focus Guard Active...$(RESET)\n"
	@$(PY) main.py daemon

.PHONY: sync
sync: venv ## Synchronize Linear issues (uses REDIS_URL from .env)
	@$(PY) main.py sync

.PHONY: chat
chat: venv ## Interactive Orchestrator Shell (uses REDIS_URL from .env)
	@$(PY) main.py chat

# -----------------------------------------------------------------------------
# ⨷ QUALITY ASSURANCE
# -----------------------------------------------------------------------------

.PHONY: check
check: lint test ## Run full local CI (Lint + Test)
	@printf "$(GREEN)✓ Local CI passed.$(RESET)\n"

.PHONY: lint
lint: venv ## Code style check & auto-fix
	@printf "$(CYAN)Linting with Ruff...$(RESET)\n"
	@if [ -f $(RUFF) ]; then $(RUFF) check . --fix || true; else printf "$(RED)Ruff not installed. Run 'make install'.$(RESET)\n"; exit 1; fi

.PHONY: fmt
fmt: venv ## Code formatting
	@printf "$(CYAN)Formatting with Ruff...$(RESET)\n"
	@if [ -f $(RUFF) ]; then $(RUFF) format .; else printf "$(RED)Ruff not installed. Run 'make install'.$(RESET)\n"; exit 1; fi

.PHONY: test
test: venv ## Run test suite
	@printf "$(CYAN)Executing Pytest...$(RESET)\n"
	@if [ -f $(PYTEST) ]; then $(PYTEST) tests/ -v --tb=short; else printf "$(RED)Pytest not installed. Run 'make install'.$(RESET)\n"; exit 1; fi

.PHONY: security
security: venv ## Vulnerability audit for dependencies
	@printf "$(CYAN)Auditing dependencies...$(RESET)\n"
	@if [ -f $(PIP_AUDIT) ]; then \
		$(PIP_AUDIT) || (printf "$(RED)⚠ Vulnerabilities found!$(RESET)\n"; exit 1); \
	else \
		printf "$(YELLOW)pip-audit not installed. Installing and running...$(RESET)\n"; \
		$(PIP) install pip-audit -q && $(PIP_AUDIT) || (printf "$(RED)⚠ Vulnerabilities found!$(RESET)\n"; exit 1); \
	fi
	@printf "$(GREEN)✓ Security audit passed.$(RESET)\n"

# -----------------------------------------------------------------------------
# ⨀ REDIS MANAGEMENT
# -----------------------------------------------------------------------------

.PHONY: redis-ready
redis-ready: ## Ensure Redis is responsive (Local/Docker)
	@if command -v redis-cli >/dev/null 2>&1 && redis-cli ping > /dev/null 2>&1; then exit 0; fi; \
	if docker ps 2>/dev/null | grep -q $(REDIS_CONTAINER); then exit 0; fi; \
	printf "$(YELLOW)Starting Redis Stack...$(RESET)\n"; \
	docker run -d --rm --name $(REDIS_CONTAINER) -p $(REDIS_PORT):6379 redis:7-alpine > /dev/null 2>&1 || \
	brew services start redis > /dev/null 2>&1 || \
	(printf "$(RED)✗ Failed to start Redis.$(RESET)\n"; exit 1)
	@sleep 1

.PHONY: redis-stats
redis-stats: ## Display local Redis memory and command stats
	@if command -v redis-cli >/dev/null 2>&1; then \
		redis-cli INFO stats | grep -E "connected|commands|memory|keys" || true; \
	else \
		docker exec $(REDIS_CONTAINER) redis-cli INFO stats 2>/dev/null | grep -E "connected|commands|memory|keys" || true; \
	fi

.PHONY: redis-keys
redis-keys: ## List all keys in local Redis
	@if command -v redis-cli >/dev/null 2>&1; then \
		redis-cli KEYS '*' | sort || true; \
	else \
		docker exec $(REDIS_CONTAINER) redis-cli KEYS '*' 2>/dev/null || true; \
	fi

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
	@if [ -d $(VENV) ] && $(PY) -c "import sys" >/dev/null 2>&1; then \
		printf "  $(BOLD)Python (Venv):$(RESET) %s\n" "$$($(PY) --version)"; \
		printf "  $(BOLD)Venv:$(RESET)          $(GREEN)OK$(RESET)\n"; \
		$(PY) -c "import agents.orchestrator, agents.focus_guard, agents.linear_sync; print('  $(BOLD)Agents:$(RESET)        \033[32mOK\033[0m')" 2>/dev/null || printf "  $(BOLD)Agents:$(RESET)        $(RED)import error$(RESET)\n"; \
	else \
		printf "  $(BOLD)Python (Venv):$(RESET) $(RED)BROKEN or MISSING$(RESET)\n"; \
		printf "  $(BOLD)Venv:$(RESET)          $(RED)FAIL$(RESET)\n"; \
		printf "  $(YELLOW)Tip: Run 'make setup' to automatically recreate and install dependencies.$(RESET)\n"; \
	fi
	@printf "  $(BOLD)Redis:$(RESET)         %s\n" "$$(redis-cli PING 2>/dev/null || echo 'DOWN')"

.PHONY: logs
logs: ## Show recent logs
	@tail -f logs/*.log 2>/dev/null || printf "$(RED)No logs found.$(RESET)\n"

.PHONY: status
status: ## Show git status
	@git status

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
	@if [ -d $(VENV) ]; then \
		if ! $(PY) -c "import sys" >/dev/null 2>&1; then \
			printf "$(YELLOW)Existing virtualenv is broken or outdated (e.g. sandboxed python). Recreating...$(RESET)\n"; \
			rm -rf $(VENV); \
		fi; \
	fi
	@if [ ! -d $(VENV) ]; then \
		printf "$(CYAN)Creating virtualenv with Python: %s...$(RESET)\n" "$(PYTHON)"; \
		$(PYTHON) -m venv $(VENV) || (printf "$(RED)Failed to create virtualenv.$(RESET)\n"; exit 1); \
	fi

.PHONY: install
install: venv ## Install project + dev dependencies into venv
	@printf "$(CYAN)Upgrading pip & installing dependencies...$(RESET)\n"
	@$(PIP) install --upgrade pip -q
	@$(PIP) install -r requirements.txt -q
	@$(PIP) install ruff pytest pip-audit ipython -q
	@printf "$(GREEN)✓ Dependencies installed.$(RESET)\n"

.PHONY: env-init
env-init: ## Copy .env.example → .env (skips if .env already exists)
	@test -f .env || cp .env.example .env

.PHONY: clean
clean: ## Remove temporary build files
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@rm -rf .ruff_cache .pytest_cache .coverage htmlcov
	@printf "$(YELLOW)✓ Temp files removed.$(RESET)\n"

.PHONY: shell
shell: venv ## Drop into iPython shell with project context
	@if [ -f $(BIN)/ipython ]; then $(BIN)/ipython; else $(PY) -m IPython; fi
