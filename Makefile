.PHONY: help install run env-check

PYTHON ?= python3
APP := main.py
ENV_FILE ?= .env
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python3
APP_PYTHON := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),$(PYTHON))
CMD ?=
ARGS ?=

help:
	@printf "\nComandos disponíveis:\n"
	@printf "  make install           Cria .venv e instala dependências Python\n"
	@printf "  make run               Abre o modo interativo\n"
	@printf "  make run CMD=status    Executa comando simples da CLI\n"
	@printf "  make run CMD=tasks     Lista tarefas\n"
	@printf "  make run CMD=agenda    Mostra agenda de hoje\n"
	@printf "  make run CMD=sync      Sincroniza com o Notion\n"
	@printf "  make run CMD=suggest   Gera sugestão de agenda via LLM\n"
	@printf "  make run CMD=add-task  Abre wizard para criar tarefa\n"
	@printf "  make run CMD=demo      Cria dados de demonstração\n"
	@printf "  make run CMD=validate ARGS=3         Valida tarefa\n"
	@printf "  make run CMD=focus ARGS='start 3'    Inicia foco em tarefa\n"
	@printf "  make run CMD=focus ARGS=end          Encerra foco ativo\n"
	@printf "  make env-check         Confere variáveis essenciais do .env\n\n"

install:
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	@printf "\nAmbiente pronto em $(VENV_DIR).\n"
	@printf "Ative com: source $(VENV_DIR)/bin/activate\n\n"

run:
	$(APP_PYTHON) $(APP) $(CMD) $(ARGS)

env-check:
	@for key in OPENAI_API_KEY NOTION_TOKEN NOTION_TASKS_DB_ID NOTION_AGENDA_DB_ID; do \
		line=$$(grep -E "^$$key=" $(ENV_FILE) | head -n 1); \
		value=$${line#*=}; \
		value=$${value%%#*}; \
		value=$$(printf "%s" "$$value" | sed 's/[[:space:]]*$$//'); \
		if [ "$$key" = "OPENAI_API_KEY" ] || [ "$$key" = "NOTION_TOKEN" ]; then \
			if [ -n "$$value" ]; then echo "$$key=set"; else echo "$$key=missing"; fi; \
		else \
			if [ -n "$$value" ]; then echo "$$key=$$value"; else echo "$$key=missing"; fi; \
		fi; \
	done
