# ECOSSISTEMA NEO-PROTOCOL

Status: ativo
Última atualização: 2026-04-06

## Propósito

Este documento mapeia o ecossistema externo que NEØ MELLØ
gerencia como responsabilidade pessoal.

Manter e evoluir a org NEO-PROTOCOL é uma tarefa real —
não um projeto separado do OS pessoal.

O `ecosystem_monitor` precisa deste mapa para saber
o que monitorar, quais sinais coletar e quais decisões
escalar para revisão humana.

---

## Identidade pública

| Superfície | URL | Papel |
| --- | --- | --- |
| Identidade ENS | `neomello.eth.limo` | Perfil público, exposição de projetos e ideias |
| Org GitHub | `github.com/NEO-PROTOCOL` | Organização técnica, repos e roadmap |
| Dashboard | `mypersonal-multiagents.up.railway.app` | Console de controle operacional |
| Token | NEOFLW · Base Mainnet | `0x41F4ff3d45DED9C1332e4908F637B75fe83F5d6B` |

---

## Repositórios da org NEO-PROTOCOL

### `neo-dashboard`

- `github.com/NEO-PROTOCOL/neo-dashboard`
- **O que é:** Console de controle operacional. Interface "Analyzer /
  Control / Topology". Superfície primária de leitura de sinais e
  estado do ecossistema.
- **Deploy:** `mypersonal-multiagents.up.railway.app`
- **Monitorar:** uptime, último deploy, health check

### `neo-mello-eth`

- `github.com/NEO-PROTOCOL/neo-mello-eth`
- **O que é:** Site público de identidade de NEØ MELLØ.
  Canal de exposição de ideias, projetos e artefatos públicos.
  Porta de saída do fluxo privado → público do OS pessoal.
- **Deploy:** `neomello.eth.limo` / `neomelloeth.up.railway.app`
- **Redis:** `redis-neomello.up.railway.app` (Railway)
- **Monitorar:** uptime, último deploy, health do Redis Railway

### `mio-system`

- `github.com/NEO-PROTOCOL/mio-system`
- **O que é:** Camada de identidade Web3. Gerencia as 9 identidades
  MIO (mio-core, mio-warrior, mio-factory, mio-gateway...).
  Autenticação e registro soberano de identidades.
- **Stack:** Node.js / Express / Web3 / ethers.js
- **Monitorar:** health da API, status das identidades

### `neoflw-base-landing`

- `github.com/NEO-PROTOCOL/neoflw-base-landing`
- **O que é:** Landing page do token NEOFLW (Base Mainnet).
  Site estático de verificação e informação do token.
- **Deploy:** Vercel / `neoflowoff.eth.limo`
- **Monitorar:** uptime, contrato on-chain

### `.github`

- **O que é:** Perfil da org, arquitetura, diretivas e definições
  críticas do protocolo. Documentação central da org.
- **Monitorar:** PRs e issues abertas

---

## Roadmap da org

**Fonte canônica:** `github.com/orgs/NEO-PROTOCOL/projects/1`

Fases identificadas via `ecosystem.json` do neobot:

### Fase 1 — Operacional (🟢)

- Neobot Orchestrator (nó soberano) — ATIVO
- MIO System (camada de identidade) — ATIVO
- NEO Nexus (event hub/relay) — ATIVO no Railway
- NEO Agent Full (WhatsApp/Telegram) — ATIVO no Railway
- Lighthouse Storage (IPFS pinning) — ATIVO

### Fase 2 — Configuração pendente (🟡)

- Neo Dashboard (console de controle) — deploy ok, requer config
- Smart Factory Hub (Web3 engineering) — integração ativa
- WhatsApp Channel Automation — setup necessário
- Notion Sync para lead reporting — em desenvolvimento

### Fase 3 — Roadmap futuro (🔵)

- Kwil DB (memória descentralizada) — planejado
- Storacha/Ceramic (storage soberano) — planejado
- Camada de governança distribuída — planejado

---

## Conexões críticas da org

| Conexão | Status | Risco se quebrar |
| --- | --- | --- |
| Nexus ↔ Neobot | VITAL | perda de trilha de auditoria |
| Agent Full ↔ Nexus | VITAL | alucinação sistêmica dos agentes |
| FlowPay ↔ Nexus | VITAL | paralisia financeira |
| WhatsApp ↔ wacli | EM CONFIG | automação de PIX/faturas falha |

---

## Relação com o OS pessoal

```text
mypersonal_multiagents (kernel íntimo)
    ↓ tarefas pessoais de manutenção
NEO-PROTOCOL org (ecossistema externo)
    ├── neobot          ← orquestrador técnico
    ├── mio-system      ← identidade Web3
    ├── neo-dashboard   ← superfície de controle
    ├── neo-mello-eth   ← identidade pública
    └── neoflw-base-landing ← token
    ↓ artefatos aprovados
neomello.eth.limo (publicação pública via eclusa Sanity)
```

O OS pessoal é o kernel cognitivo.
A org NEO-PROTOCOL é o ecossistema técnico externo.
`neo-mello-eth` é o canal de saída público.

---

## O que o `ecosystem_monitor` deve observar

### GitHub

- PRs abertas em repos da org
- Issues abertas por prioridade
- Último commit por repo (detectar repos estagnados)
- Status do Project Board `projects/1`

### Railway

- Uptime de `neo-dashboard` (serviço `neo-mello-eth` + Redis)
- Último deploy de cada serviço
- Health check dos endpoints

### On-chain

- Contrato NEOFLW: `0x41F4ff3d45DED9C1332e4908F637B75fe83F5d6B` (Base)
- Holders, volume, última transação relevante

### ENS / Domínios

- `neomello.eth.limo` resolvendo corretamente
- `neoprotocol.space` ativo
- `neoflowoff.eth.limo` ativo

---

## Política de manutenção

- Tarefas de manutenção da org entram no Notion TASKS
  como qualquer outra tarefa pessoal
- Issues críticas da org viram `signal` no `ecosystem_monitor`
- Nenhuma decisão técnica da org vai diretamente para
  `neo-mello-eth` sem passar pela eclusa Sanity → `public_artifact`
- O GitHub Projects roadmap é a fonte de verdade do
  planejamento da org — não substituir por Redis ou Notion

---

## Acesso rápido

| Recurso | URL |
| --- | --- |
| Org GitHub | `github.com/NEO-PROTOCOL` |
| Project Board | `github.com/orgs/NEO-PROTOCOL/projects/1` |
| Dashboard | `mypersonal-multiagents.up.railway.app` |
| Identidade pública | `neomello.eth.limo` |
| Railway (neo-mello-eth) | `neomelloeth.up.railway.app` |
| Token Basescan | `basescan.org/token/0x41F4ff3d45DED9C1332e4908F637B75fe83F5d6B` |
