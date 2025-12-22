# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)


class AIConversation(models.Model):
    _name = 'ai.conversation'
    _description = 'AI Conversation History'
    _order = 'last_message_date desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(
        string='Conversation ID',
        required=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('ai.conversation') or 'CONV-NEW'
    )

    agent_id = fields.Many2one(
        'ai.agent',
        string='Agent',
        required=True,
        ondelete='restrict'
    )

    # Channel information
    channel_type = fields.Selection([
        ('mercadolibre', 'MercadoLibre'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('email', 'Email'),
        ('web', 'Web Widget'),
        ('playground', 'Playground'),
    ], string='Channel', required=True, default='web')

    channel_reference = fields.Char(
        string='Channel Reference',
        help='External conversation ID from the channel'
    )

    # Customer information
    partner_id = fields.Many2one('res.partner', string='Customer')
    external_user_id = fields.Char(string='External User ID')
    external_user_name = fields.Char(string='External User Name')

    # Status
    state = fields.Selection([
        ('active', 'Active'),
        ('waiting', 'Waiting for Response'),
        ('transferred', 'Transferred to Human'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    ], string='Status', default='active', tracking=True)

    # Messages
    message_ids = fields.One2many(
        'ai.conversation.message',
        'conversation_id',
        string='Messages'
    )
    message_count = fields.Integer(
        string='Message Count',
        compute='_compute_message_count',
        store=True
    )

    # Timestamps
    start_date = fields.Datetime(
        string='Started',
        default=fields.Datetime.now
    )
    last_message_date = fields.Datetime(
        string='Last Message',
        compute='_compute_last_message_date',
        store=True
    )

    # Context and metadata
    context_data = fields.Text(
        string='Context Data',
        help='JSON with conversation context'
    )
    metadata = fields.Text(
        string='Metadata',
        help='Additional JSON metadata'
    )

    # Related records created
    activity_task_ids = fields.One2many(
        'ai.activity.task',
        'conversation_id',
        string='Activity Tasks'
    )

    # Analytics
    total_tokens = fields.Integer(string='Total Tokens', default=0)
    avg_response_time = fields.Float(string='Avg Response Time (s)', default=0)

    # Summary (can be AI-generated)
    summary = fields.Text(string='Conversation Summary')

    @api.depends('message_ids')
    def _compute_message_count(self):
        for record in self:
            record.message_count = len(record.message_ids)

    @api.depends('message_ids.create_date')
    def _compute_last_message_date(self):
        for record in self:
            if record.message_ids:
                record.last_message_date = max(record.message_ids.mapped('create_date'))
            else:
                record.last_message_date = record.start_date

    def get_context(self):
        """Get conversation context as dictionary"""
        self.ensure_one()
        base_context = {
            'conversation_id': self.id,
            'channel': self.channel_type,
            'message_count': self.message_count,
            'partner_name': self.partner_id.name if self.partner_id else self.external_user_name,
        }

        # Merge with stored context
        if self.context_data:
            try:
                stored = json.loads(self.context_data)
                base_context.update(stored)
            except json.JSONDecodeError:
                pass

        return base_context

    def set_context(self, key, value):
        """Set a context value"""
        self.ensure_one()
        context = {}
        if self.context_data:
            try:
                context = json.loads(self.context_data)
            except json.JSONDecodeError:
                context = {}

        context[key] = value
        self.context_data = json.dumps(context)

    def get_message_history(self, limit=20):
        """
        Get conversation history formatted for LLM

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of message dictionaries
        """
        self.ensure_one()
        messages = self.message_ids.sorted('create_date')[-limit:]

        return [
            {
                'role': msg.role,
                'content': msg.content
            }
            for msg in messages
        ]

    def add_message(self, role, content, metadata=None):
        """
        Add a message to the conversation

        Args:
            role: 'user', 'assistant', or 'system'
            content: Message content
            metadata: Optional dictionary of additional data

        Returns:
            Created message record
        """
        self.ensure_one()

        vals = {
            'conversation_id': self.id,
            'role': role,
            'content': content,
        }

        if metadata:
            vals['metadata'] = json.dumps(metadata)

        return self.env['ai.conversation.message'].create(vals)

    def action_close(self):
        """Close the conversation"""
        self.write({'state': 'closed'})

    def action_reopen(self):
        """Reopen a closed conversation"""
        self.write({'state': 'active'})

    def action_transfer_to_human(self):
        """Transfer conversation to human agent"""
        self.write({'state': 'transferred'})
        # TODO: Create notification/task for human agent

    def action_generate_summary(self):
        """Generate AI summary of the conversation"""
        self.ensure_one()

        if not self.message_ids:
            return

        # Get agent's LLM
        llm = self.agent_id.provider_id._get_llm_client(
            temperature=0.3,
            max_tokens=500
        )

        # Build conversation text
        conversation_text = "\n".join([
            f"{msg.role.upper()}: {msg.content}"
            for msg in self.message_ids.sorted('create_date')
        ])

        prompt = f"""Summarize the following customer conversation in 2-3 sentences.
Focus on: main topic, customer requests, and outcomes.

Conversation:
{conversation_text}

Summary:"""

        try:
            response = llm.invoke(prompt)
            self.summary = response.content
        except Exception as e:
            _logger.error(f"Error generating summary: {e}")

    @api.model
    def cleanup_old_conversations(self, days=90):
        """Archive old conversations (called by cron)"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)

        old_conversations = self.search([
            ('state', '=', 'closed'),
            ('last_message_date', '<', cutoff_date)
        ])

        old_conversations.write({'state': 'archived'})
        return len(old_conversations)


class AIConversationMessage(models.Model):
    _name = 'ai.conversation.message'
    _description = 'AI Conversation Message'
    _order = 'create_date, id'

    conversation_id = fields.Many2one(
        'ai.conversation',
        string='Conversation',
        required=True,
        ondelete='cascade'
    )

    role = fields.Selection([
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
        ('tool', 'Tool Result'),
    ], string='Role', required=True)

    content = fields.Text(string='Content', required=True)

    # Metadata
    metadata = fields.Text(string='Metadata')

    # Token tracking
    input_tokens = fields.Integer(string='Input Tokens', default=0)
    output_tokens = fields.Integer(string='Output Tokens', default=0)

    # Tool calls
    tool_calls = fields.Text(
        string='Tool Calls',
        help='JSON array of tool calls made'
    )

    # Processing info
    processing_time = fields.Float(string='Processing Time (s)')
    model_used = fields.Char(string='Model Used')

    def get_tool_calls_list(self):
        """Get tool calls as list of dictionaries"""
        if not self.tool_calls:
            return []
        try:
            return json.loads(self.tool_calls)
        except json.JSONDecodeError:
            return []
