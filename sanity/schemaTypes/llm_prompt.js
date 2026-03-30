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
      title: 'Agente',
      type: 'string',
      options: {
        list: [
          'orchestrator',
          'focus_guard',
          'scheduler',
          'validator',
          'retrospective',
          'life_guard',
          'ecosystem_monitor'
        ]
      },
      validation: Rule => Rule.required()
    },
    {
      name: 'prompt_type',
      title: 'Tipo',
      type: 'string',
      options: {
        list: ['routing', 'synthesis', 'direct', 'deviation', 'validation', 'retrospective', 'scheduling']
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
    select: { title: 'name', subtitle: 'agent' }
  }
}
