# Manual do Usuario — Multiagentes PWA

## O que e

App mobile (PWA) para gerenciar seu sistema de agentes pessoais. Controla tarefas, agenda, foco e comunicacao com o orchestrator — tudo pelo celular.

## Instalar no celular

### iPhone (Safari)
1. Abra o endereco do app no Safari (ex: `https://seu-dominio.railway.app`)
2. Toque no botao de compartilhar (quadrado com seta para cima)
3. Role para baixo e toque em **Adicionar a Tela de Inicio**
4. Confirme o nome e toque em **Adicionar**
5. O app aparece como icone na home screen e abre em tela cheia

### Android (Chrome)
1. Abra o endereco no Chrome
2. Toque no menu (tres pontos) no canto superior direito
3. Toque em **Instalar app** ou **Adicionar a tela inicial**
4. Confirme

## Navegacao

O app tem 5 abas na parte inferior:

| Aba | Funcao |
|-----|--------|
| **Home** | Dashboard com metricas, agenda do dia e tarefas |
| **Agenda** | Historico de blocos com filtro por data e importacao |
| **Tarefas** | Criar e gerenciar tarefas com prioridade |
| **Chat** | Conversar com o orchestrator (IA) |
| **Audit** | Eventos do sistema, alertas, handoffs e logs |

## Home

- Mostra greeting contextual (Bom dia / Boa tarde / Boa noite)
- 4 cards de metricas: tarefas a fazer, blocos da agenda, status do foco, alertas pendentes
- Card de **Agenda hoje** com blocos do dia — toque no check para marcar como concluido
- Card de **Tarefas** com link para ver todas

## Agenda

- Filtre por intervalo de datas usando os campos de data e o botao **Filtrar**
- Importe blocos do **Notion** como fonte principal ou do **Google Calendar** como fonte opcional no intervalo selecionado
- Cada bloco mostra status: aberto, concluido ou reagendado

## Tarefas

- Digite o titulo, escolha prioridade (! = Alta, losango = Media, losango vazio = Baixa)
- Toque **+** para criar
- Toque no circulo com check para marcar como concluida
- Prioridade alta aparece com ponto vermelho, media com amarelo, baixa com cinza

## Chat

- Converse com o orchestrator em linguagem natural
- Pergunte sobre status, peca para reagendar, crie tarefas por texto
- O chat mantem historico da sessao (ate 12 turnos)

## Audit

- **Badge vermelho** na aba indica alertas pendentes
- Veja eventos de auditoria (checks do Focus Guard, reagendamentos)
- Historico de alertas gerados pelo sistema
- Handoffs entre agentes
- Log bruto do sistema

## Sync

- O botao **Sync** no header sincroniza tarefas com o Notion
- Aparece um toast verde confirmando quantas tarefas foram sincronizadas

## Header

- **Guard** com ponto verde = Focus Guard ativo e monitorando
- **Guard** com ponto vermelho = Focus Guard desligado
- Relogio atualizado automaticamente

## Life Guard — Rotinas Pessoais

O sistema monitora rotinas diarias automaticamente via Focus Guard:

| Rotina | Horario | Canal |
|--------|---------|-------|
| Exercicio | 07:00 | Mac push |
| Banho | 10:00 | Mac push |
| Almoco | 12:30 | Mac push + Alexa |
| Jantar | 19:30 | Mac push |
| Agua | cada 90 min (8h-22h) | Mac push |

Para confirmar uma rotina feita: `python main.py fiz banho` (ou exercicio, almoco, jantar).

Para ver status do dia: `python main.py vida`.

Para registrar conta a pagar: `python main.py pagar Cartao XP dia 15 valor 1200` — alerta 3 dias antes do vencimento.

## Notificacoes

O sistema envia notificacoes ativas via:

- **macOS push** — pop-up no canto da tela (osascript)
- **Alexa** — anuncio por voz via Voice Monkey

Alertas automaticos:

- Sessao de foco ha 30 min → mac push
- Sessao de foco ha 1 hora → mac push com som
- Sessao de foco ha 2 horas → mac push + Alexa
- Sessao de foco ha 4 horas → mac push + Alexa ("sai do computador")
- Rotinas diarias nos horarios configurados
- Financas proximas do vencimento

(Web Push e Telegram planejados para versao futura)

## Dicas

- O app funciona offline para navegacao basica (cache do service worker)
- Para forcar atualizacao, puxe a pagina para baixo ou toque **Atualizar** nos cards
- Se o app parecer desatualizado apos deploy, limpe o cache do navegador
