import {TagIcon} from '@sanity/icons'

export default {
  name: 'area',
  title: 'Area',
  type: 'document',
  icon: TagIcon,
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
        list: ['active', 'paused', 'archived'],
        layout: 'radio'
      },
      initialValue: 'active'
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
    }
  ],
  preview: {
    select: {
      title: 'name',
      status: 'status'
    }
  }
}
