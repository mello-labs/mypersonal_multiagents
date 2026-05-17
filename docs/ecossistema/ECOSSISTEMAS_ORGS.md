# ECOSSISTEMAS — Todas as Orgs GitHub

Status: ativo
Última atualização: 2026-04-03

## Propósito

Mapa de todas as organizações GitHub gerenciadas por NEØ MELLØ
como responsabilidade pessoal.

Cada org tem repositórios, stack, estado de roadmap e o que
o `ecosystem_monitor` deve observar.

---

## Inventário de Orgs

| Org | Project Board | Repos | Foco |
|---|---|---|---|
| `NEO-PROTOCOL` | ✅ `projects/1` | 6+ | Orquestrador soberano, identidade pública, token |
| `NEO-FlowOFF` | ✅ `projects/1` "Unified Roadmap" M0–M13 | 17 | Automação e crescimento, token utility |
| `neo-smart-factory` | ✅ `projects/1` "Unified Roadmap 2026" | 8 | Contratos inteligentes, NFT, CLI tooling |
| `flowpay-system` | ✅ `projects/2` "FlowPay Roadmap" | 9 | Gateway de liquidação on NEO Protocol |
| `FluxxDAO` | ✅ `projects/1` "FluxxDAO Roadmap" | 3 | DAO / DeFi |
| `wodxpro` | ✅ `projects/1` "WODXPRO Roadmap" | 4 | Protocolo esportivo Web3 |

---

## NEO-PROTOCOL

**URL:** `github.com/NEO-PROTOCOL`
**Project Board:** `github.com/orgs/NEO-PROTOCOL/projects/1`
**Foco:** Orquestrador soberano do ecossistema pessoal de NEØ MELLØ

Documentação completa: `ECOSSISTEMA_NEO_PROTOCOL.md`

### Repos principais

| Repo | Stack | Deploy | Prioridade |
|---|---|---|---|
| `neobot` | TypeScript / Node.js | Railway + local macOS | P0 |
| `neo-dashboard` | (control console) | Railway | P0 |
| `neo-mello-eth` | (identidade pública) | Railway + Redis | P0 |
| `mio-system` | Node.js / Web3 | Railway | P1 |
| `neoflw-base-landing` | (landing token) | Vercel | P1 |
| `.github` | (docs org) | — | P2 |

### O que monitorar

- uptime neobot, webhook health
- neo-dashboard: último deploy, health check
- neo-mello-eth: Redis Railway ativo
- NEOFLW: preço, volume, variação on-chain
- Project Board: items sem movimento > 7 dias

---

## NEO-FlowOFF

**URL:** `github.com/NEO-FlowOFF`
**Project Board:** ✅ `github.com/orgs/NEO-FlowOFF/projects/1` — "NEO-FlowOFF Unified Roadmap"
**Foco:** Plataforma de automação e crescimento baseado em protocolo — aquisição de usuários, token utility, funil de conversão
**Repos:** 17 (4 públicos, 13 privados)
**Stack:** Python (backend), TypeScript / Astro (frontend), PWA

### Roadmap — 14 milestones M0–M13

| Milestone | Status |
|---|---|
| M0 — MVP Bootstrapping | Em progresso |
| M1 — Token path | Crítico |
| M2 — On-chain readiness | Crítico |
| M3–M9 — Produto, wallet, conversão | Fila |
| M10–M13 — Launch, automação, analytics | Planejado |

### Repos principais (públicos)

| Repo | Observações |
|---|---|
| `neo-control-plane` | Python — painel de controle central |
| `neo-flw-landing` | Landing principal |
| `neo-landing-open` | Landing open/público |
| `ceo-escalavel-miniapp` | Miniapp |

### O que monitorar

- M2 on-chain readiness: bloqueador do caminho crítico
- neo-control-plane: health da API Python
- Conversão de landing pages
- Velocidade do roadmap (14 milestones sequenciais)

---

## neo-smart-factory

**URL:** `github.com/neo-smart-factory`
**Project Board:** ✅ `github.com/orgs/neo-smart-factory/projects/1` — "Unified Roadmap 2026"
**Foco:** Contratos inteligentes, NFT, CLI e tooling Web3 para o protocolo NEO
**Membros:** 3
**Board:** ativo com 6 workflows, itens rastreados até Mai 2026

### Repos mapeados

| Repo | Lang | Visib | Observações |
|---|---|---|---|
| `smart-core` | JavaScript | público | Contratos e deployment scripts |
| `smart-ui` | JavaScript | público | PWA e landing page |
| `internal-ops` | JavaScript | privado | CI/CD e automações |
| `smart-ui-mobile` | JavaScript | privado | Telegram miniapp |
| `docs` | JavaScript | privado | Documentação da plataforma |
| `smart-nft` | JavaScript | privado | NFT Manager com IPFS |
| `smart-cli` | JavaScript | privado | CLI `nxf` universal |
| `smart-ui-landing` | Shell | privado | Landing + infraestrutura |

### O que monitorar

- `smart-nft`: atividade on-chain, contratos implantados
- `smart-cli`: último release (mais lento — fev/2026)
- `smart-core`: últimos commits de contrato
- Board "Unified Roadmap 2026": velocity e blockers

---

## flowpay-system

