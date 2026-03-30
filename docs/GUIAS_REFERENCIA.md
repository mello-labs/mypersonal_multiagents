# Guias de Referência Externos

Catálogo inicial de superfícies, runbooks e páginas de operação já existentes fora deste repositório.

Objetivo:

- manter uma fonte única de links úteis
- registrar o contexto de uso de cada guia
- permitir expansão futura para uma base mais estruturada

## Fontes registradas

| ID | Título | Tipo | URL |
|---|---|---|---|
| `neo-dashboard-runbook` | NEØ Operations Runbook | runbook operacional | `https://neo-dashboard-production-2e56.up.railway.app/runbook.html` |
| `neo-dashboard-console` | NΞØ Protocol Control Console | console operacional | `https://neo-dashboard-production-2e56.up.railway.app/` |

## Contextos capturados

### `neo-dashboard-runbook`

- Papel: guia de uso por função
- Superfícies citadas: `Analyzer`, `Control`, `Topology`
- Tese central: uma interface por função; Analyzer decide prioridade, Control executa, Topology contextualiza
- Usos principais:
  - operador: priorização e leitura de fragilidade estrutural
  - DevOps: investigação autenticada, health, logs, runtime e eventos
  - arquitetura: governança da malha e leitura de risco sistêmico
- Regras importantes:
  - não confundir superfície visual com verdade operacional
  - não tratar snapshot como estado live
  - não desproteger API só para facilitar interface

### `neo-dashboard-console`

- Papel: console autenticado de runtime
- Tese central: `Stack Analyzer` é o painel principal; `Control Console` é a camada de controle
- Capacidades percebidas:
  - sinais live
  - logs
  - eventos
  - ações operacionais
  - quick actions como health check, kernel status, report e runbook
- Relação com outras superfícies:
  - `Analyzer`: priorização estrutural
  - `Control`: runtime autenticado
  - `Topology`: inspeção visual da malha

## Próximos registros sugeridos

- outras páginas públicas do mesmo dashboard
- guias equivalentes de operação, deploy, incidentes e arquitetura
- páginas que combinem estado live, snapshot e ação autenticada

## Fonte estruturada

Este documento é a visão humana. A fonte estruturada correspondente está em:

- [GUIAS_REFERENCIA.json](./GUIAS_REFERENCIA.json)
