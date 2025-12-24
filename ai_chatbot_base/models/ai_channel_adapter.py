# -*- coding: utf-8 -*-
from odoo import models, api
import re
import json
import logging

_logger = logging.getLogger(__name__)


class AIChannelAdapter(models.AbstractModel):
    _name = 'ai.channel.adapter'
    _description = 'AI Channel Message Adapter'

    @api.model
    def get_adapter(self, channel_type):
        """
        Get the appropriate adapter for a channel type

        Args:
            channel_type: Channel type string

        Returns:
            Adapter instance or generic adapter
        """
        adapters = {
            'mercadolibre': MercadoLibreAdapter,
            'whatsapp': WhatsAppAdapter,
            'telegram': TelegramAdapter,
            'email': EmailAdapter,
            'web': WebAdapter,
        }

        adapter_class = adapters.get(channel_type, GenericAdapter)
        return adapter_class(self.env)

    @api.model
    def format_response(self, channel_type, response_text, context=None):
        """
        Format a response for a specific channel

        Args:
            channel_type: Target channel type
            response_text: AI response text
            context: Additional context

        Returns:
            Formatted response dict
        """
        adapter = self.get_adapter(channel_type)
        return adapter.format_outgoing(response_text, context)

    @api.model
    def parse_incoming(self, channel_type, raw_message, context=None):
        """
        Parse an incoming message from a channel

        Args:
            channel_type: Source channel type
            raw_message: Raw message data
            context: Additional context

        Returns:
            Normalized message dict
        """
        adapter = self.get_adapter(channel_type)
        return adapter.parse_incoming(raw_message, context)


class BaseAdapter:
    """Base adapter class for channel message formatting"""

    def __init__(self, env):
        self.env = env

    def parse_incoming(self, raw_message, context=None):
        """Parse incoming message to normalized format"""
        return {
            'text': raw_message.get('text', ''),
            'sender_id': raw_message.get('sender_id'),
            'conversation_id': raw_message.get('conversation_id'),
            'attachments': raw_message.get('attachments', []),
            'metadata': raw_message.get('metadata', {}),
        }

    def format_outgoing(self, text, context=None):
        """Format outgoing response for channel"""
        return {
            'text': text,
            'format': 'plain',
        }

    def truncate_text(self, text, max_length):
        """Truncate text to max length"""
        if max_length and len(text) > max_length:
            return text[:max_length - 3] + '...'
        return text

    def strip_markdown(self, text):
        """Remove markdown formatting"""
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        # Code
        text = re.sub(r'`(.+?)`', r'\1', text)
        # Links
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        # Headers
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        # Lists
        text = re.sub(r'^\s*[-*]\s*', '• ', text, flags=re.MULTILINE)
        return text

    def markdown_to_html(self, text):
        """Convert markdown to HTML"""
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Code
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        # Links
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
        # Line breaks
        text = text.replace('\n', '<br/>')
        return text


class GenericAdapter(BaseAdapter):
    """Generic adapter for unknown channels"""
    pass


class MercadoLibreAdapter(BaseAdapter):
    """Adapter for MercadoLibre messaging"""

    MAX_LENGTH = 2000

    def parse_incoming(self, raw_message, context=None):
        """Parse MercadoLibre message format"""
        # MercadoLibre message structure
        return {
            'text': raw_message.get('text', {}).get('plain', '') or raw_message.get('text', ''),
            'sender_id': raw_message.get('from', {}).get('user_id'),
            'conversation_id': raw_message.get('conversation_id') or raw_message.get('resource_id'),
            'attachments': raw_message.get('attachments', []),
            'metadata': {
                'message_id': raw_message.get('id'),
                'order_id': raw_message.get('resource_id'),
                'item_id': raw_message.get('item_id'),
                'status': raw_message.get('status'),
            },
        }

    def format_outgoing(self, text, context=None):
        """Format response for MercadoLibre"""
        # MercadoLibre doesn't support markdown
        text = self.strip_markdown(text)
        text = self.truncate_text(text, self.MAX_LENGTH)

        return {
            'text': text,
            'format': 'plain',
            'plain': text,  # ML specific format
        }