**URL:** `github.com/flowpay-system`
**Project Board:** ✅ `github.com/orgs/flowpay-system/projects/2` — "FlowPay Roadmap" (criado 2026-04-03)
**Foco:** Gateway de liquidação descentralizado sobre o NEØ Protocol — processamento autônomo de transações
**Repos:** 9 (2 públicos, 7 privados)
**Stack:** JavaScript, Cloudflare Workers, D1 Database, NEØ Protocol

### O que o sistema faz

- Settlement gateway em tempo real (SLA p95 < 5s)
- KYC: validação CPF/CNPJ
- Dashboard de vendedor
- Provider abstraction layer
- Proof-of-execution anchoring on-chain
- SWIE (Sign-In With Ethereum) para autenticação

### Repos mapeados

| Repo | Lang | Visib | Observações |
|---|---|---|---|
| `flowpay-app` | CSS / JS | privado | Frontend principal (seller dashboard) |
| `flowpay-api` | JavaScript | privado | API + Cloudflare Workers + D1 |
| `flowpay-marketing` | Astro | privado | Site de marketing |
| `flowpay-infra` | Shell | privado | Scripts de infra |
| `flowpay-docs` | — | privado | Documentação interna |
| `flowpay-docs-page` | — | público | Documentação pública |
| `flowpay-system-workspace` | JavaScript | privado | Monorepo workspace |
| `.github` | — | público | Perfil da org |

### O que monitorar

- flowpay-api: latência de settlement, uptime (Cloudflare Workers)
- KYC validation pipeline: taxa de sucesso
- Transações: success rate > 99.5%
- Project Board: criar e ativar (pendente)

---

## FluxxDAO

**URL:** `github.com/FluxxDAO`
**Project Board:** ✅ `github.com/orgs/FluxxDAO/projects/1` — "FluxxDAO Roadmap" (criado 2026-04-03)
**Foco:** Governança e DeFi — "Assinamos com presença, não com papel"
**Membros:** 2 (neomello, fluxx-dao)
**Domínio:** `fluxx.space`

### Repos mapeados (todos privados)

| Repo | Lang | Último commit | Observações |
|---|---|---|---|
| `fluxxdao-workspace` | JavaScript | Mar 22, 2026 | Monorepo workspace e config compartilhada |
| `fluxx-backend` | JavaScript | Mar 3, 2026 | API e lógica de negócio core |
| `fluxx-landing` | JavaScript | Mar 3, 2026 | Landing page — `fluxx.space` |

### O que monitorar

- fluxx-landing: uptime em `fluxx.space`
- fluxx-backend: health da API
- Project Board: criar e ativar (pendente)

---

## wodxpro

**URL:** `github.com/wodxpro`
**Project Board:** ✅ `github.com/orgs/wodxpro/projects/1` — "WODXPRO Roadmap" (criado 2026-04-03)
**Foco:** Registros verificáveis de atividade fitness on-chain
**Membros:** 2 (neomello, wodxproject)

### Repos mapeados

| Repo | Lang | Visib | Último commit | Observações |
|---|---|---|---|---|
| `wod-protocol` | — | privado | Mar 3, 2026 | Core do protocolo |
| `wod-eth` | TypeScript | privado | Mar 3, 2026 | Camada Ethereum/EVM |
| `wod-x-pro` | TypeScript | privado | Mar 3, 2026 | Aplicação principal |
| `wod-landing` | CSS | público | Fev 24, 2026 | Site público |

### O que monitorar

- wod-landing: uptime (único repo público)
- wod-eth: atividade on-chain / smart contract interactions
- wod-protocol: estabilidade de implementação
- Project Board: criar e ativar (pendente)

---

## Política de manutenção (todas as orgs)

- Issues críticas de qualquer org viram `signal` no `ecosystem_monitor`
- Repos sem atividade há mais de 14 dias são sinalizados como estagnados
- Project Boards são a fonte de verdade de roadmap — não substituir por Redis
- Nenhuma decisão técnica de nenhuma org vai para `neo-mello-eth` sem eclusa Sanity
- Tarefas de manutenção de org entram no Notion TASKS como qualquer tarefa pessoal

---

## Acesso rápido

| Recurso | URL |
|---|---|
| NEO-PROTOCOL | `github.com/NEO-PROTOCOL` |
| NEO-PROTOCOL Board | `github.com/orgs/NEO-PROTOCOL/projects/1` |
| NEO-FlowOFF | `github.com/NEO-FlowOFF` |
| NEO-FlowOFF Board | `github.com/orgs/NEO-FlowOFF/projects/1` |
| neo-smart-factory | `github.com/neo-smart-factory` |
| neo-smart-factory Board | `github.com/orgs/neo-smart-factory/projects/1` |
| flowpay-system | `github.com/flowpay-system` |
| flowpay-system Board | `github.com/orgs/flowpay-system/projects/2` |
| FluxxDAO | `github.com/FluxxDAO` |
| FluxxDAO Board | `github.com/orgs/FluxxDAO/projects/1` |
| wodxpro | `github.com/wodxpro` |
| wodxpro Board | `github.com/orgs/wodxpro/projects/1` |
| Dashboard NEØ | `dashboard.neoprotocol.space` |
| Identidade pública | `neomello.eth.limo` |
| Token NEOFLW | `basescan.org/token/0x41F4ff3d45DED9C1332e4908F637B75fe83F5d6B` |
