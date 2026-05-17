# Redis na Railway: checklist simples de 5 minutos

Use este passo a passo 1 vez por semana.

## 1) Abra esta tela

1. Railway > Projeto > serviço `Redis`.
2. Clique na aba `Database`.
3. Clique em `Stats`.

## 2) Veja só 4 números

1. `Connected Clients`:
   Se estiver parecido com o normal (exemplo: 2, 3, 4), está ok.
2. `Evicted Keys`:
   Tem que estar `0`.
3. `Slow Log Entries`:
   Ideal `0`.
4. `Hit Rate`:
   Bom: acima de `85%`.
   Ótimo: acima de `90%`.

## 3) Veja os logs de deploy

1. Clique em `Deploy`.
2. Procure por `BGSAVE done` e `DB saved on disk`.
3. Se só aparece isso, está saudável.
4. Se aparecer `error`, `OOM`, `MISCONF` ou `failed`, é alerta.

## 4) Valide no app (30 segundos)

1. Abra `https://mypersonal-multiagents.up.railway.app/health`.
2. Abra `https://mypersonal-multiagents.up.railway.app/status`.
3. Se ambos responderem normal, front e Redis estão conversando.

## 5) O que não fazer sem combinar antes

1. Não clicar em limpar tudo.
2. Não rodar `FLUSHDB` ou `FLUSHALL`.
3. Não apagar chaves em massa.

## Regra de decisão rápida

1. `Evicted Keys > 0` ou `Slow Log Entries` subindo:
   abrir investigação.
2. Sem erros e com `BGSAVE done`:
   manter como está.
