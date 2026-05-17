# POLÍTICA DE PRECEDÊNCIA DO NOTION

Status: ativo  
Última atualização: 2026-04-03

## Propósito

Este documento define quem vence quando `Notion`, `Redis`
e `Sanity` discordam sobre a mesma entidade.

Sem esta política, `notion_sync` vira reconciliador com
boa intenção e soberania acidental.

## Entidades cobertas

- `task`
- `agenda_block`
- status de execução
- horário previsto
- horário real
- decisão de publicação

## Regra-mãe

Cada camada governa uma classe diferente de verdade:

- `Notion` governa captura humana e intenção bruta
- `Redis` governa estado operacional do agora
- `Sanity` governa significado, memória estrutural e
  política editorial

Nenhuma camada deve fingir soberania fora do seu domínio.

## Precedência por tipo de dado

### 1. Captura humana

Exemplos:
- título digitado manualmente
- prioridade escolhida manualmente
- horário previsto escrito no Notion
- criação de tarefa ou bloco pela interface humana

Vencedor:
- `Notion`

Regra:
- se um campo nasceu como entrada humana explícita no
  Notion e ainda não foi reinterpretado pelo sistema,
  `notion_sync` deve importar, não corrigir

### 2. Estado operacional atual

Exemplos:
- tarefa em andamento
- tarefa vencida
- bloco concluído hoje
- sessão ativa
- alerta aberto

Vencedor:
- `Redis`

Regra:
- o runtime vence enquanto o fato estiver no presente
  operacional
- `notion_sync` não deve degradar estado quente para um
  status mais antigo vindo do Notion

Exemplo:
- tarefa em `Em progresso` no Redis
- Notion ainda mostra `A fazer`
- durante o sync, vence `Redis`

### 3. Significado semântico e memória estrutural

Exemplos:
- a tarefa pertence a qual projeto
- qual área ela serve
- se algo é privado, interno ou público
- que sinal virou decisão

Vencedor:
- `Sanity`

Regra:
- `notion_sync` não decide semântica estrutural
- ele só transporta e reconcilia captura humana e estado
  operacional

### 4. Publicação e exposição pública

Exemplos:
- algo pode ou não ir para `nettomello.eth.limo`
- algo pode ou não virar CID no IPFS

Vencedor:
- `Sanity`, via `public_artifact` e revisão humana

Regra:
- Notion nunca autoriza publicação
- Redis nunca autoriza publicação

## Regras por entidade

### `task`

Campos cujo vencedor padrão é `Notion`:
- `title`
- `priority`
- `scheduled_time` quando veio de input humano
- `notion_page_id`

Campos cujo vencedor padrão é `Redis`:
- `status` operacional atual
- `actual_time`
- flags de atraso ou vencimento

Campos cujo vencedor padrão é `Sanity`:
- `project_ref`
- `area_ref`
- `visibility`
- `public_eligibility`

### `agenda_block`

Campos cujo vencedor padrão é `Notion`:
- data criada manualmente
- texto-base do bloco

Campos cujo vencedor padrão é `Redis`:
- concluído ou aberto no dia corrente
- overdue
- bloco derivado automaticamente para hoje

Campos cujo vencedor padrão é `Sanity`:
- classificação estrutural
- vínculo editorial
- elegibilidade pública

## Tabela de decisão

| Situação | Vence | Ação do `notion_sync` |
|---|---|---|
| Tarefa nova existe no Notion e não existe localmente | Notion | importar e criar local |
| Tarefa existe localmente e no Notion, mas o status diverge | Redis | preservar estado local e refletir no Notion quando permitido |
| Título diverge entre Notion e Redis | Notion | atualizar título local |
| Prioridade diverge entre Notion e Redis | Notion | atualizar prioridade local |
| Campo semântico diverge entre Notion e Sanity | Sanity | não sobrescrever semântica a partir do Notion |
| Bloco do dia foi criado automaticamente pelo sistema | Redis | manter como estado quente e opcionalmente refletir depois |
| Item marcado público no Notion sem `public_artifact` | Sanity | ignorar intenção de publicação até revisão humana |

## Regras de reconciliação

### Sync Notion -> Redis

Permitido:
- importar novos itens
- atualizar campos de captura humana
- enriquecer com `notion_page_id`

Não permitido:
- rebaixar `status` operacional
- apagar efeitos do runtime
- sobrescrever semântica canônica

### Sync Redis -> Notion

Permitido:
- refletir status operacional
- refletir horário real
- criar bloco derivado quando a regra do sistema pedir

Não permitido:
- reescrever título humano sem motivo explícito
- inventar prioridade
- promover publicação

### Sync Sanity -> runtime

Permitido:
- governar semântica
- governar visibilidade
- governar relações de projeto e área

Não permitido:
- fingir estado quente de execução

## Resolução de conflitos

Quando houver conflito, `notion_sync` deve classificar o
campo antes de decidir.

Sequência obrigatória:

1. identificar o tipo do campo
2. identificar a camada soberana daquele campo
3. preservar o valor soberano
4. registrar conflito relevante em log
5. opcionalmente emitir `signal` quando houver ambiguidade
   recorrente

## Casos que devem virar `signal`

- Notion tenta rebaixar status operacional repetidamente
- Notion muda título ou prioridade em alta frequência
- bloco derivado local conflita com agenda humana
- item semântico vindo do Notion contradiz `Sanity`
- mesmo item entra em conflito mais de 3 vezes em 24h

## Política de logs

`notion_sync` deve registrar:
- importações novas
- atualizações aceitas
- atualizações rejeitadas por precedência
- conflitos recorrentes

Formato desejado:

```text
[notion_sync] precedence=redis field=status local="Em progresso" notion="A fazer" action=preserved_local
```

## Critério de conclusão

Esta política só estará realmente ativa quando:

- `notion_sync` classificar campos por soberania
- conflitos relevantes virarem log explícito
- testes cobrirem divergência entre `Notion` e `Redis`
- a precedência estiver refletida no código, e não só neste
  documento
