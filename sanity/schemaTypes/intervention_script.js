export default {
  name: 'intervention_script',
  title: 'Script de Intervenção',
  type: 'document',
  description: 'Mensagens enviadas quando hiperfoco prolongado é detectado',
  fields: [
    {
      name: 'trigger_minutes',
      title: 'Disparar após (minutos)',
      type: 'number',
      description: 'Minutos de sessão ativa para disparar',
      validation: Rule => Rule.required().min(1)
    },
    {
      name: 'channel',
      title: 'Canal',
      type: 'string',
      options: { list: ['mac', 'alexa', 'mac+alexa'] },
      validation: Rule => Rule.required()
    },
    {
      name: 'urgency',
      title: 'Urgência',
      type: 'string',
      options: { list: ['gentle', 'firm', 'loud'] }
    },
    {
      name: 'sound',
      title: 'Som',
      type: 'boolean',
      initialValue: false
    },
    {
      name: 'title',
      title: 'Título (Mac push)',
      type: 'string'
    },
    {
      name: 'message',
      title: 'Mensagem',
      type: 'text',
      rows: 3,
      description: 'Use {task} para nome da tarefa, {minutes} para tempo decorrido',
      validation: Rule => Rule.required()
    },
    {
      name: 'active',
      title: 'Ativo',
      type: 'boolean',
      initialValue: true
    }
  ],
  orderings: [
    {
      title: 'Por tempo (crescente)',
      name: 'triggerAsc',
      by: [{ field: 'trigger_minutes', direction: 'asc' }]
    }
  ],
  preview: {
    select: { title: 'trigger_minutes', subtitle: 'channel' },
    prepare({ title, subtitle }) {
      return { title: `${title} min`, subtitle }
    }
  }
}
