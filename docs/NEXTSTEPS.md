# NEXTSTEPS

Status: ativo  
Última atualização: 2026-04-02

## Como este documento deve ser usado

Este arquivo é o trilho de execução do projeto.

Nenhuma frente deve ser considerada concluída sem:

1. checkbox marcado
2. nota curta em `Log`
3. referência do commit em `Commit`

Formato obrigatório ao finalizar um item:

- `Status`: `DONE`
- `Log`: o que foi feito, em 1 a 3 linhas
- `Commit`: hash curto, link da PR, ou link do commit

Se não houve commit ainda, escrever:

- `Commit`: `pendente`

## Regra de Execução

- não pular etapa
- não abrir nova frente sem fechar a anterior ou registrar bloqueio
- sempre registrar o que foi decidido
- toda decisão estrutural precisa deixar rastro

## Fila Safe de Commit/Push

### Pode entrar no commit seguro

- `config.py`
- `Dockerfile`
- `.devcontainer/devcontainer.json`
- `agents/notion_sync.py`
- `core/memory.py`
- `core/notifier.py`
- `sanity/schemaTypes/persona.js`
- `tests/test_calendar_sync.py`
- `tests/test_memory.py`
- `tests/test_notifier_openai_utils.py`
- `tests/test_notion_sync.py`
- `tests/test_persona_manager.py`
- `tests/test_retrospective.py`
- `tests/test_scheduler.py`
- `tests/test_validator.py`
- `tests/test_web_chat.py`
- `web/app.py`
- `web/templates/base.html`
- `web/templates/index.html`
- `web/templates/partials/block_row.html`
- `web/templates/partials/status.html`
- `web/templates/partials/task_row.html`
- `web/templates/tasks_page.html`
- `docs/CONTRATO_AGENTES.md`
- `docs/NEXTSTEPS.md`
- `docs/SPRINT_VIDA.md`

### Não deve entrar no commit seguro

- `.claude/settings.local.json`
- `dump.rdb`

Motivo:
- arquivo local de ferramenta
- artefato de estado
- aumenta ruído e acopla ambiente pessoal ao repo

### Higiene ainda pendente

- adicionar `.DS_Store` ao `.gitignore` se aparecer novamente
- avaliar se `dump.rdb` deve ser removido do versionamento, não só ignorado

## Análise de Portas Abertas

Leitura em 2026-04-02:

- `8000` em `127.0.0.1`
  - esperado
  - é a Web UI local

- `6379`
  - esperado
  - Redis local ativo

- `4001`
  - esperado
  - swarm/libp2p do IPFS

- `5001`
  - esperado
  - API local do IPFS

- `8082`
  - esperado
  - gateway local do IPFS

- `36207`, `36865`, `34869`, `39194`, `34643`, `39850`
  - ruído controlado
  - portas efêmeras do Dev Container, VS Code Server e auto-forward

- `5000` e `7000`
  - não parecem ser do projeto
  - pertencem a `ControlCe`
  - devem ser identificadas antes de qualquer abertura pública ou automação sobre essas portas

Conclusão:

- não há ruído crítico nas portas do projeto
- há ruído ambiental de tooling
- o que importa de verdade hoje é `8000`, `6379`, `4001`, `5001`, `8082`

## Papel do Gemma Local

Modelo local detectado:
- `docker.io/ai/gemma3:4B-F16`
- configurado em `config.py`
- fallback implementado em `core/openai_utils.py`

Diretriz:

- o Gemma local deve ser tratado como agente de contingência e triagem
- ele reduz dependência da OpenAI para tarefas de baixo risco
- ele não deve ser usado como juiz final de publicação ou validação crítica

Usos recomendados:

- classificação simples
- rascunho inicial
- sumarização operacional
- fallback local quando OpenAI falhar
- tarefas internas de baixa criticidade

Usos não recomendados:

- síntese editorial pública
- decisões de publicação em `nettomello.eth.limo`
- validação final de conclusão
- arbitragem semântica de alto impacto

## Trilha de Execução

### Fase 0. Estabilizar a base atual

- [ ] Fazer commit seletivo do estado seguro
  - Status: DONE
  - Log: commit seguro criado com runtime, testes, docs de governança e higiene mínima de repo.
  - Commit: `c60b547`

- [ ] Fazer push do estado seguro para `main`
  - Status: TODO
  - Log: bloqueado porque `origin/main` está 4 commits à frente. Trabalho publicado em branch segura para não contaminar histórico nem forçar merge.
  - Commit: pendente

- [x] Publicar branch segura com o estado consolidado
  - Status: DONE
  - Log: branch `neonode-codex/stabilize-runtime-governance` criada e publicada no remoto com o commit seguro.
  - Commit: `c60b547`

- [ ] Confirmar Railway estável após push
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Fechar contrato operacional de notificações
  - Status: IN_PROGRESS
  - Log: diagnóstico fechado. `focus_guard` gera alerta no Railway, mas `mac_push` não funciona fora de macOS e Alexa depende de `VOICE_MONKEY_*` ou `IFTTT_*`. Observabilidade do `notifier` foi reforçada e `SPRINT_VIDA.md` reescrito para distinguir local versus Railway.
  - Commit: pendente

### Fase 1. Governança dos agentes

- [x] Criar contrato recomendado, agente por agente
  - Status: DONE
  - Log: criado documento de contrato com função, entradas, saídas, memória, autoridade, riscos e ordem de formalização dos agentes.
  - Commit: `c60b547`

- [ ] Revisar e aprovar contrato dos agentes
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Identificar quais prompts deixam de ser hardcoded e passam a ser governados pelo Sanity
  - Status: TODO
  - Log:
  - Commit: pendente

### Fase 2. Sanity v2

- [ ] Alinhar `llm_prompt` com os agentes reais
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Alinhar `agent_config` com os agentes reais
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Resolver fonte canônica de `persona`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir schema de domínio `project`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir schema de domínio `area`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir schema de domínio `task`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir schema de domínio `agenda_block`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir schema de domínio `focus_session`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir schema de domínio `signal`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir schema de domínio `decision`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir schema de domínio `source`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir schema de domínio `public_artifact`
  - Status: TODO
  - Log:
  - Commit: pendente

### Fase 3. Fronteira privado -> público

- [ ] Desenhar o contrato da aba `Publish` no front privado
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir política de promoção para `public_artifact`
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir critérios de revisão humana obrigatória
  - Status: TODO
  - Log:
  - Commit: pendente

### Fase 4. IPFS e publicação

- [ ] Desenhar fluxo Sanity -> `public_artifact` -> IPFS
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir quando gerar novo CID
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Definir papel do IPNI na descoberta pública
  - Status: TODO
  - Log:
  - Commit: pendente

- [ ] Integrar publicação com `nettomello.eth.limo`
  - Status: TODO
  - Log:
  - Commit: pendente

## Registros

### 2026-04-02

- inventário real dos agentes concluído
- contrato dos agentes criado
- trilha `NEXTSTEPS` criada
- portas locais revisadas
- papel do Gemma local explicitado
- sugestões críticas da PR 2 endereçadas com correções de HTMX, consistência de filtros, índice reverso do Notion, teste determinístico, docs e Dockerfile
- commit de correção da PR 2: `86c0e0f`
