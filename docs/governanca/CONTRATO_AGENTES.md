# CONTRATO DOS AGENTES

Status: ativo  
Última atualização: 2026-04-02

## Propósito

Este documento define o contrato operacional de cada agente do sistema.

Ele existe para impedir três formas de mentira estrutural:

1. agente sem fronteira clara
2. agente com autoridade maior do que sua governança
3. agente publicando ou alterando estado sem trilha explícita

O objetivo não é descrever intenções abstratas.  
O objetivo é fixar função, entrada, saída, memória, autoridade, limites e futuro de integração com Sanity e publicação pública.

## Princípios

- Redis é a memória quente e operacional
- Sanity é a governança semântica e editorial
- Notion é a entrada humana e a captura bruta
- `mypersonal_multiagents` é o orquestrador do kernel privado
- `nettomello.eth.limo` só recebe artefatos explicitamente promovidos
- IPFS entra no final do fluxo público, nunca no início da modelagem
- nenhum agente publica algo público por conta própria

## Matriz Rápida

| Agente              |  Usa LLM | Lê Redis | Escreve Redis | Lê Sanity | Escreve Sanity | Lê Notion | Escreve Notion | Pode publicar |
| ------------------- | -------: | -------: | ------------: | --------: | -------------: | --------: | -------------: | ------------: |
| `orchestrator`      |      sim |      sim |      indireto |       sim |            não |       não |            não |           não |
| `focus_guard`       |      sim |      sim |           sim |       sim |            não |       sim |            não |           não |
| `scheduler`         |      sim |      sim |           sim |       sim |            não |       não |            não |           não |
| `validator`         |      sim |      sim |           sim |       sim |            não |       sim |            sim |           não |
| `retrospective`     |      sim |      sim |           não |       sim |            não |       sim |            sim |           não |
| `notion_sync`       |      não |      sim |           sim |   parcial |            não |       sim |            sim |           não |
| `calendar_sync`     |      não |      sim |           sim |   parcial |            não |       não |            não |           não |
| `life_guard`        |      não |      sim |           sim |   parcial |            não |       não |            não |           não |
| `ecosystem_monitor` |      não |      sim |           sim |   parcial |            não |       não |            não |           não |
| `persona_manager`   |      não |      não |           não |       sim |            não |       não |            não |           não |
| `gemma_local`       | fallback |      não |           não |   parcial |            não |       não |            não |           não |

## Contrato Recomendado, Agente por Agente

### `orchestrator`

Arquivo: `agents/orchestrator.py`

Função:

- interpretar intenção do usuário
- escolher handoffs
- consolidar resposta final

Entradas:

- input do usuário
- contexto agregado
- persona ativa
- estado resumido do sistema

Saídas:

- lista de handoffs
- síntese final em linguagem natural

Memória:

- lê Redis para contexto resumido
- não deve persistir artefatos próprios além de handoffs e observabilidade

Autoridade:

- pode delegar
- não deve alterar estado de negócio diretamente
- não publica

Governança desejada no Sanity:

- prompt `routing`
- prompt `synthesis`
- prompt `direct`
- policy de fallback

Estado atual:

- usa LLM
- prompts `routing`, `synthesis` e `direct` governados pelo Sanity com fallback explícito
- depende de personas resolvidas por `persona_manager`

Risco atual:

- ainda governa fallback e política de provider mais no código do que no Studio

### `focus_guard`

Arquivo: `agents/focus_guard.py`

Função:

- monitorar foco, desvio e sessões
- disparar check-ins
- reagendar quando necessário

Entradas:

- agenda do dia
- sessão ativa
- tarefas em andamento
- dados do Notion quando necessário

Saídas:

- alertas
- logs de desvio
- reschedules
- status de foco

Memória:

- lê e escreve Redis intensamente

Autoridade:

- pode alertar
- pode reagendar automaticamente dentro de regras
- não publica

Governança desejada no Sanity:

- prompt `deviation`
- configuração de intervalo
- scripts de intervenção
- thresholds de escalada

Estado atual:

