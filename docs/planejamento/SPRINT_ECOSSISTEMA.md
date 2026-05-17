# SPRINT ECOSSISTEMA — Camada Externa do Kernel

**Status:** Reposicionado para implementação disciplinada  
**Prioridade:** P1, após fechar a governança dos agentes íntimos  
**Escopo:** GitHub, Railway, Vercel, on-chain, sinais externos

---

## Tese

Este sprint não existe para criar mais um dashboard.

Ele existe para impedir que NEØ MELLØ precise abrir
6 superfícies diferentes para descobrir o que já
está gritando.

O objetivo não é vigiar tudo.

O objetivo é produzir **sinais acionáveis** sobre o
ecossistema:

- o que está vivo
- o que está degradando
- o que mudou
- o que exige decisão

Sem confundir isso com a camada íntima de foco,
agenda e rotina.

---

## Reposicionamento Arquitetural

O `ecosystem_monitor` não pertence ao núcleo íntimo.

Ele pertence à **órbita externa do kernel**.

Separação correta:

- camada íntima:
  - `focus_guard`
  - `life_guard`
  - `scheduler`
  - `validator`
  - `notion_sync`

- camada externa:
  - `ecosystem_monitor`
  - GitHub
  - Railway
  - Vercel
  - on-chain
  - Cloudflare

Consequência:

- `focus_guard` não deve carregar o peso do
  ecossistema inteiro
- `ecosystem_monitor` deve produzir `signals`,
  `alerts`, `reports` e `decisions_pending`
- a síntese disso pode influenciar o kernel
  privado, mas não nascer misturada a ele

---

## O que este sprint entrega

Um agente de órbita externa que observa o
ecossistema e devolve o que importa em camadas:

1. **health check periódico**
2. **sinais consolidados**
3. **relatório diário**
4. **prioridades externas para decisão**

Formato desejado de saída:

```text
NEØ Ecosystem — 03/04
OK  16 projetos ativos
WARN 1 serviço degradado
FAIL 3 superfícies sem deploy recente

GitHub
- 4 repositórios com atividade nas últimas 24h
- 1 org sem movimento relevante

Infra
- 2 deploys bem-sucedidos
- 1 serviço Railway com comportamento suspeito

On-chain ( nao pedi como extrema urgencia esse check )
- NEOFLW: preço, volume e variação https://neoflw.vercel.app/

Ação sugerida
- revisar smart-nft
- verificar serviço degradado
```

---

## Papel do agente

Arquivo alvo:

- `agents/ecosystem_monitor.py`

Função:

- observar o ecossistema externo
- consolidar sinais
- produzir relatórios
- abrir prioridade de decisão

Não é função dele:

- alterar agenda íntima automaticamente
- publicar algo público sozinho
- virar fonte primária da sua atenção diária

---

## Entradas

Fase 1:

- GitHub REST API
- Railway GraphQL API
- DexScreener

Fase 2:

- Vercel API
- Cloudflare API

Fase 3:

- ENS namespace
- eventos on-chain
- contratos específicos

---

## Saídas

Saídas operacionais:

- `health_check`
- `daily_report`
- `signals`
- `issues`
- `summary`

Saídas semânticas futuras:

- `signal`
- `source`
- `decision`

Saídas públicas:

- nenhuma direta

Tudo público deve passar por:

- Sanity
- `public_artifact`
- revisão humana
- `neo-mello-eth`

---

## Fontes iniciais

### GitHub

Objetivo:

- detectar atividade recente relevante
- commits por org
- issues abertas
- projetos parados

Orgs monitoradas (todas as 6):

- `NEO-PROTOCOL` — orquestrador soberano (Board: projects/1)
- `NEO-FlowOFF` — SaaS de criadores (Board: projects/1)
- `neo-smart-factory` — Web3 / NFT (Board: projects/1)
- `flowpay-system` — pagamentos (Board: pendente)
- `FluxxDAO` — DAO / DeFi (Board: pendente)
- `wodxpro` — protocolo esportivo (Board: pendente)

Mapa completo dos repos e stacks em: `../ecossistema/ECOSSISTEMAS_ORGS.md`

Repos prioritários dentro de `NEO-PROTOCOL`:

| Repo                  | Prioridade | O que observar                          |
| --------------------- | ---------- | --------------------------------------- |
| `neobot`              | P0         | uptime, último commit, webhook health   |
| `neo-dashboard`       | P0         | deploy Railway, health check            |
| `neo-mello-eth`       | P0         | uptime neomello.eth.limo, Redis Railway |
| `mio-system`          | P1         | health da API de identidade             |
| `neoflw-base-landing` | P1         | uptime Vercel                           |
| `.github`             | P2         | PRs e issues da org                     |

