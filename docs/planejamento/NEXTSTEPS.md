# NEXTSTEPS

Status: ativo  
Última atualização: 2026-04-03

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
- `docs/governanca/CONTRATO_AGENTES.md`
- `docs/planejamento/NEXTSTEPS.md`
- `docs/planejamento/SPRINT_VIDA.md`

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
- Redis local migrado de Docker para brew service nativo (`redis 8.6.2`) em 2026-04-06 — Docker não é mais necessário para notificações locais

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

- [x] Fazer commit seletivo do estado seguro
  - Status: DONE
  - Log: commit seguro criado com runtime, testes, docs de governança e higiene mínima de repo.
  - Commit: `c60b547`

- [x] Fazer push do estado seguro para `main`
  - Status: DONE
  - Log: branch intermediária foi consolidada, `main` foi limpo e os avanços relevantes voltaram para a linha principal do repositório.
  - Commit: `b60190d`

- [x] Publicar branch segura com o estado consolidado
  - Status: DONE
  - Log: branch `neonode-codex/stabilize-runtime-governance` criada e publicada no remoto com o commit seguro.
  - Commit: `c60b547`

- [x] Confirmar Railway estável após push
  - Status: DONE
  - Log: health check respondeu `db: ok`, sync com Notion trouxe tarefa real e a interface no Railway refletiu agenda e tarefa sincronizadas.
  - Commit: pendente

- [x] Fechar contrato operacional de notificações
  - Status: DONE
  - Log: diagnóstico fechado. `focus_guard` gera alerta no Railway, mas `mac_push` não funciona fora de macOS e Alexa depende de `VOICE_MONKEY_*`. Observabilidade do `notifier` foi reforçada e `docs/planejamento/SPRINT_VIDA.md` reescrito para distinguir local versus Railway.
  - Commit: pendente

- [x] Corrigir confiabilidade do chat web (contexto + resposta operacional)
  - Status: DONE
  - Log: chat passou a persistir histórico por sessão no Redis com TTL e fallback local, recebeu rota determinística para perguntas sobre capacidade do deploy e proteção anti-resposta papagaio.
  - Commit: `59250b9`, `5c6af40`, `0ac0cc6`

- [ ] Validar UX do chat no iPhone após deploy Railway
  - Status: TODO
  - Log: confirmar se input limpa após envio, se contexto persiste após refresh e se respostas de capacidade do sistema não caem em texto genérico.
  - Commit: pendente

### Fase 1. Governança dos agentes

- [x] Criar contrato recomendado, agente por agente
  - Status: DONE
  - Log: criado documento de contrato com função, entradas, saídas, memória, autoridade, riscos e ordem de formalização dos agentes.
  - Commit: `c60b547`

- [x] Revisar e aprovar contrato dos agentes
  - Status: DONE
  - Log: contrato lido, tensionado e validado como base da governança dos agentes, com separação clara entre kernel íntimo e camadas futuras.
  - Commit: pendente

- [x] Identificar quais prompts deixam de ser hardcoded e passam a ser governados pelo Sanity
  - Status: DONE
  - Log: mapeados os agentes com dependência real de LLM e os pontos onde a autoridade ainda está dividida entre código e Studio.
  - Commit: pendente

### Fase 2. Sanity v2

- [x] Alinhar `llm_prompt` com os agentes reais
  - Status: DONE
  - Log: `llm_prompt` foi reduzido ao conjunto real de entidades com uso de LLM, os prompts de `orchestrator`, `scheduler`, `validator`, `retrospective` e `focus_guard` foram publicados no Sanity, e o runtime passou a ler esses documentos com fallback explícito.
  - Commit: `679f390`

- [x] Alinhar `agent_config` com os agentes reais
  - Status: DONE
  - Log: `agent_config` foi alinhado ao catálogo real de agentes e capacidades, com publicação no Studio dos registros de governança para `focus_guard`, `life_guard`, `gemma_local`, `orchestrator`, `scheduler`, `notion_sync`, `validator`, `retrospective`, `calendar_sync` e `persona_manager`.
  - Commit: `679f390`

- [x] Resolver fonte canônica de `persona`
  - Status: DONE
  - Log: `persona_manager` passou a ler o Sanity como fonte primária e o disco como fallback explícito, preservando compatibilidade do runtime e eliminando a dupla verdade como regra operacional.
  - Commit: `679f390`

- [x] Definir schema de domínio `project`
  - Status: DONE
  - Log: schema `project` criado no Studio para modelar iniciativas estruturais, com campos de status, visibilidade, links e relações.
  - Commit: `679f390`

