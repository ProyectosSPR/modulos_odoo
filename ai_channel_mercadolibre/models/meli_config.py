# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class MeliConfig(models.Model):
    _name = 'ai.meli.config'
    _description = 'MercadoLibre API Configuration'
    _order = 'name'

    name = fields.Char(string='Account Name', required=True)
    active = fields.Boolean(default=True)

    # === NUEVA INTEGRACION CON mercadolibre_connector ===
    # Usar cuenta de mercadolibre_connector para tokens siempre actualizados
    ml_account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta MercadoLibre',
        domain="[('state', '=', 'connected'), ('active', '=', True)]",
        help='Cuenta de MercadoLibre Connector con token siempre actualizado',
    )
    use_connector_token = fields.Boolean(
        string='Usar Token de Connector',
        default=True,
        help='Si esta activo, usa el token de mercadolibre_connector (recomendado). '
             'Si no, usa las credenciales propias de este registro.',
    )

    # API Credentials (solo si no usa connector)
    app_id = fields.Char(
        string='App ID',
        help='Solo necesario si no usa token de mercadolibre_connector',
    )
    client_secret = fields.Char(
        string='Client Secret',
        groups='ai_agent_core.group_ai_admin',
        help='Solo necesario si no usa token de mercadolibre_connector',
    )

    # OAuth tokens (solo si no usa connector - DEPRECADO)
    access_token = fields.Char(
        string='Access Token (Deprecado)',
        groups='ai_agent_core.group_ai_admin',
        help='Deprecado: Usar mercadolibre_connector en su lugar',
    )
    refresh_token = fields.Char(
        string='Refresh Token (Deprecado)',
        groups='ai_agent_core.group_ai_admin',
        help='Deprecado: Usar mercadolibre_connector en su lugar',
    )
    token_expiry = fields.Datetime(
        string='Token Expiry (Deprecado)',
        help='Deprecado: Usar mercadolibre_connector en su lugar',
    )

    # MercadoLibre user info (computados desde ml_account_id si usa connector)
    meli_user_id = fields.Char(
        string='MercadoLibre User ID',
        compute='_compute_meli_info',
        store=True,
        readonly=False,
    )
    meli_nickname = fields.Char(
        string='Nickname',
        compute='_compute_meli_info',
        store=True,
        readonly=False,
    )
    meli_site_id = fields.Char(string='Site ID', default='MLM')

    @api.depends('ml_account_id', 'use_connector_token')
    def _compute_meli_info(self):
        """Obtener info de ML desde mercadolibre_connector."""
        for record in self:
            if record.use_connector_token and record.ml_account_id:
                record.meli_user_id = record.ml_account_id.ml_user_id
                record.meli_nickname = record.ml_account_id.ml_nickname
            # Si no usa connector, mantener los valores actuales

    # AI Agent configuration
    agent_id = fields.Many2one(
        'ai.agent',
        string='AI Agent',
        help='Agent to handle incoming messages'
    )

    channel_id = fields.Many2one(
        'ai.channel',
        string='Channel',
        domain=[('channel_type', '=', 'mercadolibre')]
    )

    # Auto-reply settings
    auto_reply_enabled = fields.Boolean(
        string='Auto-Reply Enabled',
        default=True
    )
    auto_reply_delay = fields.Integer(
        string='Reply Delay (seconds)',
        default=5,
        help='Delay before sending auto-reply'
    )
    working_hours_only = fields.Boolean(
        string='Working Hours Only',
        default=False
    )
    working_hour_start = fields.Float(string='Start Hour', default=9.0)
    working_hour_end = fields.Float(string='End Hour', default=18.0)

    # Message filters
    reply_to_questions = fields.Boolean(
        string='Reply to Questions',
        default=True
    )
    reply_to_orders = fields.Boolean(
        string='Reply to Order Messages',
        default=True
    )

    # Webhook
    webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_webhook_url'
    )
    webhook_configured = fields.Boolean(
        string='Webhook Configured',
        readonly=True
    )

    # Statistics
    total_messages_received = fields.Integer(
        string='Messages Received',
        readonly=True,
        default=0
    )
    total_replies_sent = fields.Integer(
        string='Replies Sent',
        readonly=True,
        default=0
    )
    last_message_date = fields.Datetime(
        string='Last Message',
        readonly=True
    )

    # Connection status
    connection_status = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], string='Status', default='disconnected', readonly=True)
    last_error = fields.Text(string='Last Error', readonly=True)

    @api.depends('app_id')
    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.webhook_url = f"{base_url}/ai/meli/webhook/{record.id}"

    def _get_api_url(self, endpoint):
        """Get full API URL"""
        base = 'https://api.mercadolibre.com'
        return f"{base}{endpoint}"

    def _get_access_token(self):
        """
        Obtener token de acceso valido.
        Usa mercadolibre_connector si esta configurado, sino el token propio.

        Returns:
            str: Access token valido

        Raises:
            UserError si no hay token disponible
        """
        self.ensure_one()

        # Usar token de mercadolibre_connector (recomendado)
        if self.use_connector_token and self.ml_account_id:
            try:
                token = self.ml_account_id.get_valid_token()
                if token:
                    self.write({
                        'connection_status': 'connected',
                        'last_error': False,
                    })
                    return token
            except Exception as e:
                _logger.error(f"Error obteniendo token de connector: {e}")
                self.write({
                    'connection_status': 'error',
                    'last_error': str(e),
                })
                raise UserError(f"Error con token de mercadolibre_connector: {e}")

        # Fallback: usar token propio (deprecado)
        if self._refresh_token_if_needed_legacy():
            return self.access_token

        raise UserError("No hay token de acceso disponible. Configure una cuenta de MercadoLibre Connector.")

    def _refresh_token_if_needed_legacy(self):
        """
        [DEPRECADO] Refrescar token propio si esta expirado.
        Se mantiene para compatibilidad con configuraciones existentes.
        """
        self.ensure_one()

        if not self.token_expiry or not self.refresh_token:
            return False

        # Check if token expires in next 5 minutes
        if self.token_expiry > datetime.now() + timedelta(minutes=5):
            return True

        try:
            response = requests.post(
                self._get_api_url('/oauth/token'),
                data={
                    'grant_type': 'refresh_token',
                    'client_id': self.app_id,
                    'client_secret': self.client_secret,
                    'refresh_token': self.refresh_token,
                }
            )

            if response.ok:
                data = response.json()
                self.write({
                    'access_token': data['access_token'],
                    'refresh_token': data.get('refresh_token', self.refresh_token),
                    'token_expiry': datetime.now() + timedelta(seconds=data['expires_in']),
                    'connection_status': 'connected',
                    'last_error': False,
                })
                return True
            else:
                self.write({
                    'connection_status': 'error',
                    'last_error': response.text
                })
                return False

        except Exception as e:
            self.write({
                'connection_status': 'error',
                'last_error': str(e)
            })
            return False

    def _refresh_token_if_needed(self):
        """Alias para compatibilidad. Ahora usa _get_access_token."""
        try:
            self._get_access_token()
            return True
        except Exception:
            return False

    def _make_api_request(self, method, endpoint, **kwargs):
        """Make authenticated API request"""
        self.ensure_one()

        # Obtener token (de connector o propio)
        access_token = self._get_access_token()

        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'Bearer {access_token}'

        url = self._get_api_url(endpoint)

        response = requests.request(method, url, headers=headers, **kwargs)

        if response.status_code == 401:
            # Token might have just expired, try to get a fresh one
            try:
                access_token = self._get_access_token()
                headers['Authorization'] = f'Bearer {access_token}'
                response = requests.request(method, url, headers=headers, **kwargs)
            except Exception as e:
                _logger.error(f"Error re-authenticating: {e}")

        return response

    def action_get_auth_url(self):
        """Get OAuth authorization URL"""
        self.ensure_one()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = f"{base_url}/ai/meli/callback"

        auth_url = (
            f"https://auth.mercadolibre.com.ar/authorization?"
            f"response_type=code&client_id={self.app_id}&redirect_uri={redirect_uri}"
        )

        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'new',
        }

    def action_test_connection(self):
        """Test API connection"""
        self.ensure_one()

        try:
            response = self._make_api_request('GET', '/users/me')

            if response.ok:
                data = response.json()
                self.write({
                    'meli_user_id': str(data['id']),
                    'meli_nickname': data.get('nickname'),
                    'meli_site_id': data.get('site_id'),
                    'connection_status': 'connected',
                    'last_error': False,
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Connection Successful',
                        'message': f"Connected as {data.get('nickname')}",
                        'type': 'success',
                    }
                }
            else:
                raise UserError(response.text)

        except Exception as e:
            self.write({
                'connection_status': 'error',
                'last_error': str(e)
            })
            raise UserError(f"Connection failed: {str(e)}")

    def action_configure_webhook(self):
        """Configure webhook notifications"""
        self.ensure_one()

        try:
            # Subscribe to messages topic
            response = self._make_api_request(
                'POST',
                f'/users/{self.meli_user_id}/applications/{self.app_id}/callbacks',
                json={
                    'topic': 'messages',
                    'url': self.webhook_url,
                }
            )

            if response.ok or response.status_code == 201:
                self.webhook_configured = True
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Webhook Configured',
                        'message': 'Now listening for messages',
                        'type': 'success',
                    }
                }
            else:
                raise UserError(response.text)

        except Exception as e:
            raise UserError(f"Webhook configuration failed: {str(e)}")

    def send_message(self, pack_id, text, attachments=None):
        """
        Send message to MercadoLibre conversation

        Args:
            pack_id: Message pack/conversation ID
            text: Message text
            attachments: Optional list of attachment URLs

        Returns:
            API response
        """
        self.ensure_one()

        payload = {
            'from': {
                'user_id': int(self.meli_user_id)
            },
            'to': {
                'resource_id': pack_id,
                'site_id': self.meli_site_id,
            },
            'text': {
                'plain': text[:2000]  # ML limit
            }
        }

        if attachments:
            payload['attachments'] = attachments

        response = self._make_api_request(
            'POST',
            '/messages/packs/{}/sellers/{}/send'.format(pack_id, self.meli_user_id),
            json=payload
        )

        if response.ok:
            self.sudo().write({
                'total_replies_sent': self.total_replies_sent + 1
            })

        return response

    def get_messages(self, pack_id, limit=50):
        """
        Get messages from a conversation

        Args:
            pack_id: Message pack ID
            limit: Maximum messages

        Returns:
            List of messages
        """
        self.ensure_one()

        response = self._make_api_request(
            'GET',
            f'/messages/packs/{pack_id}/sellers/{self.meli_user_id}',
            params={'limit': limit}
        )

        if response.ok:
            return response.json().get('messages', [])
        return []

    def is_within_working_hours(self):
        """Check if current time is within working hours"""
        if not self.working_hours_only:
            return True

        now = datetime.now()
        current_hour = now.hour + now.minute / 60

        return self.working_hour_start <= current_hour <= self.working_hour_end


