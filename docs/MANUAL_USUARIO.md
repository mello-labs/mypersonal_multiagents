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
- Importe blocos do **Notion** ou **Google Calendar** no intervalo selecionado
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

## Notificacoes

O app esta preparado para push notifications. Quando ativadas, voce recebera alertas de:

- Proximo compromisso em 15 min / 5 min
- Bloco atrasado
- Reagendamento automatico
- Resumo diario

(Funcionalidade de push sera ativada em versao futura via Telegram ou Web Push)

## Dicas

- O app funciona offline para navegacao basica (cache do service worker)
- Para forcar atualizacao, puxe a pagina para baixo ou toque **Atualizar** nos cards
- Se o app parecer desatualizado apos deploy, limpe o cache do navegador