Project Board da org:

- `github.com/orgs/NEO-PROTOCOL/projects/1`
- observar: items sem movimento há mais de 7 dias

### Railway

Objetivo:

- status de serviços
- último deploy
- estado de execução

### On-chain

Objetivo:

- monitorar NEOFLW
- preço
- volume
- variação relevante

### Vercel

Objetivo:

- deploys recentes
- falhas
- superfícies sem atualização

### Cloudflare

Objetivo:

- erros 5xx
- disponibilidade de domínio

---

## Modelo operacional correto

Fluxo certo:

```text
APIs externas
  -> ecosystem_monitor
  -> Redis (estado quente)
  -> Sanity (signal/source/decision)
  -> relatório / alertas / priorização
```

Fluxo errado:

```text
APIs externas
  -> focus_guard
  -> notificação direta
  -> caos
```

O monitor deve pousar primeiro em `signal` e
`source`.

Sem isso, ele só produz log bonito.

---

## Dependências arquiteturais

Para sair da Fase 1 e promover sinais ao Sanity,
três coisas precisam estar resolvidas:

1. governança mínima dos agentes no Sanity
2. contrato explícito de precedência entre fontes
3. camada `signal/source/decision` definida

Sem isso, o monitor opera como cache útil,
mas não fecha a ponte semântica.

---

## Variáveis de ambiente

```bash
# GitHub
GITHUB_TOKEN=

# Railway
RAILWAY_TOKEN=

# Vercel
VERCEL_TOKEN=

# Cloudflare
CLOUDFLARE_TOKEN=
CLOUDFLARE_ZONE_ID=
```

Possível expansão futura:

```bash
BASE_RPC_URL=
ETHERSCAN_API_KEY=
```

---

## Fases de implementação

### Fase 1 — Sinais mínimos e úteis

Entram:

- GitHub
- Railway
- DexScreener / NEOFLW

Entregas:

- `python main.py ecosistema`
- `run_health_check()`
- `generate_daily_report()`
- persistência do relatório no Redis

Critério de aceite:

- listar atividade real das orgs
- mostrar status básico de serviços
- mostrar NEOFLW corretamente

Status: implementado no runtime com cache em Redis.

### Fase 2 — Infraestrutura expandida

Entram:

- Vercel
- Cloudflare

Entregas:

- saúde de deploys
- erros 5xx
- mais contexto operacional

Critério de aceite:

- detectar degradação sem abrir os painéis manuais

### Fase 3 — Sinais semânticos

Entram:

- `signal`
- `source`
- `decision`
- prioridade consolidada

Entregas:

- registros no Sanity
- reports com peso semântico
- contexto para decisões

Critério de aceite:

- o sistema distinguir “mudou algo” de “isso
  importa”

### Fase 4 — Publicação filtrada

Entram:

- `public_artifact`
- `neo-mello-eth`
- pipeline público

Entregas:

- recortes públicos do ecossistema
- nenhuma exposição indevida do kernel privado

Critério de aceite:

- só sinais explicitamente promovidos saem para o
  público

---

## Canais de saída

Local:

- terminal
- macOS push

Produção:

- logs estruturados
- Alexa, quando fizer sentido

Futuro:

- web push
- Telegram
- Slack / Discord

Regra:

o relatório diário não precisa nascer como alerta
agressivo.

Ele deve começar como síntese.

Alerta imediato fica só para:

- falha séria
- queda abrupta
- serviço degradado
- evento que pede reação rápida

---

## Critérios de aceite

- [ ] `python main.py ecosistema` imprime um relatório coerente
- [ ] GitHub retorna atividade das orgs relevantes
- [ ] Railway retorna estado dos serviços relevantes
- [ ] NEOFLW retorna preço e volume corretos
- [ ] relatório diário é persistido
- [ ] alertas imediatos só disparam para eventos com peso real
- [ ] nada do monitor publica algo público sozinho

---

## O que não fazer

- não acoplar `ecosystem_monitor` ao loop íntimo
  do `focus_guard`
- não transformar tudo em alerta
- não publicar sinais crus
- não misturar operação pessoal com telemetria
  de ecossistema
- não chamar acúmulo de APIs de arquitetura

---

## Próximo passo correto

Para sair do cache e entrar em semântica:

1. amarrar `signal/source/decision` ao Sanity
2. definir thresholds e dedupe no Studio
3. promover sinais do Redis para Sanity por regra