class MeliMessageLog(models.Model):
    _name = 'ai.meli.message.log'
    _description = 'MercadoLibre Message Log'
    _order = 'create_date desc'

    config_id = fields.Many2one(
        'ai.meli.config',
        string='Account',
        required=True,
        ondelete='cascade'
    )

    # Message identifiers
    meli_message_id = fields.Char(string='Message ID')
    pack_id = fields.Char(string='Pack ID')
    resource_id = fields.Char(string='Resource ID')

    # Message content
    direction = fields.Selection([
        ('in', 'Incoming'),
        ('out', 'Outgoing'),
    ], string='Direction')

    sender_id = fields.Char(string='Sender ID')
    sender_name = fields.Char(string='Sender Name')

    content = fields.Text(string='Content')
    attachments = fields.Text(string='Attachments')

    # AI processing
    ai_processed = fields.Boolean(string='AI Processed', default=False)
    ai_response = fields.Text(string='AI Response')
    conversation_id = fields.Many2one('ai.conversation', string='Conversation')

    # Status
    status = fields.Selection([
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('replied', 'Replied'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ], string='Status', default='received')

    error_message = fields.Text(string='Error')

    # Metadata
    raw_data = fields.Text(string='Raw Data')

    def process_with_ai(self):
        """Process message with AI agent"""
        self.ensure_one()

        if self.ai_processed or self.direction != 'in':
            return False

        config = self.config_id
        if not config.agent_id or not config.auto_reply_enabled:
            self.write({'status': 'skipped'})
            return False

        if not config.is_within_working_hours():
            self.write({'status': 'skipped'})
            return False

        self.write({'status': 'processing'})

        try:
            # Build context
            context = {
                'channel': 'mercadolibre',
                'channel_reference': self.pack_id,
                'external_user_id': self.sender_id,
                'external_user_name': self.sender_name,
                'resource_id': self.resource_id,
            }

            # Process with agent
            result = config.agent_id.process_message(
                message=self.content,
                context=context,
            )

            response_text = result.get('response', '')

            if response_text:
                # Send reply
                response = config.send_message(self.pack_id, response_text)

                if response.ok:
                    self.write({
                        'ai_processed': True,
                        'ai_response': response_text,
                        'conversation_id': result.get('conversation_id'),
                        'status': 'replied',
                    })
                    return True
                else:
                    raise Exception(response.text)

        except Exception as e:
            _logger.exception(f"AI processing error for message {self.id}")
            self.write({
                'status': 'failed',
                'error_message': str(e),
            })

        return False
