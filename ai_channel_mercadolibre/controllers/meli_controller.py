# -*- coding: utf-8 -*-
import json
import logging
import hmac
import hashlib
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MeliController(http.Controller):

    @http.route('/meli/oauth/callback', type='http', auth='public', csrf=False)
    def oauth_callback(self, **kwargs):
        """
        OAuth callback endpoint for MercadoLibre authorization

        URL to configure in MercadoLibre app:
        https://your-odoo-domain.com/meli/oauth/callback
        """
        code = kwargs.get('code')
        state = kwargs.get('state')  # Contains config_id
        error = kwargs.get('error')

        if error:
            _logger.error(f"MercadoLibre OAuth error: {error}")
            return request.render('ai_channel_mercadolibre.oauth_error', {
                'error': error,
                'error_description': kwargs.get('error_description', ''),
            })

        if not code or not state:
            return request.render('ai_channel_mercadolibre.oauth_error', {
                'error': 'Missing parameters',
                'error_description': 'Code or state parameter is missing',
            })

        try:
            config_id = int(state)
            config = request.env['ai.meli.config'].sudo().browse(config_id)

            if not config.exists():
                return request.render('ai_channel_mercadolibre.oauth_error', {
                    'error': 'Invalid configuration',
                    'error_description': 'Configuration not found',
                })

            # Exchange code for tokens
            result = config._exchange_code_for_token(code)

            if result.get('success'):
                return request.render('ai_channel_mercadolibre.oauth_success', {
                    'config_name': config.name,
                    'user_id': config.meli_user_id,
                })
            else:
                return request.render('ai_channel_mercadolibre.oauth_error', {
                    'error': 'Token exchange failed',
                    'error_description': result.get('error', 'Unknown error'),
                })

        except Exception as e:
            _logger.exception(f"OAuth callback error: {e}")
            return request.render('ai_channel_mercadolibre.oauth_error', {
                'error': 'Server error',
                'error_description': str(e),
            })

    @http.route('/meli/webhook/<int:config_id>', type='json', auth='public',
                methods=['POST'], csrf=False)
    def webhook(self, config_id, **kwargs):
        """
        Webhook endpoint for MercadoLibre notifications

        URL to configure in MercadoLibre app:
        https://your-odoo-domain.com/meli/webhook/<config_id>
        """
        try:
            config = request.env['ai.meli.config'].sudo().browse(config_id)

            if not config.exists() or not config.active:
                _logger.warning(f"Webhook for invalid config: {config_id}")
                return {'status': 'error', 'message': 'Invalid configuration'}

            # Get payload
            payload = request.jsonrequest

            # Verify signature if secret is configured
            if config.webhook_secret:
                signature = request.httprequest.headers.get('X-Signature')
                if not self._verify_signature(payload, config.webhook_secret, signature):
                    _logger.warning(f"Invalid webhook signature for config {config_id}")
                    return {'status': 'error', 'message': 'Invalid signature'}

            # Log the webhook
            _logger.info(f"MercadoLibre webhook received: {payload.get('topic')} - {payload.get('resource')}")

            # Process the notification
            handler = request.env['ai.meli.message.handler'].sudo()
            result = handler.process_webhook(config_id, payload)

            return {'status': 'ok', 'result': result}

        except Exception as e:
            _logger.exception(f"Webhook processing error: {e}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/meli/webhook/<int:config_id>', type='http', auth='public',
                methods=['GET'], csrf=False)
    def webhook_verify(self, config_id, **kwargs):
        """
        Webhook verification endpoint (GET request from MercadoLibre)
        """
        # MercadoLibre may send a verification request
        challenge = kwargs.get('challenge')
        if challenge:
            return challenge
        return 'OK'

    def _verify_signature(self, payload, secret, signature):
        """Verify MercadoLibre webhook signature"""
        if not signature:
            return False

        try:
            payload_str = json.dumps(payload, separators=(',', ':'))
            expected = hmac.new(
                secret.encode('utf-8'),
                payload_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    @http.route('/meli/test/<int:config_id>', type='json', auth='user', methods=['POST'])
    def test_connection(self, config_id, **kwargs):
        """Test MercadoLibre API connection"""
        config = request.env['ai.meli.config'].browse(config_id)

        if not config.exists():
            return {'success': False, 'error': 'Configuration not found'}

        return config.test_connection()

    @http.route('/meli/conversations/<int:config_id>', type='json', auth='user', methods=['POST'])
    def get_conversations(self, config_id, **kwargs):
        """Get recent conversations from MercadoLibre"""
        config = request.env['ai.meli.config'].browse(config_id)

        if not config.exists():
            return {'success': False, 'error': 'Configuration not found'}

        limit = kwargs.get('limit', 20)
        offset = kwargs.get('offset', 0)

        try:
            response = config._make_api_request(
                'GET',
                f'/messages/packs/{config.meli_user_id}/sellers/{config.meli_user_id}',
                params={'limit': limit, 'offset': offset}
            )

            if response.ok:
                return {'success': True, 'data': response.json()}
            else:
                return {'success': False, 'error': response.text}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/meli/send_message/<int:config_id>', type='json', auth='user', methods=['POST'])
    def send_message(self, config_id, **kwargs):
        """Send a message through MercadoLibre"""
        config = request.env['ai.meli.config'].browse(config_id)

        if not config.exists():
            return {'success': False, 'error': 'Configuration not found'}

        pack_id = kwargs.get('pack_id')
        text = kwargs.get('text')

        if not pack_id or not text:
            return {'success': False, 'error': 'pack_id and text are required'}

        return config.send_message(pack_id, text)
