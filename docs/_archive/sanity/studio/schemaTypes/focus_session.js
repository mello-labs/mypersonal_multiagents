import {ClockIcon} from '@sanity/icons'

export default {
  name: 'focus_session',
  title: 'Focus Session',
  type: 'document',
  icon: ClockIcon,
  fields: [
    {
      name: 'task',
      title: 'Tarefa',
      type: 'reference',
      to: [{type: 'task'}]
    },
    {
      name: 'started_at',
      title: 'Início',
      type: 'datetime',
      validation: Rule => Rule.required()
    },
    {
      name: 'ended_at',
      title: 'Fim',
      type: 'datetime'
    },
    {
      name: 'planned_minutes',
      title: 'Minutos planejados',
      type: 'number'
    },
    {
      name: 'actual_minutes',
      title: 'Minutos reais',
      type: 'number'
    },
    {
      name: 'status',
      title: 'Status',
      type: 'string',
      options: {
        list: ['active', 'completed', 'abandoned', 'canceled'],
        layout: 'radio'
      },
      initialValue: 'active'
    },
    {
      name: 'source',
      title: 'Fonte',
      type: 'reference',
      to: [{type: 'source'}]
    },
    {
      name: 'notes',
      title: 'Notas',
      type: 'text',
      rows: 4
    }
  ],
  preview: {
    select: {
      title: 'task.title',
      status: 'status',
      startedAt: 'started_at'
    },
    prepare({title, status, startedAt}) {
      return {
        title: title || 'Sessão sem tarefa',
        subtitle: `${status || 'sem status'} · ${startedAt || 'sem início'}`
      }
    }
  }
}
