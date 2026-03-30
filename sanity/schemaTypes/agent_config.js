export default {
  name: 'agent_config',
  title: 'Configuração de Agente',
  type: 'document',
  fields: [
    {
      name: 'agent_name',
      title: 'Agente',
      type: 'string',
      options: {
        list: [
          'focus_guard',
          'scheduler',
          'life_guard',
          'ecosystem_monitor',
          'notion_sync',
          'orchestrator',
          'validator',
          'retrospective'
        ]
      },
      validation: Rule => Rule.required()
    },
    {
      name: 'enabled',
      title: 'Habilitado',
      type: 'boolean',
      initialValue: true
    },
    {
      name: 'check_interval_minutes',
      title: 'Intervalo de check (minutos)',
      type: 'number'
    },
    {
      name: 'parameters',
      title: 'Parâmetros adicionais (JSON)',
      type: 'text',
      rows: 8,
      description: 'JSON com parâmetros específicos do agente'
    }
  ],
  preview: {
    select: { title: 'agent_name', subtitle: 'enabled' }
  }
}
