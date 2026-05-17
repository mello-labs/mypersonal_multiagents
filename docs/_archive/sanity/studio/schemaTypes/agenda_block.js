import {CalendarIcon} from '@sanity/icons'

export default {
  name: 'agenda_block',
  title: 'Agenda Block',
  type: 'document',
  icon: CalendarIcon,
  fields: [
    {
      name: 'title',
      title: 'Título',
      type: 'string',
      validation: Rule => Rule.required()
    },
    {
      name: 'block_date',
      title: 'Data',
      type: 'date',
      validation: Rule => Rule.required()
    },
    {
      name: 'time_slot',
      title: 'Intervalo',
      type: 'string',
      description: 'Ex.: 11:00-11:30',
      validation: Rule => Rule.required()
    },
    {
      name: 'status',
      title: 'Status',
      type: 'string',
      options: {
        list: ['open', 'completed', 'overdue', 'rescheduled', 'canceled'],
        layout: 'radio'
      },
      initialValue: 'open'
    },
    {
      name: 'task',
      title: 'Tarefa relacionada',
      type: 'reference',
      to: [{type: 'task'}]
    },
    {
      name: 'source',
      title: 'Fonte',
      type: 'reference',
      to: [{type: 'source'}]
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
      blockDate: 'block_date',
      timeSlot: 'time_slot'
    },
    prepare({title, blockDate, timeSlot}) {
      return {
        title,
        subtitle: `${blockDate || '?'} · ${timeSlot || '?'}`
      }
    }
  }
}
