import {LinkIcon} from '@sanity/icons'

export default {
  name: 'source',
  title: 'Source',
  type: 'document',
  icon: LinkIcon,
  fields: [
    {
      name: 'id',
      title: 'ID',
      type: 'slug',
      options: {source: 'name'},
      validation: Rule => Rule.required()
    },
    {
      name: 'provider',
      title: 'Provider',
      type: 'string',
      options: {
        list: ['github', 'railway', 'vercel', 'cloudflare', 'onchain', 'notion', 'manual'],
        layout: 'radio'
      },
      validation: Rule => Rule.required()
    },
    {
      name: 'scope',
      title: 'Escopo',
      type: 'string',
      options: {
        list: ['org', 'project', 'service', 'token', 'repo', 'domain', 'contract'],
        layout: 'radio'
      },
      validation: Rule => Rule.required()
    },
    {
      name: 'name',
      title: 'Nome',
      type: 'string',
      validation: Rule => Rule.required()
    },
    {
      name: 'identifier',
      title: 'Identificador',
      type: 'string'
    },
    {
      name: 'active',
      title: 'Ativa',
      type: 'boolean',
      initialValue: true
    },
    {
      name: 'owner',
      title: 'Owner',
      type: 'string'
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
      name: 'metadata',
      title: 'Metadata',
      type: 'text',
      rows: 8,
      description: 'JSON reduzido com contexto estrutural da fonte'
    }
  ],
  preview: {
    select: {
      title: 'name',
      provider: 'provider',
      scope: 'scope'
    },
    prepare({title, provider, scope}) {
      return {
        title,
        subtitle: `${provider || 'sem provider'} · ${scope || 'sem escopo'}`
      }
    }
  }
}