- lê prompt de desvio do Sanity
- lê scripts de intervenção do Sanity por ambiente com fallback local
- é o agente mais maduro na camada de governança

Risco atual:

- ainda conserva fallback local para não quebrar operação se o Studio falhar

### `scheduler`

Arquivo: `agents/scheduler.py`

Função:

- gerir agenda
- sugerir blocos
- priorizar tarefas
- reorganizar dia útil

Entradas:

- tarefas
- blocos existentes
- contexto temporal

Saídas:

- blocos de agenda
- sugestões de priorização
- warnings de sobrecarga

Memória:

- lê e escreve Redis

Autoridade:

- pode criar blocos
- pode completar blocos
- pode propor agenda via LLM
- não publica

Governança desejada no Sanity:

- prompt `scheduling`
- policy de duração mínima
- policy de pausas
- parâmetros de conflito e carga

Estado atual:

- usa LLM
- prompt `scheduling` governado pelo Sanity com fallback explícito
- config publicada no Studio

Risco atual:

- parâmetros semânticos de carga, pausa e conflito ainda vivem mais no código do que no Studio

### `validator`

Arquivo: `agents/validator.py`

Função:

- confirmar se uma tarefa foi realmente concluída
- cruzar evidências
- evitar conclusão performática

Entradas:

- tarefa local
- sessões de foco
- blocos de agenda
- espelho do Notion

Saídas:

- `validated`
- `rejected`
- `pending_confirmation`

Memória:

- lê e escreve Redis
- pode refletir status no Notion

Autoridade:

- pode consolidar veredicto
- pode atualizar Notion quando o contrato permitir
- não publica

Governança desejada no Sanity:

- prompt `validation`
- policy de thresholds
- regras de consistência

Estado atual:

- usa LLM
- prompt `validation` governado pelo Sanity com fallback explícito
- config publicada no Studio

Risco atual:

- thresholds de consistência e política de veredicto ainda não foram externalizados por completo

### `retrospective`

Arquivo: `agents/retrospective.py`

Função:

- ler a semana
- gerar análise e relatório
- opcionalmente enviar para Notion

Entradas:

- sessões
- tarefas
- handoffs
- histórico recente

Saídas:

- relatório markdown
- página opcional no Notion

Memória:

- lê Redis
- não precisa estado quente próprio

Autoridade:

- pode sintetizar
- pode escrever retrospectiva no Notion
- não publica automaticamente

Governança desejada no Sanity:

- prompt `retrospective`
- template editorial
- política de exportação

Estado atual:

- usa LLM
- prompt `retrospective` governado pelo Sanity com fallback explícito
- config publicada no Studio

Risco atual:

- política de exportação e template final ainda não estão externalizados por completo

### `notion_sync`

Arquivo: `agents/notion_sync.py`

Função:

- sincronizar tarefas e agenda com Notion
- normalizar input humano para o kernel

Entradas:

- databases do Notion
- tarefas locais
- blocos locais

Saídas:

- tarefas locais atualizadas
- blocos derivados
- páginas atualizadas no Notion

Memória:

- lê e escreve Redis

Autoridade:

- pode importar
- pode atualizar status
- não decide política semântica
- não publica

Governança desejada no Sanity:

- mapeamento de origem
- política de reconciliação
- parâmetros operacionais

Estado atual:

- não usa LLM
- `agent_config` publicado no Studio
- governança ainda majoritariamente implícita no código

Risco atual:

- reconciliador sem contrato explícito de precedência entre fontes

### `calendar_sync`

Arquivo: `agents/calendar_sync.py`

Função:

- integrar Google Calendar à agenda operacional como capacidade opcional

Entradas:

- eventos do calendário
- blocos locais

Saídas:

- importação de eventos como blocos
- exportação de blocos para o calendário

Memória:

- lê e escreve Redis

Autoridade:

- pode espelhar agenda quando a integração opcional estiver ativa
- não interpreta prioridade nem intenção
- não publica

Governança desejada no Sanity:

