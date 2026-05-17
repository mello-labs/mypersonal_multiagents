export default {
  name: 'llm_prompt',
  title: 'LLM Prompt',
  type: 'document',
  fields: [
    {
      name: 'name',
      title: 'Nome',
      type: 'string',
      validation: Rule => Rule.required()
    },
    {
      name: 'id',
      title: 'ID único',
      type: 'slug',
      options: { source: 'name' },
      validation: Rule => Rule.required()
    },
    {
      name: 'agent',
      title: 'Agente ou capacidade',
      type: 'string',
      options: {
        list: [
          'orchestrator',
          'focus_guard',
          'scheduler',
          'validator',
          'retrospective',
          'gemma_local'
        ]
      },
      validation: Rule => Rule.required()
    },
    {
      name: 'prompt_type',
      title: 'Tipo',
      type: 'string',
      options: {
        list: [
          'routing',
          'synthesis',
          'direct',
          'deviation',
          'validation',
          'retrospective',
          'scheduling',
          'fallback',
          'intervention'
        ]
      }
    },
    {
      name: 'system_prompt',
      title: 'System Prompt',
      type: 'text',
      rows: 20,
      validation: Rule => Rule.required()
    },
    {
      name: 'temperature',
      title: 'Temperatura',
      type: 'number',
      validation: Rule => Rule.min(0).max(2)
    },
    {
      name: 'model_hint',
      title: 'Modelo sugerido',
      type: 'string',
      description: 'Ex.: gpt-4o-mini ou gemma3:4B-F16'
    },
    {
      name: 'version',
      title: 'Versão',
      type: 'string',
      initialValue: 'v1'
    },
    {
      name: 'active',
      title: 'Ativo',
      type: 'boolean',
      initialValue: true
    },
    {
      name: 'notes',
      title: 'Notas / Changelog',
      type: 'text',
      rows: 4
    }
  ],
  preview: {
    select: {
      title: 'name',
      agent: 'agent',
      type: 'prompt_type',
      active: 'active'
    },
    prepare({ title, agent, type, active }) {
      return {
        title,
        subtitle: `${agent}${type ? ` · ${type}` : ''}${active ? '' : ' · inativo'}`
      }
    }
  }
}