- [x] Definir schema de domínio `area`
  - Status: DONE
  - Log: schema `area` criado no Studio para separar áreas de vida e operação como camada semântica própria.
  - Commit: `679f390`

- [x] Definir schema de domínio `task`
  - Status: DONE
  - Log: schema `task` criado no Studio para representar tarefas canônicas com precedência semântica sobre o estado quente do Redis.
  - Commit: `679f390`

- [x] Definir schema de domínio `agenda_block`
  - Status: DONE
  - Log: schema `agenda_block` criado no Studio para consolidar blocos de agenda como entidades próprias, distintas da renderização efêmera do dia.
  - Commit: `679f390`

- [x] Definir schema de domínio `focus_session`
  - Status: DONE
  - Log: schema `focus_session` criado no Studio para capturar sessões de foco, desvio e outcome como histórico operacional interpretável.
  - Commit: `679f390`

- [x] Definir schema de domínio `signal`
  - Status: DONE
  - Log: schema definido no Studio e alinhado ao `docs/arquitetura/SCHEMA_SIGNAL_DECISION.md` como base da órbita externa do kernel.
  - Commit: `679f390`

- [x] Definir schema de domínio `source`
  - Status: DONE
  - Log: schema definido no Studio e alinhado ao `docs/arquitetura/SCHEMA_SIGNAL_DECISION.md` para distinguir origem estrutural de evento.
  - Commit: `679f390`

- [x] Definir schema de domínio `decision`
  - Status: DONE
  - Log: schema definido no Studio e alinhado ao `docs/arquitetura/SCHEMA_SIGNAL_DECISION.md` para consolidar sinais em resposta governável.
  - Commit: `679f390`

- [x] Definir schema de domínio `public_artifact`
  - Status: DONE
  - Log: schema `public_artifact` criado no Studio para sustentar a futura eclusa privado -> público sem vazamento direto do kernel íntimo.
  - Commit: `679f390`

- [x] Concluir Fase 2. Sanity v2
  - Status: DONE
  - Log: governança dos agentes consolidada no Sanity, Studio redeployado com schemas de domínio, runtime conectado ao Studio para prompts, personas e scripts de intervenção, e documentos-base publicados no dataset `production`.
  - Commit: `679f390`

### Fase 3. Fronteira privado -> público

- [ ] Desenhar o contrato da aba `Publish` no front privado
  - Status: TODO
  - Log:
  - Commit: pendente

### Fase 4. Órbita externa do kernel

- [x] Versionar configuração do ecossistema
  - Status: DONE
  - Log: criado `config/ecosystem.yml` com orgs, fontes, modo `pull_first`, TTL e política de publicação externa.
  - Commit: pendente

- [x] Definir thresholds explícitos do monitor externo
  - Status: DONE
  - Log: criado `config/alert_thresholds.yml` com limiares para GitHub, Railway, Vercel, Cloudflare e NEOFLW.
  - Commit: pendente

- [x] Reposicionar `SPRINT_ECOSSISTEMA` como camada externa do kernel
  - Status: DONE
  - Log: sprint reescrito para separar sinais do ecossistema da camada íntima e impedir acoplamento com `focus_guard`.
  - Commit: pendente

- [x] Implementar Fase 1 do `ecosystem_monitor`
  - Status: DONE
  - Log: agente criado em `agents/ecosystem_monitor.py`. Cobre GitHub (6 orgs), Railway (6 serviços via HTTP health check), DexScreener (NEOFLW). Comando `python main.py ecosistema` funcional. Relatório persistido no Redis. Alertas P0 disparam mac_push.
  - Commit: pendente

- [ ] Definir gate automatizado para desbloquear Fase 2 do monitor
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

### 2026-04-06

- Redis local migrado de Docker para `brew services` (redis 8.6.2 nativo macOS)
- `focus_guard_service` (launchd) passou a reconectar automaticamente — notificações macOS restauradas
- Makefile atualizado: `redis-up` e `redis-ensure` agora priorizam brew service, Docker fica como fallback

### 2026-04-03

- `SPRINT_ECOSSISTEMA` reposicionado como órbita externa do kernel
- criado `docs/governanca/PLANO_SOBERANIA_SANITY.md`
- criado `docs/arquitetura/SCHEMA_SIGNAL_DECISION.md`
- criado `config/ecosystem.yml`
- criado `config/alert_thresholds.yml`
- trilhas do plano, sprint e next steps foram amarradas
- docs reorganizados por taxonomia com `docs/INDEX.md` como entrada única (`257fa29`)
- baseline documental tagueado e publicado: `docs-aligned-2026-04-03`
- chat web reforçado com resposta determinística de capacidade, persistência em Redis e proteção anti-eco (`59250b9`, `5c6af40`, `0ac0cc6`)
