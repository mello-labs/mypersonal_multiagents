import {CheckmarkCircleIcon} from '@sanity/icons'

export default {
  name: 'task',
  title: 'Task',
  type: 'document',
  icon: CheckmarkCircleIcon,
  fields: [
    {
      name: 'title',
      title: 'Título',
      type: 'string',
      validation: Rule => Rule.required()
    },
    {
      name: 'status',
      title: 'Status',
      type: 'string',
      options: {
        list: ['A fazer', 'Em progresso', 'Concluído', 'Cancelado'],
        layout: 'radio'
      },
      initialValue: 'A fazer'
    },
    {
      name: 'priority',
      title: 'Prioridade',
      type: 'string',
      options: {
        list: ['Alta', 'Média', 'Baixa'],
        layout: 'radio'
      },
      initialValue: 'Média'
    },
    {
      name: 'project',
      title: 'Projeto',
      type: 'reference',
      to: [{type: 'project'}]
    },
    {
      name: 'area',
      title: 'Área',
      type: 'reference',
      to: [{type: 'area'}]
    },
    {
      name: 'source',
      title: 'Fonte',
      type: 'reference',
      to: [{type: 'source'}]
    },
    {
      name: 'external_id',
      title: 'ID externo',
      type: 'string'
    },
    {
      name: 'scheduled_time',
      title: 'Horário planejado',
      type: 'string'
    },
    {
      name: 'actual_time',
      title: 'Horário real',
      type: 'string'
    },
    {
      name: 'due_date',
      title: 'Data limite',
      type: 'date'
    },
    {
      name: 'visibility',
      title: 'Visibilidade',
      type: 'string',
      options: {
        list: ['private', 'internal', 'public'],
        layout: 'radio'
      },
      initialValue: 'private'
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
      title: 'title',
      status: 'status',
      priority: 'priority'
    },
    prepare({title, status, priority}) {
      return {
        title,
        subtitle: `${status || 'sem status'} · ${priority || 'sem prioridade'}`
      }
    }
  }
}
