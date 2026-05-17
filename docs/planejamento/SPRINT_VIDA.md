# SPRINT VIDA
## Interrupção Cognitiva e Rotinas Pessoais

**Status:** implementado parcialmente e em operação  
**Data-base:** 30/03/2026  
**Última revisão:** 02/04/2026  
**Prioridade:** P0  

## O problema real

Autismo + hiperfoco distorcem percepção de tempo.
O terminal registra. Mas não interrompe.

O objetivo deste sprint nunca foi "mostrar alertas bonitos".
O objetivo foi criar canais externos ao fluxo cognitivo:

- tela
- voz
- rotina automática

Sem isso, o sistema pensa. Mas não corta a inércia.

## O que continua válido

Estes pilares continuam corretos:

- `core/notifier.py` como camada única de notificação
- `agents/focus_guard.py` como guardião de desvio e escalada
- `agents/life_guard.py` como camada de rotinas pessoais
- escalada por tempo de sessão
- Alexa como canal de voz
- hidratação, refeições e finanças como rotinas observáveis

## O que mudou desde o texto original

O sprint original tratava algumas premissas como universais.
Hoje sabemos que não são.

### 1. `mac_push` não é canal de produção

`mac_push()` depende de `osascript`.
Isso só existe em macOS local.

Conclusão:

- local macOS: suportado
- Railway Linux: não suportado

Se o `focus_guard` rodar no Railway, ele pode até tentar chamar
`mac_push()`, mas isso jamais gera pop-up no Mac.

### 2. Alexa agora usa Voice Monkey

Hoje o desenho correto é usar `VOICE_MONKEY_*`.

### 3. Falha silenciosa deixou de ser aceitável

O protótipo usava `pass` em caso de erro.
Isso servia para não derrubar o agente.

Agora isso virou ruído perigoso.

O sistema precisa distinguir:

- "mensagem foi gerada"
- "tentativa de notificar aconteceu"
- "notificação foi realmente entregue"

## Estado atual dos entregáveis

```text
+---+-----------------------------+---------------------------+------------+
| # | Entregável                  | Arquivo                   | Estado     |
+---+-----------------------------+---------------------------+------------+
| 1 | Mac push via osascript      | core/notifier.py          | parcial    |
| 2 | Escalada no Focus Guard     | agents/focus_guard.py     | ativo      |
| 3 | Alexa via Voice Monkey        | core/notifier.py          | parcial    |
| 4 | Life Guard                  | agents/life_guard.py      | ativo      |
| 5 | Integração no loop          | agents/focus_guard.py     | ativo      |
| 6 | CLI vida/pagar/fiz          | main.py                   | ativo      |
| 7 | Observabilidade de canais   | core/notifier.py          | em avanço  |
+---+-----------------------------+---------------------------+------------+
```

## Contrato por ambiente

Esta seção é a parte que faltava.
Sem ela, o sprint parecia completo quando ainda não era.

### Ambiente local macOS

Suporta:

- `mac_push()`
- `alexa_announce()` via Voice Monkey
- testes manuais de interrupção real

Pré-requisitos:

- `osascript` disponível
- credenciais de Alexa configuradas
- applets ou Voice Monkey válidos

### Ambiente Railway

Suporta:

- geração de alerta
- persistência em Redis
- logs
- chamada HTTP para Voice Monkey

Não suporta:

- notificação nativa do macOS

Conclusão brutal:

Se o `focus_guard` roda no Railway:

- ele pode criar alerta
- ele pode tentar Voice Monkey
- ele nunca vai abrir pop-up no seu Mac

## Implementação atual

### 1. `core/notifier.py`

Hoje concentra:

- `notify()`
- `mac_push()`
- `alexa_announce()`

Contrato atual:

- `mac_push()` é canal local macOS
- `alexa_announce()` tenta Voice Monkey
- se não houver um provider de voice monkey, deve registrar indisponibilidade

### 2. `agents/focus_guard.py`

O `focus_guard` já implementa:

- checagem periódica
- análise de desvio
- escalada por tempo de sessão
- criação de alertas
- integração com `life_guard`

Escalada atual:

```python
ESCALATION_LEVELS = [
    {"minutes": 30,  "channel": "mac",       "sound": False},
    {"minutes": 60,  "channel": "mac",       "sound": True},
    {"minutes": 120, "channel": "mac+alexa", "sound": True},
    {"minutes": 240, "channel": "mac+alexa", "sound": True},
]
```

Essa lógica continua boa.
O que faltava era o contrato de ambiente.

### 3. `agents/life_guard.py`

O `life_guard` já existe e roda dentro do `focus_guard`.

Cobertura atual:

- exercício
- banho
- almoço
- jantar
- hidratação
- contas a pagar

Variáveis atuais:

- `LIFE_GUARD_ACTIVE_HOUR_START`
- `LIFE_GUARD_ACTIVE_HOUR_END`
- `LIFE_GUARD_WATER_INTERVAL`

## Variáveis de ambiente necessárias

### Alexa por Voice Monkey

```bash
VOICE_MONKEY_TOKEN=
VOICE_MONKEY_DEVICE=eco-room
VOICE_MONKEY_VOICE=Ricardo
```


### Life Guard

```bash
LIFE_GUARD_ACTIVE_HOUR_START=8
LIFE_GUARD_ACTIVE_HOUR_END=22
LIFE_GUARD_WATER_INTERVAL=90
```

## Critérios de aceite corretos

Os critérios antigos misturavam local e produção.
Agora ficam separados.

### Local macOS

- `notifier.mac_push("teste", "funciona")` abre pop-up
- `notifier.alexa_announce("teste")` aciona Alexa se houver provider
- sessão de foco com 30 min gera aviso local
- sessão de foco com 2h tenta voz + tela
- `python main.py vida` imprime status
- `python main.py fiz banho` confirma a rotina

### Railway

- o deploy sobe sem erro
- `focus_guard` executa check periódico
- alerta é registrado no Redis
- o log explicita se o canal é incompatível
- Alexa só dispara se houver `VOICE_MONKEY_*`

## O que este sprint ainda não concluiu

O sprint não está morto.
Só ficou mais honesto.

Ainda faltam:

- observabilidade explícita de falha de canal
- teste automatizado de Voice Monkey
- separação formal entre "backend gerou alerta" e
  "usuário recebeu interrupção"
- configuração declarativa de canais via Sanity

## O que deve ir para o Sanity

Não o tutorial inteiro.
Só a camada de governança.

Sanity deve definir:

- níveis de escalada
- mensagem por nível
- canal por nível
- ativação/desativação de canais
- rotinas do `life_guard`
- janelas de horário ativo
- política de fallback

Sanity não deve guardar:


- pseudo-código histórico
- suposições locais como se fossem universais

## Conclusão

O sprint acertou a arquitetura-base.
Errou a metafísica da entrega.

Antes:

- chamou função
- assumiu notificação

Agora:

- canal precisa existir
- ambiente precisa suportar
- credencial precisa estar configurada
- entrega precisa ser observável

Esse é o ponto em que o sistema deixa de parecer vivo
e começa a realmente interromper a realidade.
