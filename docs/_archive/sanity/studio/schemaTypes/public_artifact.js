import {DocumentIcon} from '@sanity/icons'

export default {
  name: 'public_artifact',
  title: 'Public Artifact',
  type: 'document',
  icon: DocumentIcon,
  fields: [
    {
      name: 'title',
      title: 'Título',
      type: 'string',
      validation: Rule => Rule.required()
    },
    {
      name: 'slug',
      title: 'Slug',
      type: 'slug',
      options: {source: 'title'},
      validation: Rule => Rule.required()
    },
    {
      name: 'artifact_type',
      title: 'Tipo',
      type: 'string',
      options: {
        list: ['note', 'report', 'manifesto', 'update', 'page', 'dataset'],
        layout: 'radio'
      },
      initialValue: 'note'
    },
    {
      name: 'status',
      title: 'Status',
      type: 'string',
      options: {
        list: ['draft', 'review', 'approved', 'published', 'archived'],
        layout: 'radio'
      },
      initialValue: 'draft'
    },
    {
      name: 'visibility',
      title: 'Visibilidade',
      type: 'string',
      options: {
        list: ['private', 'internal', 'public'],
        layout: 'radio'
      },
      initialValue: 'public'
    },
    {
      name: 'summary',
      title: 'Resumo',
      type: 'text',
      rows: 3
    },
    {
      name: 'body',
      title: 'Corpo',
      type: 'array',
      of: [{type: 'block'}]
    },
    {
      name: 'source_signals',
      title: 'Signals de origem',
      type: 'array',
      of: [{type: 'reference', to: [{type: 'signal'}]}]
    },
    {
      name: 'source_decisions',
      title: 'Decisions de origem',
      type: 'array',
      of: [{type: 'reference', to: [{type: 'decision'}]}]
    },
    {
      name: 'canonical_url',
      title: 'URL canônica',
      type: 'url'
    },
    {
      name: 'ipfs_cid',
      title: 'IPFS CID',
      type: 'string'
    },
    {
      name: 'published_at',
      title: 'Publicado em',
      type: 'datetime'
    }
  ],
  preview: {
    select: {
      title: 'title',
      status: 'status',
      artifactType: 'artifact_type'
    },
    prepare({title, status, artifactType}) {
      return {
        title,
        subtitle: `${artifactType || 'sem tipo'} · ${status || 'sem status'}`
      }
    }
  }
}