class WhatsAppAdapter(BaseAdapter):
    """Adapter for WhatsApp messaging"""

    MAX_LENGTH = 4096

    def parse_incoming(self, raw_message, context=None):
        """Parse WhatsApp message format"""
        # Handle different message types
        message_type = raw_message.get('type', 'text')

        text = ''
        if message_type == 'text':
            text = raw_message.get('text', {}).get('body', '')
        elif message_type == 'interactive':
            interactive = raw_message.get('interactive', {})
            if interactive.get('type') == 'button_reply':
                text = interactive.get('button_reply', {}).get('title', '')
            elif interactive.get('type') == 'list_reply':
                text = interactive.get('list_reply', {}).get('title', '')

        return {
            'text': text,
            'sender_id': raw_message.get('from'),
            'conversation_id': raw_message.get('from'),  # WhatsApp uses phone as conversation ID
            'attachments': self._extract_attachments(raw_message),
            'metadata': {
                'message_id': raw_message.get('id'),
                'timestamp': raw_message.get('timestamp'),
                'type': message_type,
            },
        }

    def _extract_attachments(self, raw_message):
        """Extract attachments from WhatsApp message"""
        attachments = []
        for media_type in ['image', 'audio', 'video', 'document']:
            if media_type in raw_message:
                attachments.append({
                    'type': media_type,
                    'id': raw_message[media_type].get('id'),
                    'mime_type': raw_message[media_type].get('mime_type'),
                })
        return attachments

    def format_outgoing(self, text, context=None):
        """Format response for WhatsApp"""
        # WhatsApp supports basic formatting
        text = self.truncate_text(text, self.MAX_LENGTH)

        # Convert markdown to WhatsApp format
        # Bold: **text** -> *text*
        text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
        # Italic: *text* -> _text_
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'_\1_', text)

        return {
            'text': text,
            'format': 'whatsapp',
            'type': 'text',
            'body': text,
        }


class TelegramAdapter(BaseAdapter):
    """Adapter for Telegram messaging"""

    MAX_LENGTH = 4096

    def parse_incoming(self, raw_message, context=None):
        """Parse Telegram message format"""
        message = raw_message.get('message', raw_message)

        return {
            'text': message.get('text', ''),
            'sender_id': str(message.get('from', {}).get('id', '')),
            'conversation_id': str(message.get('chat', {}).get('id', '')),
            'attachments': self._extract_attachments(message),
            'metadata': {
                'message_id': message.get('message_id'),
                'date': message.get('date'),
                'chat_type': message.get('chat', {}).get('type'),
                'from_username': message.get('from', {}).get('username'),
            },
        }

    def _extract_attachments(self, message):
        """Extract attachments from Telegram message"""
        attachments = []
        if 'photo' in message:
            # Get largest photo
            largest = max(message['photo'], key=lambda x: x.get('file_size', 0))
            attachments.append({'type': 'photo', 'file_id': largest.get('file_id')})
        if 'document' in message:
            attachments.append({'type': 'document', 'file_id': message['document'].get('file_id')})
        if 'voice' in message:
            attachments.append({'type': 'voice', 'file_id': message['voice'].get('file_id')})
        return attachments

    def format_outgoing(self, text, context=None):
        """Format response for Telegram"""
        text = self.truncate_text(text, self.MAX_LENGTH)

        # Telegram supports MarkdownV2, but basic markdown works
        return {
            'text': text,
            'format': 'markdown',
            'parse_mode': 'Markdown',
        }


class EmailAdapter(BaseAdapter):
    """Adapter for Email communication"""

    def parse_incoming(self, raw_message, context=None):
        """Parse email message format"""
        return {
            'text': raw_message.get('body_plain') or raw_message.get('body', ''),
            'sender_id': raw_message.get('from'),
            'conversation_id': raw_message.get('message_id') or raw_message.get('thread_id'),
            'attachments': raw_message.get('attachments', []),
            'metadata': {
                'subject': raw_message.get('subject'),
                'to': raw_message.get('to'),
                'cc': raw_message.get('cc'),
                'date': raw_message.get('date'),
            },
        }

    def format_outgoing(self, text, context=None):
        """Format response for Email"""
        # Convert to HTML for email
        html_text = self.markdown_to_html(text)

        return {
            'text': text,
            'html': html_text,
            'format': 'html',
        }


class WebAdapter(BaseAdapter):
    """Adapter for Web widget"""

    def parse_incoming(self, raw_message, context=None):
        """Parse web widget message format"""
        return {
            'text': raw_message.get('message') or raw_message.get('text', ''),
            'sender_id': raw_message.get('session_id') or raw_message.get('user_id'),
            'conversation_id': raw_message.get('conversation_id'),
            'attachments': raw_message.get('attachments', []),
            'metadata': raw_message.get('metadata', {}),
        }

    def format_outgoing(self, text, context=None):
        """Format response for Web widget"""
        # Web supports full formatting
        return {
            'text': text,
            'format': 'markdown',
            'html': self.markdown_to_html(text),
        }
