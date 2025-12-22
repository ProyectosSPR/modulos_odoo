# -*- coding: utf-8 -*-
from odoo import models, fields, api
import uuid
import hashlib
import hmac
import logging

_logger = logging.getLogger(__name__)


class AIWebhook(models.Model):
    _name = 'ai.webhook'
    _description = 'AI Webhook Configuration'
    _order = 'name'

    name = fields.Char(string='Webhook Name', required=True)
    active = fields.Boolean(default=True)

    # Channel configuration
    channel_type = fields.Selection([
        ('mercadolibre', 'MercadoLibre'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('custom', 'Custom'),
    ], string='Channel Type', required=True)

    channel_id = fields.Many2one(
        'ai.channel',
        string='Channel',
        domain="[('channel_type', '=', channel_type)]"
    )

    agent_id = fields.Many2one(
        'ai.agent',
        string='Default Agent',
        help='Agent to handle incoming messages'
    )

    # Webhook URL and security
    webhook_token = fields.Char(
        string='Webhook Token',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False
    )

    webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_webhook_url',
        store=False
    )

    secret_key = fields.Char(
        string='Secret Key',
        groups='ai_agent_core.group_ai_admin',
        help='Used to verify webhook signatures'
    )

    # Authentication
    auth_type = fields.Selection([
        ('none', 'None'),
        ('token', 'Bearer Token'),
        ('signature', 'Signature Verification'),
        ('basic', 'Basic Auth'),
    ], string='Authentication', default='token')

    auth_token = fields.Char(
        string='Auth Token',
        groups='ai_agent_core.group_ai_admin'
    )

    # Request configuration
    request_method = fields.Selection([
        ('POST', 'POST'),
        ('GET', 'GET'),
    ], string='Method', default='POST')

    # Message field mapping (JSON paths)
    message_field_path = fields.Char(
        string='Message Field Path',
        default='message.text',
        help='JSON path to message text (e.g., message.text)'
    )
    sender_field_path = fields.Char(
        string='Sender Field Path',
        default='from.id',
        help='JSON path to sender ID'
    )
    conversation_field_path = fields.Char(
        string='Conversation Field Path',
        default='conversation_id',
        help='JSON path to conversation ID'
    )

    # Statistics
    total_requests = fields.Integer(string='Total Requests', default=0)
    successful_requests = fields.Integer(string='Successful', default=0)
    failed_requests = fields.Integer(string='Failed', default=0)
    last_request_date = fields.Datetime(string='Last Request')

    # Logging
    log_requests = fields.Boolean(
        string='Log Requests',
        default=True,
        help='Log incoming webhook requests'
    )
    log_ids = fields.One2many(
        'ai.webhook.log',
        'webhook_id',
        string='Request Logs'
    )

    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.webhook_url = f"{base_url}/ai/webhook/{record.webhook_token}"

    def action_regenerate_token(self):
        """Regenerate webhook token"""
        self.ensure_one()
        self.webhook_token = str(uuid.uuid4())
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Token Regenerated',
                'message': 'Webhook token has been regenerated. Update your integration.',
                'type': 'warning',
                'sticky': False,
            }
        }

    def verify_signature(self, payload, signature):
        """
        Verify webhook signature

        Args:
            payload: Request body bytes
            signature: Signature from request header

        Returns:
            Boolean
        """
        self.ensure_one()
        if not self.secret_key:
            return True

        expected = hmac.new(
            self.secret_key.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def extract_message_data(self, payload):
        """
        Extract message data from webhook payload

        Args:
            payload: Parsed JSON payload

        Returns:
            Dictionary with message, sender_id, conversation_id
        """
        self.ensure_one()

        def get_nested_value(data, path):
            """Get value from nested dict using dot notation"""
            keys = path.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    value = value[int(key)] if int(key) < len(value) else None
                else:
                    return None
            return value

        return {
            'message': get_nested_value(payload, self.message_field_path),
            'sender_id': get_nested_value(payload, self.sender_field_path),
            'conversation_id': get_nested_value(payload, self.conversation_field_path),
            'raw_payload': payload,
        }

    def process_incoming(self, payload, headers=None):
        """
        Process incoming webhook request

        Args:
            payload: Parsed JSON payload
            headers: Request headers

        Returns:
            Response dictionary
        """
        self.ensure_one()
        headers = headers or {}

        # Update statistics
        self.sudo().write({
            'total_requests': self.total_requests + 1,
            'last_request_date': fields.Datetime.now(),
        })

        try:
            # Extract message data
            message_data = self.extract_message_data(payload)

            if not message_data.get('message'):
                raise ValueError("No message found in payload")

            # Get or use default agent
            agent = self.agent_id
            if not agent:
                agent = self.env['ai.agent'].get_default_agent_for_channel(self.channel_type)

            if not agent:
                raise ValueError(f"No agent configured for channel {self.channel_type}")

            # Build context
            context = {
                'channel': self.channel_type,
                'channel_reference': message_data.get('conversation_id'),
                'external_user_id': message_data.get('sender_id'),
                'webhook_id': self.id,
            }

            # Process with agent
            result = agent.process_message(
                message=message_data['message'],
                context=context
            )

            # Log success
            if self.log_requests:
                self._create_log(payload, result, success=True)

            self.sudo().write({
                'successful_requests': self.successful_requests + 1,
            })

            return {
                'success': True,
                'response': result.get('response'),
                'conversation_id': result.get('conversation_id'),
            }

        except Exception as e:
            _logger.exception(f"Webhook processing error: {e}")

            if self.log_requests:
                self._create_log(payload, {'error': str(e)}, success=False)

            self.sudo().write({
                'failed_requests': self.failed_requests + 1,
            })

            return {
                'success': False,
                'error': str(e),
            }

    def _create_log(self, request_data, response_data, success=True):
        """Create webhook log entry"""
        import json
        self.env['ai.webhook.log'].sudo().create({
            'webhook_id': self.id,
            'request_data': json.dumps(request_data, indent=2, default=str),
            'response_data': json.dumps(response_data, indent=2, default=str),
            'success': success,
        })


class AIWebhookLog(models.Model):
    _name = 'ai.webhook.log'
    _description = 'AI Webhook Request Log'
    _order = 'create_date desc'

    webhook_id = fields.Many2one(
        'ai.webhook',
        string='Webhook',
        required=True,
        ondelete='cascade'
    )

    request_data = fields.Text(string='Request Data')
    response_data = fields.Text(string='Response Data')
    success = fields.Boolean(string='Success')
    create_date = fields.Datetime(string='Date', readonly=True)

    @api.autovacuum
    def _gc_old_logs(self):
        """Garbage collect old logs (keep last 30 days)"""
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=30)
        self.search([('create_date', '<', cutoff)]).unlink()
