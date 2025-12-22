# -*- coding: utf-8 -*-
from odoo import models, fields, api
import re
import logging

_logger = logging.getLogger(__name__)


class AIAgentPromptTemplate(models.Model):
    _name = 'ai.agent.prompt.template'
    _description = 'AI Agent Prompt Template'
    _order = 'sequence, name'

    name = fields.Char(string='Template Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Template content
    content = fields.Text(
        string='Template Content',
        required=True,
        help='Use {{variable_name}} for dynamic placeholders'
    )

    # Category
    category = fields.Selection([
        ('system', 'System Prompt'),
        ('instruction', 'Instructions'),
        ('context', 'Context Template'),
        ('response', 'Response Format'),
        ('rules', 'Rules Section'),
    ], string='Category', default='system')

    # Description for users
    description = fields.Text(string='Description')

    # Extracted variables (computed)
    variable_names = fields.Char(
        string='Variables',
        compute='_compute_variable_names',
        store=True
    )

    @api.depends('content')
    def _compute_variable_names(self):
        """Extract variable names from template"""
        for record in self:
            if record.content:
                variables = re.findall(r'\{\{(\w+)\}\}', record.content)
                record.variable_names = ', '.join(set(variables)) if variables else ''
            else:
                record.variable_names = ''

    def render(self, values=None):
        """
        Render template with given values

        Args:
            values: Dictionary of variable values

        Returns:
            Rendered string
        """
        self.ensure_one()
        values = values or {}

        result = self.content or ''
        for key, value in values.items():
            placeholder = '{{%s}}' % key
            result = result.replace(placeholder, str(value) if value else '')

        return result


class AIAgentPromptVariable(models.Model):
    _name = 'ai.agent.prompt.variable'
    _description = 'AI Agent Prompt Variable'
    _order = 'sequence, name'

    agent_id = fields.Many2one(
        'ai.agent',
        string='Agent',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(default=10)

    name = fields.Char(
        string='Variable Name',
        required=True,
        help='Name without brackets (e.g., company_name)'
    )
    description = fields.Char(string='Description')

    variable_type = fields.Selection([
        ('static', 'Static Value'),
        ('dynamic', 'Dynamic (from context)'),
        ('computed', 'Computed from Odoo'),
        ('selection', 'Selection List'),
    ], string='Type', default='static', required=True)

    # For static values
    static_value = fields.Text(string='Static Value')

    # For computed values
    compute_model = fields.Char(string='Model')
    compute_field = fields.Char(string='Field')
    compute_domain = fields.Char(string='Domain', default='[]')

    # For selection
    selection_options = fields.Text(
        string='Options',
        help='One option per line'
    )
    selected_option = fields.Char(string='Selected Option')

    # Current resolved value
    current_value = fields.Text(
        string='Current Value',
        compute='_compute_current_value'
    )

    @api.depends('variable_type', 'static_value', 'selected_option')
    def _compute_current_value(self):
        for record in self:
            if record.variable_type == 'static':
                record.current_value = record.static_value or ''
            elif record.variable_type == 'selection':
                record.current_value = record.selected_option or ''
            elif record.variable_type == 'computed':
                record.current_value = record._get_computed_value()
            else:
                record.current_value = f'{{{{dynamic:{record.name}}}}}'

    def _get_computed_value(self):
        """Get computed value from Odoo model"""
        self.ensure_one()

        if not self.compute_model or not self.compute_field:
            return ''

        try:
            model = self.env.get(self.compute_model)
            if not model:
                return f'[Model {self.compute_model} not found]'

            domain = eval(self.compute_domain or '[]')
            records = model.search(domain, limit=10)

            if not records:
                return '[No records found]'

            values = records.mapped(self.compute_field)
            return ', '.join(str(v) for v in values if v)

        except Exception as e:
            return f'[Error: {str(e)}]'

    def get_value(self, context=None):
        """
        Get the resolved value for this variable

        Args:
            context: Dictionary with dynamic context values

        Returns:
            Resolved value string
        """
        self.ensure_one()
        context = context or {}

        if self.variable_type == 'static':
            return self.static_value or ''

        elif self.variable_type == 'selection':
            return self.selected_option or ''

        elif self.variable_type == 'dynamic':
            # Look for value in context
            return context.get(self.name, '')

        elif self.variable_type == 'computed':
            return self._get_computed_value()

        return ''

    def get_selection_list(self):
        """Get list of selection options"""
        self.ensure_one()
        if not self.selection_options:
            return []
        return [opt.strip() for opt in self.selection_options.split('\n') if opt.strip()]
