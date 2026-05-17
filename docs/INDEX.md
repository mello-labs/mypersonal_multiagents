# DOCS INDEX

Status: ativo  
Ultima atualizacao: 2026-04-03

## Objetivo

Este indice e a porta de entrada unica da documentacao.
Se um agente ou humano nao souber por onde comecar, comeca aqui.

## Estrutura por tipo

- `governanca/`
  - [CONTRATO_AGENTES.md](./governanca/CONTRATO_AGENTES.md)
  - [MATRIZ_GOVERNANCA_AGENTES.md](./governanca/MATRIZ_GOVERNANCA_AGENTES.md)
  - [PLANO_SOBERANIA_SANITY.md](./governanca/PLANO_SOBERANIA_SANITY.md)
  - [POLITICA_PRECEDENCIA_NOTION.md](./governanca/POLITICA_PRECEDENCIA_NOTION.md)
- `arquitetura/`
  - [SCHEMA_SIGNAL_DECISION.md](./arquitetura/SCHEMA_SIGNAL_DECISION.md)
  - [SANITY_SCHEMA.md](./arquitetura/SANITY_SCHEMA.md)
- `operacao/`
  - [MANUAL_USUARIO.md](./operacao/MANUAL_USUARIO.md)
  - [MANUAL_DEV.md](./operacao/MANUAL_DEV.md)
  - [redis-weekly-check.md](./operacao/redis-weekly-check.md)
- `planejamento/`
  - [NEXTSTEPS.md](./planejamento/NEXTSTEPS.md)
  - [SPRINT_VIDA.md](./planejamento/SPRINT_VIDA.md)
  - [SPRINT_ECOSSISTEMA.md](./planejamento/SPRINT_ECOSSISTEMA.md)
- `ecossistema/`
  - [ECOSSISTEMA_NEO_PROTOCOL.md](./ecossistema/ECOSSISTEMA_NEO_PROTOCOL.md)
  - [ECOSSISTEMAS_ORGS.md](./ecossistema/ECOSSISTEMAS_ORGS.md)
  - [GUIAS_REFERENCIA.md](./ecossistema/GUIAS_REFERENCIA.md)
- `auditoria/`
  - [AUDITORIA_AGENTES.md](./auditoria/AUDITORIA_AGENTES.md)

## Ordem de verdade

Quando houver conflito entre documentos, usar esta precedencia:

1. `docs/governanca/CONTRATO_AGENTES.md`
2. `docs/governanca/MATRIZ_GOVERNANCA_AGENTES.md`
3. Runtime no codigo
4. Planejamentos historicos

## Leitura rapida por intencao

- "Como o sistema deve operar":
  - `governanca/CONTRATO_AGENTES.md`
  - `governanca/POLITICA_PRECEDENCIA_NOTION.md`
- "O que falta fazer":
  - `planejamento/NEXTSTEPS.md`
- "Como esta modelado":
  - `arquitetura/SCHEMA_SIGNAL_DECISION.md`
  - `governanca/PLANO_SOBERANIA_SANITY.md`
- "Como usar no dia a dia":
  - `operacao/MANUAL_USUARIO.md`
  - `operacao/redis-weekly-check.md`

## Regras de higiene documental

- Novo `.md` precisa entrar na subpasta correta.
- Novo `.md` precisa ser adicionado neste indice.
- Evitar criar documento no `docs/` raiz.
- `docs/` raiz fica reservado para o indice e artefatos estruturados (`.json`).
