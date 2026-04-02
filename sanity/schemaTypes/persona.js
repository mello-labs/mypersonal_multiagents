export default {
  name: 'persona',
  title: 'Persona',
  type: 'document',
  fields: [
    {
      name: 'name',
      title: 'Nome',
      type: 'string',
      validation: Rule => Rule.required()
    },
    {
      name: 'persona_id',
      title: 'ID',
      type: 'slug',
      options: {source: 'name'},
      validation: Rule => Rule.required()
    },
    {
      name: 'short_name',
      title: 'Nome curto',
      type: 'string'
    },
    {
      name: 'description',
      title: 'Descrição',
      type: 'text'
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
          {title: 'Strategic', value: 'strategic'}
        ],
        layout: 'radio'
      }
    },
    {
      name: 'system_prompt',
      title: 'System Prompt base',
      type: 'text',
      rows: 20,
      validation: Rule => Rule.required()
    },
    {
      name: 'temperature_routing',
      title: 'Temperatura (roteamento)',
      type: 'number',
      validation: Rule => Rule.min(0).max(2)
    },
    {
      name: 'temperature_synthesis',
      title: 'Temperatura (síntese)',
      type: 'number',
      validation: Rule => Rule.min(0).max(2)
    },
    {
      name: 'active',
      title: 'Ativa',
      type: 'boolean',
      initialValue: true
    }
  ],
  preview: {
    select: {title: 'name', subtitle: 'tone'}
  }
}
