# PLANO DE SOBERANIA DO SANITY

Status: autorizado
Última atualização: 2026-04-03

## Tese

Este plano existe para transformar o Sanity de
camada auxiliar de configuração em camada canônica
de governança e, depois, de modelagem semântica do
kernel privado.

O objetivo não é “usar CMS”.

O objetivo é construir uma arquitetura em que:

- Notion captura
- Redis opera
- Sanity governa
- `mypersonal_multiagents` orquestra
- `neo-mello-eth` publica

## Princípios de precedência

1. Notion é a origem principal de tarefas e agenda
2. Google Calendar é capacidade opcional
3. Redis é estado quente e operacional
4. Sanity é verdade semântica e editorial
5. Nenhum agente publica por conta própria
6. IPFS entra no final do fluxo público

## Fase 1 — Fechar governança dos agentes

Objetivo:

- representar todos os agentes relevantes no Sanity
  com padrão uniforme

Escopo:

- `agent_config`
- `persona`
- `llm_prompt`
- `intervention_script`

Agentes-alvo:

- `orchestrator`
- `focus_guard`
- `scheduler`
- `notion_sync`
- `validator`
- `retrospective`
- `calendar_sync`
- `life_guard`
- `persona_manager`
- `gemma_local`
- `ecosystem_monitor`

Critério de conclusão:

- nenhum agente importante fica sem representação
  explícita no Studio

Risco principal:

- criar documentos incompletos e chamar isso de
  governança

## Fase 2 — Eliminar duplas verdades

Objetivo:

- reduzir conflito entre código hardcoded e Sanity

Escopo:

- prompts
- personas
- políticas de intervenção
- parâmetros operacionais

Movimento esperado:

- Sanity vira fonte primária
- código mantém fallback explícito só onde for
  necessário para resiliência

Critério de conclusão:

- a governança dos agentes não depende mais de
  constantes espalhadas pelo runtime

Risco principal:

- metade da autoridade no código, metade no Studio

## Fase 3 — Formalizar precedência entre fontes

Objetivo:

- impedir ambiguidade estrutural de origem

Contrato:

- Notion Tasks = fonte principal de tarefas
- Notion Agenda = fonte principal de agenda
- Google Calendar = integração opcional
- Redis = execução corrente
- Sanity = interpretação e memória semântica

Critério de conclusão:

- docs, UI, contratos e código contam a mesma
  história

Risco principal:

- sistema dizer uma coisa e operar outra

## Fase 4 — Subir a camada de domínio

Objetivo:

- fazer o Sanity modelar o mundo, não só os agentes

Schemas-alvo:

- `project`
- `area`
- `task`
- `agenda_block`
- `focus_session`
- `signal`
- `decision`
- `source`
- `public_artifact`

Observação decisiva:

- `signal`, `source` e `decision` são a ponte entre
  o kernel íntimo e a órbita externa do
  `ecosystem_monitor`
- o monitor existe, mas deve operar com cache
  em Redis e promover sinais ao Sanity

Critério de conclusão:

- o Studio permitir navegar a operação como grafo,
  não só editar prompts
- o monitor externo ter onde pousar seus sinais sem
  virar log glorificado

Risco principal:

- despejar Redis no Sanity sem semântica

## Fase 5 — Construir a eclusa privado → público

Objetivo:

- impedir vazamento estrutural do kernel privado

Fluxo:

- kernel privado gera contexto
- Sanity classifica
- `public_artifact` marca elegibilidade
- revisão humana aprova
- `neo-mello-eth` distribui

Critério de conclusão:

- nada público sai sem gate explícito

Risco principal:

- misturar operação íntima com superfície pública

## Fase 6 — Posicionar IPFS no ponto certo

Objetivo:

- usar IPFS como distribuição pública, não como
  cérebro do sistema

Ordem correta:

- Sanity decide
- Publish Gate aprova
- `neo-mello-eth` publica
- IPFS/IPNI propagam

Critério de conclusão:

- IPFS participa da publicação, não da confusão
  semântica

Risco principal:

- empurrar CID cedo demais e chamar isso de
  arquitetura

## Fase 7 — Fechar observabilidade e notificações

Objetivo:

- distinguir geração de alerta de entrega real

Escopo:

- logs por canal
- entrega local macOS
- entrega Alexa em produção
- critérios de falha por ambiente

Critério de conclusão:

- cada alerta crítico tem trilha clara de geração,
  tentativa e entrega

Risco principal:

- backend parecer ativo enquanto o canal está mudo

## Ordem de execução

1. Governança dos agentes no Sanity
2. Remoção das duplas verdades
3. Precedência entre fontes
4. `signal/source/decision` como ponte semântica
5. Demais schemas de domínio
6. Eclusa privado → público
7. IPFS/IPNI no fim do pipeline
8. Observabilidade e entrega real

## Regra de disciplina

Nenhuma fase conta como concluída apenas porque:

- existe código
- existe tela
- existe draft
- existe intenção

Uma fase só fecha quando:

- o contrato está explícito
- o comportamento foi validado
- a fonte de verdade está definida
- a documentação não contradiz o runtime

## Próximo passo autorizado

Fechar a Fase 1 por completo:

- inventário final dos agentes
- padronização dos documentos do Sanity
- publicação apenas do núcleo governável
