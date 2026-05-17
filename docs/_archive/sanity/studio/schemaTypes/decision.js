import {DocumentIcon} from '@sanity/icons'

export default {
  name: 'decision',
  title: 'Decision',
  type: 'document',
  icon: DocumentIcon,
  fields: [
    {
      name: 'id',
      title: 'ID',
      type: 'slug',
      options: {source: 'title'},
      validation: Rule => Rule.required()
    },
    {
      name: 'signal_ids',
      title: 'Signals',
      type: 'array',
      of: [{type: 'reference', to: [{type: 'signal'}]}]
    },
    {
      name: 'title',
      title: 'Título',
      type: 'string',
      validation: Rule => Rule.required()
    },
    {
      name: 'summary',
      title: 'Resumo',
      type: 'text',
      rows: 4,
      validation: Rule => Rule.required()
    },
    {
      name: 'priority',
      title: 'Prioridade',
      type: 'string',
      options: {
        list: ['low', 'medium', 'high', 'critical'],
        layout: 'radio'
      },
      initialValue: 'medium'
    },
    {
      name: 'state',
      title: 'Estado',
      type: 'string',
      options: {
        list: ['pending', 'approved', 'rejected', 'resolved'],
        layout: 'radio'
      },
      initialValue: 'pending'
    },
    {
      name: 'owner',
      title: 'Owner',
      type: 'string',
      options: {
        list: ['human', 'agent', 'mixed'],
        layout: 'radio'
      },
      initialValue: 'human'
    },
    {
      name: 'created_at',
      title: 'Criada em',
      type: 'datetime',
      validation: Rule => Rule.required()
    },
    {
      name: 'resolved_at',
      title: 'Resolvida em',
      type: 'datetime'
    },
    {
      name: 'resolution',
      title: 'Resolução',
      type: 'text',
      rows: 4
    },
    {
      name: 'links',
      title: 'Links',
      type: 'array',
      of: [{
        type: 'object',
        fields: [
          {name: 'label', title: 'Rótulo', type: 'string'},
          {name: 'url', title: 'URL', type: 'url'}
        ]
      }]
    }
  ],
  preview: {
    select: {
      title: 'title',
      priority: 'priority',
      state: 'state'
    },
    prepare({title, priority, state}) {
      return {
        title,
        subtitle: `${priority || 'sem prioridade'} · ${state || 'sem estado'}`
      }
    }
  }
}
