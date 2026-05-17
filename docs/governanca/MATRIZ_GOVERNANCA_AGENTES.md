# MATRIZ DE GOVERNANÇA DOS AGENTES

Status: ativo  
Última atualização: 2026-04-03

## Propósito

Este documento existe para responder uma pergunta simples:

"A governança de cada agente já está suficientemente escrita
para o sistema parar de depender de memória humana?"

Resposta curta:

- alguns já estão fortes
- alguns ainda estão parciais
- nenhum deve ser tratado como "autoexplicativo"

## Legenda

- `FORTE`: já tem governança suficiente para operar sem
  improviso estrutural
- `PARCIAL`: existe governança, mas ainda há zonas críticas
  vivendo no código ou em configuração implícita
- `N/A`: a peça não precisa daquele tipo de governança

## Cobertura Atual

| Entidade            |  Usa LLM | agent_config |                   persona | llm_prompt | intervention_script | Cobertura | O que falta                                                                |
| ------------------- | -------: | -----------: | ------------------------: | ---------: | ------------------: | --------- | -------------------------------------------------------------------------- |
| `orchestrator`      |      sim |          sim | usa persona compartilhada |        sim |                 N/A | FORTE     | política de fallback por provider e guardrails de delegação                |
| `focus_guard`       |      sim |          sim |                       N/A |        sim |                 sim | FORTE     | remover fallback local quando o Studio estiver maduro o bastante           |
| `scheduler`         |      sim |          sim |                       N/A |        sim |                 N/A | FORTE     | externalizar parâmetros de carga, pausa e conflito                         |
| `validator`         |      sim |          sim |                       N/A |        sim |                 N/A | FORTE     | externalizar thresholds de consistência e veredicto                        |
| `retrospective`     |      sim |          sim | usa persona compartilhada |        sim |                 N/A | FORTE     | template final e política de exportação                                    |
| `notion_sync`       |      não |          sim |                       N/A |        N/A |                 N/A | PARCIAL   | política explícita de reconciliação e precedência                          |
| `calendar_sync`     |      não |          sim |                       N/A |        N/A |                 N/A | PARCIAL   | política de import/export e precedência do Notion                          |
| `life_guard`        |      não |          sim |                       sim |        N/A |                 N/A | PARCIAL   | scripts de rotina, janelas ativas e canais editáveis                       |
| `ecosystem_monitor` |      não |          sim |                       N/A |        N/A |                 N/A | PARCIAL   | sinal, source, decision e thresholds governados                            |
| `persona_manager`   |      não |          sim |                       sim |        N/A |                 N/A | PARCIAL   | versionamento editorial e política de override por fase                    |
| `gemma_local`       | fallback |          sim |                       sim |        N/A |                 N/A | PARCIAL   | política explícita de quando preferir local por intenção, não só por falha |

## Pacote Mínimo por Entidade

### `orchestrator`

- `agent_config`: sim
- `persona`: indireta, via `persona_manager`
- `llm_prompt`: `routing`, `synthesis`, `direct`
- `intervention_script`: não
- Falta: política explícita de provider e limites de delegação

### `focus_guard`

- `agent_config`: sim
- `persona`: não
- `llm_prompt`: `deviation`
- `intervention_script`: 30, 60, 120, 240 min
- Falta: maturar o Studio para reduzir fallback local

### `scheduler`

- `agent_config`: sim
- `persona`: não
- `llm_prompt`: `scheduling`
- `intervention_script`: não
- Falta: parâmetros de carga, pausas e conflito como dados

### `validator`

- `agent_config`: sim
- `persona`: não
- `llm_prompt`: `validation`
- `intervention_script`: não
- Falta: thresholds de consistência e política de veredicto

### `retrospective`

- `agent_config`: sim
- `persona`: indireta
- `llm_prompt`: `retrospective`
- `intervention_script`: não
- Falta: template final e política de exportação

### `notion_sync`

- `agent_config`: sim
- `persona`: não
- `llm_prompt`: não, por decisão explícita
- `intervention_script`: não
- Falta: reconciliação, precedência e mapeamento de origem

### `calendar_sync`

- `agent_config`: sim
- `persona`: não
- `llm_prompt`: não, por decisão explícita
- `intervention_script`: não
- Falta: política de import/export e operação como capacidade opcional

### `life_guard`

- `agent_config`: sim
- `persona`: sim
- `llm_prompt`: não, por decisão explícita atual
- `intervention_script`: ainda não
- Falta: transformar rotina, canal e janela ativa em governança editável

### `ecosystem_monitor`

- `agent_config`: sim
- `persona`: não
- `llm_prompt`: não
- `intervention_script`: não
- Falta: `signal`, `source`, `decision` no Sanity, thresholds, TTL e dedupe

### `persona_manager`

- `agent_config`: sim
- `persona`: sim
- `llm_prompt`: não
- `intervention_script`: não
- Falta: regras editoriais de override e versionamento leve

### `gemma_local`

- `agent_config`: sim
- `persona`: sim
- `llm_prompt`: não, por decisão explícita atual
- `intervention_script`: não
- Falta: política de ativação por intenção, custo e risco

## Veredito

A base de governança já existe para todos os agentes e
capacidades relevantes.

O que ainda falta não é "ter ou não ter instrução".
O que falta é elevar alguns agentes de governança
`PARCIAL` para governança `FORTE`.

Os cinco pontos que ainda pedem fechamento fino são:

1. `ecosystem_monitor`
2. `notion_sync`
3. `calendar_sync`
4. `life_guard`
5. `gemma_local`

Esse é o conjunto residual. O resto já saiu do terreno
da improvisação.