- parâmetros operacionais
- política de import/export
- mapeamento de calendário
  com precedência explícita do Notion Agenda

Estado atual:

- não usa LLM
- `agent_config` publicado no Studio
- integração ainda vive principalmente no código como capacidade opcional

Risco atual:

- integração opcional ainda vive fora da camada de governança

### `life_guard`

Arquivo: `agents/life_guard.py`

Função:

- lembrar rotinas vitais
- lembrar hidratação
- lembrar refeições
- controlar rotinas recorrentes de vida

Entradas:

- relógio
- estados de rotina no Redis

Saídas:

- notificações
- flags de rotina enviada

Memória:

- lê e escreve Redis

Autoridade:

- pode notificar
- não deve inferir sem contrato
- não publica

Governança desejada no Sanity:

- parâmetros operacionais
- scripts de rotina
- janela ativa
- canais e intensidade

Estado atual:

- não usa LLM
- `agent_config` e `persona` publicados no Studio
- parâmetros centrais ainda vivem em env e código

Risco atual:

- é um agente de vida, mas ainda sem configuração digna de agente

### `ecosystem_monitor`

Arquivo: `agents/ecosystem_monitor.py`

Função:

- monitorar ecossistema externo
- produzir sinais e resumo operacional
- manter health checks e relatório diário

Entradas:

- APIs externas e serviços críticos
- estado recente no Redis

Saídas:

- sinais em cache
- relatório diário
- alertas P0 quando necessário

Memória:

- lê e escreve Redis

Autoridade:

- pode produzir sinais e relatórios
- não altera agenda íntima
- não publica

Governança desejada no Sanity:

- `signal`, `source`, `decision`
- thresholds e severidade
- política de TTL e dedupe

Estado atual:

- runtime ativo em `agents/ecosystem_monitor.py`
- persiste `health_check` e `daily_report` no Redis
- schema documentado em `../arquitetura/SCHEMA_SIGNAL_DECISION.md`

Risco atual:

- sinais ainda vivem como cache e texto
- governança de thresholds ainda fora do Sanity

### `persona_manager`

Arquivo: `agents/persona_manager.py`

Função:

- selecionar a persona ativa
- fornecer `system_prompt` e temperatures por fase

Entradas:

- arquivos JSON locais
- `persona_id` solicitado

Saídas:

- persona resolvida
- overrides de prompt e temperatura

Memória:

- sem Redis

Autoridade:

- governa tom e estilo da camada de linguagem
- não publica

Governança desejada no Sanity:

- fonte canônica de personas
- histórico editorial
- versionamento leve

Estado atual:

- Sanity é a fonte primária de persona
- `personas/` virou fallback explícito de runtime

Risco atual:

- ainda falta fechar versionamento editorial e política explícita de override por fase

## Ordem Recomendada de Formalização

1. `ecosystem_monitor`
2. `notion_sync`
3. `calendar_sync`
4. `life_guard`
5. `gemma_local`

## Política de Publicação

Nenhum agente acima pode publicar diretamente em `nettomello.eth.limo`.

Fluxo correto:

1. agente produz sinal ou decisão
2. Redis registra o estado operacional
3. Sanity canoniza quando for memória estrutural
4. um item elegível vira `public_artifact`
5. revisão humana aprova
6. só então artefato pode seguir para IPFS e domínio público

## Papel do Gemma Local

Modelo local configurado:

- `docker.io/ai/gemma3:4B-F16`
- fallback em `core/openai_utils.py`

Papel recomendado:

- contingência quando OpenAI falhar
- tarefas de baixa criticidade editorial
- rascunhos operacionais
- classificação simples
- triagem local

Não usar como autoridade final para:

- síntese pública
- decisões de publicação
- validações críticas de conclusão
- artefatos destinados a `nettomello.eth.limo`

## Critério de Conclusão

Este contrato só estará realmente ativo quando:

- cada agente tiver instrução explícita ou decisão explícita de não usar instrução
- a governança do Sanity refletir o runtime real
- a fonte de verdade de persona estiver unificada
- a política privado -> público estiver documentada e implementada
