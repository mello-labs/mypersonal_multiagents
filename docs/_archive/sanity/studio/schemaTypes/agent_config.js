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
          'orchestrator',
          'focus_guard',
          'scheduler',
          'notion_sync',
          'validator',
          'retrospective',
          'calendar_sync',
          'life_guard',
          'persona_manager',
          'gemma_local'
        ]
      },
      validation: Rule => Rule.required()
    },
    {
      name: 'uses_llm',
      title: 'Usa LLM',
      type: 'boolean',
      initialValue: false
    },
    {
      name: 'provider_preference',
      title: 'Provider preferido',
      type: 'string',
      options: {
        list: [
          { title: 'Auto', value: 'auto' },
          { title: 'OpenAI', value: 'openai' },
          { title: 'Gemma local', value: 'gemma_local' },
          { title: 'Nenhum', value: 'none' }
        ],
        layout: 'radio'
      },
      initialValue: 'auto'
    },
    {
      name: 'primary_model',
      title: 'Modelo principal',
      type: 'string',
      description: 'Ex.: gpt-4o-mini ou gemma3:4B-F16'
    },
    {
      name: 'fallback_model',
      title: 'Modelo fallback',
      type: 'string',
      description: 'Modelo usado quando o principal falhar'
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
      name: 'can_write_redis',
      title: 'Pode escrever no Redis',
      type: 'boolean',
      initialValue: true
    },
    {
      name: 'can_write_sanity',
      title: 'Pode escrever no Sanity',
      type: 'boolean',
      initialValue: false
    },
    {
      name: 'can_publish_public',
      title: 'Pode publicar em canal público',
      type: 'boolean',
      initialValue: false
    },
    {
      name: 'notes',
      title: 'Notas operacionais',
      type: 'text',
      rows: 4
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
    select: {
      title: 'agent_name',
      enabled: 'enabled',
      provider: 'provider_preference'
    },
    prepare({ title, enabled, provider }) {
      return {
        title,
        subtitle: `${enabled ? 'ativo' : 'desligado'} · ${provider || 'sem provider'}`
      }
    }
  }
}
