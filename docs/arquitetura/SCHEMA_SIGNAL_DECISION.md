# SCHEMA SIGNAL SOURCE DECISION

Status: draft operacional
Ultima atualizacao: 2026-04-03

## Proposito

Definir a camada minima que permite ao
`ecosystem_monitor` produzir inteligencia real em vez
de apenas log.

Esta camada existe para responder tres perguntas:

1. o que aconteceu
2. de onde veio
3. exige decisao ou nao

## Regra de modelagem

- `Signal` registra um fato relevante
- `Source` descreve a origem estrutural desse fato
- `Decision` registra a interpretacao e a resposta

Sem esses tres tipos, o monitor externo vira um script
com boa retorica e memoria ruim.

## Signal

Representa um evento, mudanca, anomalia ou observacao
vinda de uma fonte externa ou interna.

Campos minimos:

```json
{
  "id": "signal_2026_04_03_railway_service_down",
  "source_id": "source_railway_mello_dash",
  "kind": "service_status",
  "severity": "fail",
  "message": "Service mypersonal_multiagents offline for 7 minutes",
  "timestamp": "2026-04-03T14:12:00-03:00",
  "actionable": true,
  "decision_required": true,
  "context": {
    "service": "mypersonal_multiagents",
    "project": "Mello Dash",
    "minutes_down": 7
  }
}
```

Campos recomendados:

- `id`
- `source_id`
- `kind`
- `severity`
- `message`
- `timestamp`
- `actionable`
- `decision_required`
- `context`
- `dedupe_key`
- `ttl_hours`
- `status`

Enums sugeridos:

- `severity`: `ok`, `warn`, `fail`, `critical`
- `status`: `open`, `acknowledged`, `dismissed`, `resolved`

## Source

Representa a fonte estrutural que produz sinais.

Campos minimos:

```json
{
  "id": "source_railway_mello_dash",
  "provider": "railway",
  "scope": "project",
  "name": "Mello Dash",
  "identifier": "d9b36ed2-fb3c-43ff-bb2c-1af4a7f78989",
  "active": true,
  "metadata": {
    "environment": "production"
  }
}
```

Campos recomendados:

- `id`
- `provider`
- `scope`
- `name`
- `identifier`
- `active`
- `metadata`
- `owner`
- `priority`

Enums sugeridos:

- `provider`: `github`, `railway`, `vercel`, `cloudflare`, `onchain`, `notion`, `manual`
- `scope`: `org`, `project`, `service`, `token`, `repo`, `domain`, `contract`

## Decision

Representa uma interpretacao ou acao proposta a partir
de um ou mais sinais.

Campos minimos:

```json
{
  "id": "decision_2026_04_03_review_mypersonal_service",
  "signal_ids": ["signal_2026_04_03_railway_service_down"],
  "title": "Review production health of mypersonal_multiagents",
  "summary": "Service instability crossed alert threshold and needs inspection.",
  "priority": "high",
  "state": "pending",
  "owner": "human",
  "created_at": "2026-04-03T14:15:00-03:00"
}
```

Campos recomendados:

- `id`
- `signal_ids`
- `title`
- `summary`
- `priority`
- `state`
- `owner`
- `created_at`
- `resolved_at`
- `resolution`
- `links`

Enums sugeridos:

- `priority`: `low`, `medium`, `high`, `critical`
- `state`: `pending`, `approved`, `rejected`, `resolved`
- `owner`: `human`, `agent`, `mixed`

## Diferencas operacionais

`Signal`:

- fato observavel
- nao decide nada por si

`Source`:

- origem permanente ou semi-permanente
- nao e evento

`Decision`:

- interpretacao orientada a acao
- pode consolidar varios sinais

## Persistencia recomendada

Redis:

- cache quente de sinais abertos
- TTL padrao de 24h
- dedupe e estado corrente
- nao e fonte de schema

Sanity:

- registro permanente de `Source`
- registro historico e editorial de `Signal`
- registro governado de `Decision`

## Regras de reconciliacao

- Redis nunca e a fonte permanente de `Decision`
- Redis nao define schema nem semantica
- `Source` nasce canonicamente no Sanity
- `Signal` pode nascer no Redis e ser promovido ao Sanity
- `Decision` deve nascer no Sanity ou ser promovida ao
  Sanity imediatamente quando criada

## Gates antes da implementacao

1. schema aprovado
2. thresholds aprovados
3. `ecosystem.yml` definido
4. politica de TTL definida

## Proxima aplicacao

Primeiro uso deste schema:

- `ecosystem_monitor`
- sinais de GitHub
- sinais de Railway
- sinais de NEOFLW
