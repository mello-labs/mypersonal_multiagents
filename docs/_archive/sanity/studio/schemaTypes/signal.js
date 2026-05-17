import {DocumentIcon} from '@sanity/icons'

export default {
  name: 'signal',
  title: 'Signal',
  type: 'document',
  icon: DocumentIcon,
  fields: [
    {
      name: 'id',
      title: 'ID',
      type: 'slug',
      options: {source: 'message'},
      validation: Rule => Rule.required()
    },
    {
      name: 'source',
      title: 'Fonte',
      type: 'reference',
      to: [{type: 'source'}],
      validation: Rule => Rule.required()
    },
    {
      name: 'kind',
      title: 'Tipo',
      type: 'string',
      validation: Rule => Rule.required()
    },
    {
      name: 'severity',
      title: 'Severidade',
      type: 'string',
      options: {
        list: ['ok', 'warn', 'fail', 'critical'],
        layout: 'radio'
      },
      validation: Rule => Rule.required()
    },
    {
      name: 'message',
      title: 'Mensagem',
      type: 'text',
      rows: 3,
      validation: Rule => Rule.required()
    },
    {
      name: 'timestamp',
      title: 'Timestamp',
      type: 'datetime',
      validation: Rule => Rule.required()
    },
    {
      name: 'actionable',
      title: 'Acionável',
      type: 'boolean',
      initialValue: false
    },
    {
      name: 'decision_required',
      title: 'Exige decisão',
      type: 'boolean',
      initialValue: false
    },
    {
      name: 'status',
      title: 'Status',
      type: 'string',
      options: {
        list: ['open', 'acknowledged', 'dismissed', 'resolved'],
        layout: 'radio'
      },
      initialValue: 'open'
    },
    {
      name: 'dedupe_key',
      title: 'Dedupe key',
      type: 'string'
    },
    {
      name: 'ttl_hours',
      title: 'TTL em horas',
      type: 'number',
      initialValue: 24
    },
    {
      name: 'context',
      title: 'Contexto',
      type: 'text',
      rows: 10,
      description: 'JSON reduzido com payload relevante'
    }
  ],
  preview: {
    select: {
      title: 'message',
      severity: 'severity',
      status: 'status'
    },
    prepare({title, severity, status}) {
      return {
        title,
        subtitle: `${severity || 'sem severidade'} · ${status || 'sem status'}`
      }
    }
  }
}
