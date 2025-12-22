# -*- coding: utf-8 -*-
from odoo import models, api
import json
import logging

_logger = logging.getLogger(__name__)


class MeliMessageHandler(models.AbstractModel):
    _name = 'ai.meli.message.handler'
    _description = 'MercadoLibre Message Handler'

    @api.model
    def process_webhook(self, config_id, payload):
        """
        Process incoming webhook notification

        Args:
            config_id: ai.meli.config ID
            payload: Webhook payload

        Returns:
            Processing result
        """
        config = self.env['ai.meli.config'].browse(config_id)
        if not config.exists() or not config.active:
            return {'success': False, 'error': 'Invalid or inactive configuration'}

        topic = payload.get('topic')
        resource = payload.get('resource')

        _logger.info(f"MercadoLibre webhook: {topic} - {resource}")

        if topic == 'messages':
            return self._handle_message_notification(config, payload)
        elif topic == 'questions':
            return self._handle_question_notification(config, payload)
        elif topic == 'orders':
            return self._handle_order_notification(config, payload)

        return {'success': True, 'message': f'Topic {topic} not handled'}

    def _handle_message_notification(self, config, payload):
        """Handle message notification"""
        resource = payload.get('resource', '')

        # Extract message info from resource URL
        # Format: /messages/pack_id/sellers/user_id/from/buyer_id
        parts = resource.split('/')

        try:
            # Fetch actual message
            response = config._make_api_request('GET', resource)

            if not response.ok:
                return {'success': False, 'error': response.text}

            message_data = response.json()

            # Check if it's an incoming message
            sender_id = str(message_data.get('from', {}).get('user_id', ''))
            if sender_id == config.meli_user_id:
                # Our own message, skip
                return {'success': True, 'message': 'Own message, skipped'}

            # Create message log
            message_log = self.env['ai.meli.message.log'].create({
                'config_id': config.id,
                'meli_message_id': message_data.get('id'),
                'pack_id': message_data.get('conversation_id', {}).get('pack_id'),
                'resource_id': message_data.get('conversation_id', {}).get('resource_id'),
                'direction': 'in',
                'sender_id': sender_id,
                'sender_name': message_data.get('from', {}).get('nickname'),
                'content': message_data.get('text', {}).get('plain', ''),
                'attachments': json.dumps(message_data.get('attachments', [])),
                'raw_data': json.dumps(message_data),
            })

            # Update config stats
            config.sudo().write({
                'total_messages_received': config.total_messages_received + 1,
                'last_message_date': message_log.create_date,
            })

            # Process with AI if enabled
            if config.auto_reply_enabled and config.agent_id:
                message_log.process_with_ai()

            return {'success': True, 'message_log_id': message_log.id}

        except Exception as e:
            _logger.exception(f"Error handling message notification: {e}")
            return {'success': False, 'error': str(e)}

    def _handle_question_notification(self, config, payload):
        """Handle question notification"""
        if not config.reply_to_questions:
            return {'success': True, 'message': 'Questions disabled'}

        resource = payload.get('resource', '')

        try:
            # Fetch question
            response = config._make_api_request('GET', resource)

            if not response.ok:
                return {'success': False, 'error': response.text}

            question_data = response.json()

            # Create as message log
            message_log = self.env['ai.meli.message.log'].create({
                'config_id': config.id,
                'meli_message_id': str(question_data.get('id')),
                'resource_id': question_data.get('item_id'),
                'direction': 'in',
                'sender_id': str(question_data.get('from', {}).get('id', '')),
                'content': question_data.get('text', ''),
                'raw_data': json.dumps(question_data),
            })

            # Process with AI
            if config.auto_reply_enabled and config.agent_id:
                # Add item context
                item_id = question_data.get('item_id')
                if item_id:
                    # Could fetch item details here
                    pass

                message_log.process_with_ai()

            return {'success': True, 'message_log_id': message_log.id}

        except Exception as e:
            _logger.exception(f"Error handling question: {e}")
            return {'success': False, 'error': str(e)}

    def _handle_order_notification(self, config, payload):
        """Handle order notification - just log for now"""
        if not config.reply_to_orders:
            return {'success': True, 'message': 'Order messages disabled'}

        # Order notifications can trigger message fetching
        # but we mainly handle them through the messaging API
        return {'success': True, 'message': 'Order notification logged'}


class MeliChannelAdapter(models.AbstractModel):
    _inherit = 'ai.channel.adapter'

    @api.model
    def get_adapter(self, channel_type):
        """Override to return MercadoLibre adapter"""
        if channel_type == 'mercadolibre':
            return MeliAdapter(self.env)
        return super().get_adapter(channel_type)


class MeliAdapter:
    """MercadoLibre specific message adapter"""

    MAX_LENGTH = 2000

    def __init__(self, env):
        self.env = env

    def parse_incoming(self, raw_message, context=None):
        """Parse MercadoLibre message format"""
        # Handle different MercadoLibre message structures
        if isinstance(raw_message.get('text'), dict):
            text = raw_message['text'].get('plain', '')
        else:
            text = raw_message.get('text', '')

        conversation_id = raw_message.get('conversation_id', {})
        if isinstance(conversation_id, dict):
            pack_id = conversation_id.get('pack_id')
            resource_id = conversation_id.get('resource_id')
        else:
            pack_id = raw_message.get('pack_id')
            resource_id = raw_message.get('resource_id')

        return {
            'text': text,
            'sender_id': str(raw_message.get('from', {}).get('user_id', '')),
            'conversation_id': pack_id,
            'attachments': raw_message.get('attachments', []),
            'metadata': {
                'message_id': raw_message.get('id'),
                'resource_id': resource_id,
                'item_id': raw_message.get('item_id'),
                'status': raw_message.get('status'),
                'site_id': raw_message.get('site_id'),
            },
        }

    def format_outgoing(self, text, context=None):
        """Format response for MercadoLibre"""
        import re

        # Strip markdown - MercadoLibre only supports plain text
        text = self._strip_formatting(text)

        # Truncate to limit
        if len(text) > self.MAX_LENGTH:
            text = text[:self.MAX_LENGTH - 3] + '...'

        return {
            'text': text,
            'format': 'plain',
            'plain': text,
        }

    def _strip_formatting(self, text):
        """Remove markdown/HTML formatting"""
        import re
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        # Code
        text = re.sub(r'`(.+?)`', r'\1', text)
        # Links - keep text, remove URL
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        # Headers
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        # Lists - convert to simple bullets
        text = re.sub(r'^\s*[-*]\s*', '• ', text, flags=re.MULTILINE)
        # HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        return text
