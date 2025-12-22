# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class AIChannel(models.Model):
    _name = 'ai.channel'
    _description = 'AI Communication Channel'
    _order = 'sequence, name'

    name = fields.Char(string='Channel Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    channel_type = fields.Selection([
        ('mercadolibre', 'MercadoLibre'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('email', 'Email'),
        ('web', 'Web Widget'),
        ('facebook', 'Facebook Messenger'),
        ('instagram', 'Instagram'),
        ('custom', 'Custom'),
    ], string='Channel Type', required=True)

    # Channel-specific identifier
    channel_reference = fields.Char(
        string='Channel Reference',
        help='External reference ID for this channel (e.g., WhatsApp business ID)'
    )

    # Message format configuration
    message_format = fields.Selection([
        ('plain', 'Plain Text'),
        ('markdown', 'Markdown'),
        ('html', 'HTML'),
        ('rich', 'Rich (with buttons/cards)'),
    ], string='Message Format', default='plain')

    max_message_length = fields.Integer(
        string='Max Message Length',
        default=2000,
        help='Maximum characters per message (0 = unlimited)'
    )

    # Channel capabilities
    supports_attachments = fields.Boolean(
        string='Supports Attachments',
        default=False
    )
    supports_buttons = fields.Boolean(
        string='Supports Buttons',
        default=False
    )
    supports_cards = fields.Boolean(
        string='Supports Cards',
        default=False
    )
    supports_quick_replies = fields.Boolean(
        string='Supports Quick Replies',
        default=False
    )

    # Associated agents
    agent_ids = fields.Many2many(
        'ai.agent',
        'ai_agent_channel_rel',
        'channel_id',
        'agent_id',
        string='Associated Agents'
    )

    # Configuration (stored as JSON)
    config_data = fields.Text(
        string='Configuration',
        help='JSON configuration for channel-specific settings'
    )

    # Statistics
    total_conversations = fields.Integer(
        string='Total Conversations',
        compute='_compute_statistics'
    )
    total_messages = fields.Integer(
        string='Total Messages',
        compute='_compute_statistics'
    )

    # Description
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('channel_type_ref_unique', 'UNIQUE(channel_type, channel_reference)',
         'Channel reference must be unique per channel type!')
    ]

    def _compute_statistics(self):
        for record in self:
            conversations = self.env['ai.conversation'].search([
                ('channel_type', '=', record.channel_type)
            ])
            record.total_conversations = len(conversations)
            record.total_messages = sum(conversations.mapped('message_count'))

    @api.onchange('channel_type')
    def _onchange_channel_type(self):
        """Set default capabilities based on channel type"""
        capabilities = {
            'mercadolibre': {
                'message_format': 'plain',
                'max_message_length': 2000,
                'supports_attachments': True,
                'supports_buttons': False,
                'supports_cards': False,
                'supports_quick_replies': False,
            },
            'whatsapp': {
                'message_format': 'plain',
                'max_message_length': 4096,
                'supports_attachments': True,
                'supports_buttons': True,
                'supports_cards': False,
                'supports_quick_replies': True,
            },
            'telegram': {
                'message_format': 'markdown',
                'max_message_length': 4096,
                'supports_attachments': True,
                'supports_buttons': True,
                'supports_cards': False,
                'supports_quick_replies': True,
            },
            'email': {
                'message_format': 'html',
                'max_message_length': 0,
                'supports_attachments': True,
                'supports_buttons': False,
                'supports_cards': False,
                'supports_quick_replies': False,
            },
            'web': {
                'message_format': 'markdown',
                'max_message_length': 0,
                'supports_attachments': True,
                'supports_buttons': True,
                'supports_cards': True,
                'supports_quick_replies': True,
            },
            'facebook': {
                'message_format': 'plain',
                'max_message_length': 2000,
                'supports_attachments': True,
                'supports_buttons': True,
                'supports_cards': True,
                'supports_quick_replies': True,
            },
            'instagram': {
                'message_format': 'plain',
                'max_message_length': 1000,
                'supports_attachments': True,
                'supports_buttons': False,
                'supports_cards': False,
                'supports_quick_replies': False,
            },
        }

        if self.channel_type in capabilities:
            caps = capabilities[self.channel_type]
            for key, value in caps.items():
                setattr(self, key, value)

    def get_config(self, key=None, default=None):
        """Get configuration value"""
        self.ensure_one()
        import json
        try:
            config = json.loads(self.config_data or '{}')
            if key:
                return config.get(key, default)
            return config
        except json.JSONDecodeError:
            return default if key else {}

    def set_config(self, key, value):
        """Set configuration value"""
        self.ensure_one()
        import json
        try:
            config = json.loads(self.config_data or '{}')
        except json.JSONDecodeError:
            config = {}

        config[key] = value
        self.config_data = json.dumps(config)

    def format_message(self, text, attachments=None):
        """
        Format message according to channel requirements

        Args:
            text: Message text
            attachments: Optional list of attachments

        Returns:
            Formatted message dict ready for channel
        """
        self.ensure_one()

        # Truncate if needed
        if self.max_message_length and len(text) > self.max_message_length:
            text = text[:self.max_message_length - 3] + '...'

        # Format conversion
        if self.message_format == 'plain':
            text = self._strip_formatting(text)
        elif self.message_format == 'html':
            text = self._markdown_to_html(text)

        result = {'text': text}

        if attachments and self.supports_attachments:
            result['attachments'] = attachments

        return result

    def _strip_formatting(self, text):
        """Remove markdown/HTML formatting"""
        import re
        # Remove markdown bold/italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        # Remove markdown links
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        return text

    def _markdown_to_html(self, text):
        """Convert markdown to HTML"""
        import re
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Links
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
        # Line breaks
        text = text.replace('\n', '<br/>')
        return text
