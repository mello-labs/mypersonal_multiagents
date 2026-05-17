import {DocumentIcon} from '@sanity/icons'

export default {
  name: 'project',
  title: 'Project',
  type: 'document',
  icon: DocumentIcon,
  fields: [
    {
      name: 'name',
      title: 'Nome',
      type: 'string',
      validation: Rule => Rule.required()
    },
    {
      name: 'slug',
      title: 'Slug',
      type: 'slug',
      options: {source: 'name'},
      validation: Rule => Rule.required()
    },
    {
      name: 'summary',
      title: 'Resumo',
      type: 'text',
      rows: 3
    },
    {
      name: 'status',
      title: 'Status',
      type: 'string',
      options: {
        list: ['draft', 'active', 'paused', 'archived'],
        layout: 'radio'
      },
      initialValue: 'active',
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
      name: 'primary_source',
      title: 'Fonte principal',
      type: 'reference',
      to: [{type: 'source'}]
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
      title: 'name',
      status: 'status',
      visibility: 'visibility'
    },
    prepare({title, status, visibility}) {
      return {
        title,
        subtitle: `${status || 'sem status'} · ${visibility || 'sem visibilidade'}`
      }
    }
  }
}
