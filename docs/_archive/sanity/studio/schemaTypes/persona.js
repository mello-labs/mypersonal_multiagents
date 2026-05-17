export default {
  name: 'persona',
  title: 'Persona',
  type: 'document',
  fields: [
    {
      name: 'name',
      title: 'Nome',
      type: 'string',
      validation: (Rule) => Rule.required(),
    },
    {
      name: 'persona_id',
      title: 'ID',
      type: 'slug',
      options: {source: 'name'},
      validation: (Rule) => Rule.required(),
    },
    {
      name: 'short_name',
      title: 'Nome curto',
      type: 'string',
    },
    {
      name: 'icon',
      title: 'Icone',
      type: 'string',
      description: 'Unicode curto para representar a persona na UI',
    },
    {
      name: 'description',
      title: 'Descrição',
      type: 'text',
    },
    {
      name: 'role',
      title: 'Papel',
      type: 'string',
      description: 'Ex.: arquiteto, coordenador, auditor, fallback local',
    },
    {
      name: 'tone',
      title: 'Tom',
      type: 'string',
      options: {
        list: [
          {title: 'Warm', value: 'warm'},
          {title: 'Professional', value: 'professional'},
          {title: 'Direct', value: 'direct'},
          {title: 'Casual', value: 'casual'},
          {title: 'Technical', value: 'technical'},
          {title: 'Strategic', value: 'strategic'},
          {title: 'Sharp', value: 'sharp'},
          {title: 'Bold', value: 'bold'},
          {title: 'Neutral', value: 'neutral'},
        ],
        layout: 'radio',
      },
    },
    {
      name: 'language',
      title: 'Idioma',
      type: 'string',
      description: 'Ex.: pt-BR ou en',
    },
    {
      name: 'style_rules',
      title: 'Regras de estilo',
      type: 'array',
      of: [{type: 'string'}],
      description: 'Regras curtas e atômicas de linguagem',
    },
    {
      name: 'system_prompt',
      title: 'System Prompt base',
      type: 'text',
      rows: 20,
      validation: (Rule) => Rule.required(),
    },
    {
      name: 'synthesis_prompt_override',
      title: 'Override de síntese',
      type: 'text',
      rows: 8,
    },
    {
      name: 'direct_prompt_override',
      title: 'Override de resposta direta',
      type: 'text',
      rows: 8,
    },
    {
      name: 'preferred_model',
      title: 'Modelo preferido',
      type: 'string',
      description: 'Ex.: gpt-4o-mini ou gemma3:4B-F16',
    },
    {
      name: 'temperature_routing',
      title: 'Temperatura (roteamento)',
      type: 'number',
      validation: (Rule) => Rule.min(0).max(2),
    },
    {
      name: 'temperature_synthesis',
      title: 'Temperatura (síntese)',
      type: 'number',
      validation: (Rule) => Rule.min(0).max(2),
    },
    {
      name: 'temperature_direct',
      title: 'Temperatura (direta)',
      type: 'number',
      validation: (Rule) => Rule.min(0).max(2),
    },
    {
      name: 'parameters',
      title: 'Parâmetros',
      type: 'object',
      fields: [
        {
          name: 'temperature_routing',
          title: 'Temperatura (roteamento)',
          type: 'number',
          validation: (Rule) => Rule.min(0).max(2),
        },
        {
          name: 'temperature_synthesis',
          title: 'Temperatura (síntese)',
          type: 'number',
          validation: (Rule) => Rule.min(0).max(2),
        },
        {
          name: 'temperature_direct',
          title: 'Temperatura (direta)',
          type: 'number',
          validation: (Rule) => Rule.min(0).max(2),
        },
      ],
    },
    {
      name: 'active',
      title: 'Ativa',
      type: 'boolean',
      initialValue: true,
    },
  ],
  preview: {
    select: {
      title: 'name',
      tone: 'tone',
      role: 'role',
      icon: 'icon',
    },
    prepare({title, tone, role, icon}) {
      return {
        title: icon ? `${icon} ${title}` : title,
        subtitle: role ? `${role} · ${tone || 'sem tom'}` : tone || 'sem tom',
      }
    },
  },
}
