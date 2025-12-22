# -*- coding: utf-8 -*-
from odoo import models, fields, api
import re
import json
import logging

_logger = logging.getLogger(__name__)


class AIAgentRule(models.Model):
    _name = 'ai.agent.rule'
    _description = 'AI Agent Behavior Rule'
    _order = 'sequence, name'

    agent_id = fields.Many2one(
        'ai.agent',
        string='Agent',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Rule Name', required=True)
    active = fields.Boolean(default=True)

    # Trigger configuration
    trigger_type = fields.Selection([
        ('keyword', 'Keyword Detection'),
        ('pattern', 'Regex Pattern'),
        ('intent', 'Intent Classification'),
        ('entity', 'Entity Detection'),
        ('sentiment', 'Sentiment Analysis'),
        ('always', 'Always Apply'),
    ], string='Trigger Type', default='keyword', required=True)

    trigger_value = fields.Char(
        string='Trigger Value',
        help='Keywords (comma-separated), regex pattern, or intent name'
    )

    trigger_description = fields.Text(
        string='Trigger Description',
        help='Human-readable description of when this rule applies'
    )

    # Action configuration
    action_type = fields.Selection([
        ('instruction', 'Add Instruction'),
        ('tool', 'Execute Tool'),
        ('activity', 'Create Activity'),
        ('response', 'Custom Response'),
        ('transfer', 'Transfer to Human'),
        ('workflow', 'Trigger Workflow'),
        ('context', 'Add Context'),
    ], string='Action Type', default='instruction', required=True)

    # For instruction action
    instruction_text = fields.Text(
        string='Instruction',
        help='Additional instruction to add to the prompt when rule triggers'
    )

    # For tool action
    tool_id = fields.Many2one('ai.agent.tool', string='Tool to Execute')
    tool_params = fields.Text(
        string='Tool Parameters',
        help='JSON parameters for the tool'
    )

    # For activity action
    activity_type = fields.Selection([
        ('create_invoice', 'Create Invoice'),
        ('create_lead', 'Create CRM Lead'),
        ('create_ticket', 'Create Support Ticket'),
        ('create_task', 'Create Task'),
        ('send_email', 'Send Email'),
        ('custom', 'Custom Activity'),
    ], string='Activity Type')

    activity_data_extraction = fields.Text(
        string='Data Extraction Prompt',
        help='Instructions for AI to extract data for this activity'
    )

    # For response action
    response_template = fields.Text(
        string='Response Template',
        help='Template for custom response with {{variable}} placeholders'
    )

    # For transfer action
    transfer_to = fields.Selection([
        ('human_agent', 'Human Agent'),
        ('specific_user', 'Specific User'),
        ('department', 'Department'),
    ], string='Transfer To')
    transfer_user_id = fields.Many2one('res.users', string='Specific User')
    transfer_message = fields.Text(string='Transfer Message')

    # For context action
    context_key = fields.Char(string='Context Key')
    context_value = fields.Text(string='Context Value')

    # Conditions
    condition_ids = fields.One2many(
        'ai.agent.rule.condition',
        'rule_id',
        string='Additional Conditions'
    )

    # Priority and limits
    priority = fields.Integer(
        string='Priority',
        default=10,
        help='Higher priority rules are evaluated first'
    )
    max_triggers_per_conversation = fields.Integer(
        string='Max Triggers',
        default=0,
        help='Maximum times this rule can trigger per conversation (0 = unlimited)'
    )

    def check_trigger(self, message, context=None):
        """
        Check if this rule should trigger for the given message

        Args:
            message: User message string
            context: Conversation context dictionary

        Returns:
            Boolean indicating if rule should trigger
        """
        self.ensure_one()
        context = context or {}

        if not self.active:
            return False

        # Check additional conditions first
        if self.condition_ids:
            if not all(cond.evaluate(context) for cond in self.condition_ids):
                return False

        # Check trigger based on type
        if self.trigger_type == 'always':
            return True

        elif self.trigger_type == 'keyword':
            if not self.trigger_value:
                return False
            keywords = [k.strip().lower() for k in self.trigger_value.split(',')]
            message_lower = message.lower()
            return any(keyword in message_lower for keyword in keywords)

        elif self.trigger_type == 'pattern':
            if not self.trigger_value:
                return False
            try:
                pattern = re.compile(self.trigger_value, re.IGNORECASE)
                return bool(pattern.search(message))
            except re.error:
                _logger.warning(f"Invalid regex pattern in rule {self.name}: {self.trigger_value}")
                return False

        elif self.trigger_type == 'intent':
            # Intent should be provided in context by intent classifier
            detected_intent = context.get('detected_intent', '')
            return detected_intent == self.trigger_value

        elif self.trigger_type == 'entity':
            # Entities should be provided in context
            detected_entities = context.get('detected_entities', [])
            return self.trigger_value in detected_entities

        elif self.trigger_type == 'sentiment':
            # Sentiment should be provided in context
            sentiment = context.get('sentiment', '')
            return sentiment == self.trigger_value

        return False

    def get_action_prompt(self):
        """
        Get the prompt modification for this rule

        Returns:
            String to add to the prompt
        """
        self.ensure_one()

        if self.action_type == 'instruction':
            return self.instruction_text or ''

        elif self.action_type == 'activity':
            return f"""
IMPORTANT: The user is requesting a {self.activity_type} action.
{self.activity_data_extraction or ''}
Use the create_activity_task tool to register this request.
"""

        elif self.action_type == 'response':
            return f"When responding to this, use the following template: {self.response_template}"

        elif self.action_type == 'transfer':
            return f"""
IMPORTANT: This conversation should be transferred to a human agent.
Transfer reason: {self.transfer_message or 'User request requires human assistance'}
Politely inform the user that you are transferring them to a human agent.
"""

        return ''

    def format_for_prompt(self):
        """
        Format rule for inclusion in system prompt

        Returns:
            Formatted string describing the rule
        """
        self.ensure_one()

        parts = [f"Rule: {self.name}"]

        if self.trigger_description:
            parts.append(f"When: {self.trigger_description}")
        elif self.trigger_value:
            parts.append(f"Trigger: {self.trigger_type} = {self.trigger_value}")

        action_desc = self._get_action_description()
        if action_desc:
            parts.append(f"Action: {action_desc}")

        return " | ".join(parts)

    def _get_action_description(self):
        """Get human-readable action description"""
        if self.action_type == 'instruction':
            return self.instruction_text[:100] + '...' if len(self.instruction_text or '') > 100 else self.instruction_text

        elif self.action_type == 'tool':
            return f"Execute tool: {self.tool_id.name if self.tool_id else 'Not set'}"

        elif self.action_type == 'activity':
            return f"Create activity: {self.activity_type}"

        elif self.action_type == 'response':
            return "Use custom response template"

        elif self.action_type == 'transfer':
            return f"Transfer to: {self.transfer_to}"

        elif self.action_type == 'context':
            return f"Set context: {self.context_key}"

        return ''


class AIAgentRuleCondition(models.Model):
    _name = 'ai.agent.rule.condition'
    _description = 'AI Agent Rule Condition'
    _order = 'sequence'

    rule_id = fields.Many2one(
        'ai.agent.rule',
        string='Rule',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(default=10)

    condition_type = fields.Selection([
        ('context_value', 'Context Value'),
        ('time_range', 'Time Range'),
        ('channel', 'Channel Type'),
        ('customer_tag', 'Customer Tag'),
        ('conversation_length', 'Conversation Length'),
    ], string='Condition Type', required=True)

    # For context_value
    context_key = fields.Char(string='Context Key')
    operator = fields.Selection([
        ('equals', 'Equals'),
        ('not_equals', 'Not Equals'),
        ('contains', 'Contains'),
        ('greater_than', 'Greater Than'),
        ('less_than', 'Less Than'),
        ('in_list', 'In List'),
    ], string='Operator', default='equals')
    context_value = fields.Char(string='Value')

    # For time_range
    time_start = fields.Float(string='Start Hour')
    time_end = fields.Float(string='End Hour')

    # For channel
    channel_type = fields.Selection([
        ('mercadolibre', 'MercadoLibre'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('email', 'Email'),
        ('web', 'Web'),
    ], string='Channel')

    def evaluate(self, context):
        """
        Evaluate condition against context

        Args:
            context: Dictionary with conversation context

        Returns:
            Boolean result
        """
        self.ensure_one()

        if self.condition_type == 'context_value':
            actual_value = context.get(self.context_key)
            expected_value = self.context_value

            if self.operator == 'equals':
                return str(actual_value) == str(expected_value)
            elif self.operator == 'not_equals':
                return str(actual_value) != str(expected_value)
            elif self.operator == 'contains':
                return str(expected_value) in str(actual_value)
            elif self.operator == 'greater_than':
                try:
                    return float(actual_value) > float(expected_value)
                except (ValueError, TypeError):
                    return False
            elif self.operator == 'less_than':
                try:
                    return float(actual_value) < float(expected_value)
                except (ValueError, TypeError):
                    return False
            elif self.operator == 'in_list':
                items = [i.strip() for i in expected_value.split(',')]
                return str(actual_value) in items

        elif self.condition_type == 'channel':
            return context.get('channel') == self.channel_type

        elif self.condition_type == 'time_range':
            from datetime import datetime
            current_hour = datetime.now().hour + datetime.now().minute / 60
            return self.time_start <= current_hour <= self.time_end

        elif self.condition_type == 'conversation_length':
            msg_count = context.get('message_count', 0)
            try:
                return msg_count >= int(self.context_value)
            except (ValueError, TypeError):
                return False

        return True
