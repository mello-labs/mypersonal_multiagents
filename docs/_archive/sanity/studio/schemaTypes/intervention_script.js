export default {
  name: 'intervention_script',
  title: 'Script de Intervenção',
  type: 'document',
  description: 'Mensagens enviadas quando hiperfoco prolongado é detectado',
  fields: [
    {
      name: 'agent_name',
      title: 'Agente',
      type: 'string',
      options: {
        list: ['focus_guard', 'life_guard', 'orchestrator'],
      },
      initialValue: 'focus_guard',
      validation: (Rule) => Rule.required(),
    },
    {
      name: 'trigger_minutes',
      title: 'Disparar após (minutos)',
      type: 'number',
      description: 'Minutos de sessão ativa para disparar',
      validation: (Rule) => Rule.required().min(1),
    },
    {
      name: 'channel',
      title: 'Canal',
      type: 'string',
      options: {
        list: [
          {title: 'Mac', value: 'mac'},
          {title: 'Alexa', value: 'alexa'},
          {title: 'Mac + Alexa', value: 'mac+alexa'},
          {title: 'Somente log', value: 'log_only'},
        ],
      },
      validation: (Rule) => Rule.required(),
    },
    {
      name: 'environment_scope',
      title: 'Ambiente',
      type: 'string',
      options: {
        list: [
          {title: 'Ambos', value: 'all'},
          {title: 'Local macOS', value: 'local'},
          {title: 'Servidor / Railway', value: 'server'},
        ],
        layout: 'radio',
      },
      initialValue: 'all',
    },
    {
      name: 'urgency',
      title: 'Urgência',
      type: 'string',
      options: {list: ['gentle', 'firm', 'loud']},
    },
    {
      name: 'sound',
      title: 'Som',
      type: 'boolean',
      initialValue: false,
    },
    {
      name: 'title',
      title: 'Título (Mac push)',
      type: 'string',
    },
    {
      name: 'message',
      title: 'Mensagem',
      type: 'text',
      rows: 3,
      description: 'Use {task}, {minutes} e {planned} para interpolação',
      validation: (Rule) => Rule.required(),
    },
    {
      name: 'provider_preference',
      title: 'Provider preferido',
      type: 'string',
      options: {
        list: [
          {title: 'Auto', value: 'auto'},
          {title: 'Voice Monkey', value: 'voice_monkey'},
          {title: 'IFTTT', value: 'ifttt'},
          {title: 'Somente log', value: 'log_only'},
        ],
        layout: 'radio',
      },
      initialValue: 'auto',
    },
    {
      name: 'active',
      title: 'Ativo',
      type: 'boolean',
      initialValue: true,
    },
  ],
  orderings: [
    {
      title: 'Por tempo (crescente)',
      name: 'triggerAsc',
      by: [{field: 'trigger_minutes', direction: 'asc'}],
    },
  ],
  preview: {
    select: {
      agent: 'agent_name',
      minutes: 'trigger_minutes',
      channel: 'channel',
      scope: 'environment_scope',
    },
    prepare({agent, minutes, channel, scope}) {
      const channelLabels = {
        mac: 'Mac',
        alexa: 'Alexa',
        'mac+alexa': 'Mac + Alexa',
        log_only: 'Somente log',
      }
      const scopeLabels = {
        all: 'Ambos',
        local: 'Local macOS',
        server: 'Servidor / Railway',
      }
      const channelLabel = channelLabels[channel] || channel || 'canal'
      const scopeLabel = scope ? scopeLabels[scope] || scope : ''
      return {
        title: `${agent || 'agent'} · ${minutes} min`,
        subtitle: `${channelLabel}${scopeLabel ? ` · ${scopeLabel}` : ''}`,
      }
    },
  },
}
