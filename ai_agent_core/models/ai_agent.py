# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re
import json
import logging

_logger = logging.getLogger(__name__)


class AIAgent(models.Model):
    _name = 'ai.agent'
    _description = 'AI Agent Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Agent Name', required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)

    # Description and purpose
    description = fields.Text(
        string='Description',
        help='Internal description of what this agent does'
    )

    # LLM Configuration
    provider_id = fields.Many2one(
        'ai.agent.provider',
        string='LLM Provider',
        required=True,
        tracking=True
    )
    model_name = fields.Char(
        string='Model',
        help='Leave empty to use provider default'
    )
    temperature = fields.Float(
        string='Temperature',
        default=0.7,
        help='Higher = more creative, Lower = more focused'
    )
    max_tokens = fields.Integer(
        string='Max Tokens',
        default=2000,
        help='Maximum tokens in response'
    )

    # System Prompt Configuration
    system_prompt_template = fields.Text(
        string='System Prompt',
        required=True,
        help='Main prompt template. Use {{variable}} for dynamic values.',
        default="""Eres un asistente virtual inteligente llamado {{agent_name}}.
Tu objetivo es ayudar a los clientes de manera eficiente y amable.

Empresa: {{company_name}}
Canal: {{channel}}

Instrucciones generales:
- Responde siempre en español
- Sé conciso pero completo
- Si no tienes información, indícalo claramente
- Usa las herramientas disponibles para obtener información

{{additional_instructions}}
"""
    )

    # Prompt variables
    prompt_variable_ids = fields.One2many(
        'ai.agent.prompt.variable',
        'agent_id',
        string='Prompt Variables'
    )

    # Behavior rules
    rule_ids = fields.One2many(
        'ai.agent.rule',
        'agent_id',
        string='Behavior Rules'
    )
    active_rules_count = fields.Integer(
        string='Active Rules',
        compute='_compute_active_rules_count'
    )

    # Tools
    tool_ids = fields.Many2many(
        'ai.agent.tool',
        'ai_agent_tool_rel',
        'agent_id',
        'tool_id',
        string='Enabled Tools'
    )
    tools_count = fields.Integer(
        string='Tools',
        compute='_compute_tools_count'
    )

    # Channels (populated by channel modules)
    channel_ids = fields.Many2many(
        'ai.channel',
        'ai_agent_channel_rel',
        'agent_id',
        'channel_id',
        string='Active Channels'
    )

    # Response configuration
    response_language = fields.Selection([
        ('es', 'Spanish'),
        ('en', 'English'),
        ('pt', 'Portuguese'),
        ('auto', 'Auto-detect'),
    ], string='Response Language', default='es')

    max_response_length = fields.Integer(
        string='Max Response Length',
        default=500,
        help='Maximum characters in response (0 = no limit)'
    )

    include_sources = fields.Boolean(
        string='Include Sources',
        default=False,
        help='Include data sources in responses'
    )

    # Advanced settings
    enable_memory = fields.Boolean(
        string='Enable Memory',
        default=True,
        help='Remember conversation context'
    )
    memory_window = fields.Integer(
        string='Memory Window',
        default=20,
        help='Number of messages to remember'
    )

    enable_intent_detection = fields.Boolean(
        string='Enable Intent Detection',
        default=False,
        help='Use AI to classify user intent'
    )

    fallback_response = fields.Text(
        string='Fallback Response',
        default="Lo siento, no pude procesar tu solicitud. ¿Podrías reformular tu pregunta?"
    )

    # Statistics
    conversation_ids = fields.One2many(
        'ai.conversation',
        'agent_id',
        string='Conversations'
    )
    total_conversations = fields.Integer(
        string='Total Conversations',
        compute='_compute_statistics'
    )
    total_messages = fields.Integer(
        string='Total Messages',
        compute='_compute_statistics'
    )

    @api.depends('rule_ids.active')
    def _compute_active_rules_count(self):
        for record in self:
            record.active_rules_count = len(record.rule_ids.filtered('active'))

    @api.depends('tool_ids')
    def _compute_tools_count(self):
        for record in self:
            record.tools_count = len(record.tool_ids)

    def _compute_statistics(self):
        for record in self:
            conversations = self.env['ai.conversation'].search([('agent_id', '=', record.id)])
            record.total_conversations = len(conversations)
            record.total_messages = sum(conversations.mapped('message_count'))

    @api.constrains('temperature')
    def _check_temperature(self):
        for record in self:
            if not 0 <= record.temperature <= 2:
                raise ValidationError("Temperature must be between 0 and 2")

    def build_system_prompt(self, context=None):
        """
        Build the complete system prompt with all variables resolved

        Args:
            context: Dictionary with dynamic context values

        Returns:
            Complete system prompt string
        """
        self.ensure_one()
        context = context or {}

        prompt = self.system_prompt_template or ''

        # Add default context values
        default_context = {
            'agent_name': self.name,
            'company_name': self.env.company.name,
            'channel': context.get('channel', 'general'),
            'additional_instructions': '',
        }
        default_context.update(context)

        # Resolve prompt variables
        for var in self.prompt_variable_ids:
            placeholder = '{{%s}}' % var.name
            value = var.get_value(context)
            prompt = prompt.replace(placeholder, value)

        # Resolve context variables
        for key, value in default_context.items():
            placeholder = '{{%s}}' % key
            prompt = prompt.replace(placeholder, str(value) if value else '')

        # Add active rules section
        rules_section = self._build_rules_section(context)
        if rules_section:
            prompt += "\n\n## Reglas de Comportamiento:\n" + rules_section

        # Add tools description
        if self.tool_ids:
            tools_section = self._build_tools_section()
            prompt += "\n\n## Herramientas Disponibles:\n" + tools_section

        return prompt.strip()

    def _build_rules_section(self, context=None):
        """Build the rules section for the prompt"""
        context = context or {}
        rules_text = []

        for rule in self.rule_ids.filtered('active').sorted('sequence'):
            # Check if rule should be included based on conditions
            if rule.trigger_type == 'always' or rule.check_trigger('', context):
                rules_text.append(f"- {rule.format_for_prompt()}")

        return "\n".join(rules_text)

    def _build_tools_section(self):
        """Build the tools description section"""
        tools_text = []
        for tool in self.tool_ids.filtered('active'):
            tools_text.append(f"- {tool.name}: {tool.description}")
        return "\n".join(tools_text)

    def get_triggered_rules(self, message, context=None):
        """
        Get all rules that trigger for a given message

        Args:
            message: User message
            context: Conversation context

        Returns:
            Recordset of triggered rules
        """
        self.ensure_one()
        context = context or {}

        triggered = self.env['ai.agent.rule']
        for rule in self.rule_ids.filtered('active').sorted(key=lambda r: -r.priority):
            if rule.check_trigger(message, context):
                triggered |= rule

        return triggered

    def get_langchain_tools(self, env=None):
        """
        Get LangChain tool definitions for this agent

        Args:
            env: Odoo environment (defaults to self.env)

        Returns:
            List of LangChain tools
        """
        self.ensure_one()
        env = env or self.env

        tools = []
        for tool in self.tool_ids.filtered('active'):
            try:
                lc_tool = tool.get_langchain_tool(env)
                tools.append(lc_tool)
            except Exception as e:
                _logger.warning(f"Failed to load tool {tool.name}: {e}")

        return tools

    def process_message(self, message, context=None, conversation=None):
        """
        Process a user message and return response

        Args:
            message: User message string
            context: Additional context dictionary
            conversation: Existing conversation record (optional)

        Returns:
            Dictionary with response and metadata
        """
        self.ensure_one()

        # Use the LangGraph engine service
        engine = self.env['ai.langgraph.engine']
        return engine.process_message(
            agent=self,
            message=message,
            context=context,
            conversation=conversation
        )

    def action_view_conversations(self):
        """Open conversations view for this agent"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Conversations - {self.name}',
            'res_model': 'ai.conversation',
            'view_mode': 'tree,form',
            'domain': [('agent_id', '=', self.id)],
            'context': {'default_agent_id': self.id},
        }

    def action_view_rules(self):
        """Open rules view for this agent"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Rules - {self.name}',
            'res_model': 'ai.agent.rule',
            'view_mode': 'tree,form',
            'domain': [('agent_id', '=', self.id)],
            'context': {'default_agent_id': self.id},
        }

    def action_test_prompt(self):
        """Test and preview the built prompt"""
        self.ensure_one()

        # Build sample prompt
        sample_context = {
            'channel': 'test',
            'partner_name': 'Cliente de Prueba',
        }
        prompt = self.build_system_prompt(sample_context)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Prompt Preview',
            'res_model': 'ai.agent.prompt.preview',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_agent_id': self.id,
                'default_prompt_preview': prompt,
            }
        }

    @api.model
    def get_default_agent_for_channel(self, channel_type):
        """
        Get the default agent for a channel type

        Args:
            channel_type: Channel type string

        Returns:
            Agent record or False
        """
        return self.search([
            ('active', '=', True),
            ('channel_ids.channel_type', '=', channel_type)
        ], limit=1)
