# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class AIPlaygroundController(http.Controller):

    @http.route('/ai/playground/send', type='json', auth='user', methods=['POST'])
    def playground_send(self, playground_id, message):
        """
        AJAX endpoint for sending messages from playground

        Args:
            playground_id: ID of the playground session
            message: Message text to send

        Returns:
            JSON response with AI reply
        """
        playground = request.env['ai.playground'].browse(int(playground_id))
        if not playground.exists():
            return {'success': False, 'error': 'Playground session not found'}

        result = playground.send_message(message)
        return result

    @http.route('/ai/playground/clear', type='json', auth='user', methods=['POST'])
    def playground_clear(self, playground_id):
        """
        AJAX endpoint for clearing playground chat

        Args:
            playground_id: ID of the playground session

        Returns:
            JSON response
        """
        playground = request.env['ai.playground'].browse(int(playground_id))
        if not playground.exists():
            return {'success': False, 'error': 'Playground session not found'}

        playground.action_clear_chat()
        return {'success': True}

    @http.route('/ai/playground/messages', type='json', auth='user', methods=['POST'])
    def playground_messages(self, playground_id):
        """
        AJAX endpoint for getting playground messages

        Args:
            playground_id: ID of the playground session

        Returns:
            List of messages
        """
        playground = request.env['ai.playground'].browse(int(playground_id))
        if not playground.exists():
            return {'success': False, 'error': 'Playground session not found'}

        messages = []
        for msg in playground.message_ids:
            messages.append({
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'time': msg.create_date.strftime('%H:%M:%S') if msg.create_date else '',
                'processing_time': msg.processing_time,
            })

        return {
            'success': True,
            'messages': messages,
            'debug': {
                'last_prompt': playground.last_system_prompt,
                'tools_called': playground.last_tools_called,
                'triggered_rules': playground.last_triggered_rules,
                'processing_time': playground.last_processing_time,
            } if playground.show_debug else None
        }

    @http.route('/ai/webhook/<string:token>', type='json', auth='public', methods=['POST'], csrf=False)
    def webhook_handler(self, token, **kwargs):
        """
        Public webhook endpoint for incoming messages

        Args:
            token: Webhook authentication token
            **kwargs: Request payload

        Returns:
            JSON response
        """
        try:
            # Get request data
            if request.httprequest.content_type == 'application/json':
                payload = request.get_json_data()
            else:
                payload = kwargs

            headers = dict(request.httprequest.headers)

            # Route through message router
            router = request.env['ai.message.router'].sudo()
            result = router.process_webhook(token, payload, headers)

            return result

        except Exception as e:
            _logger.exception(f"Webhook error for token {token}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/ai/chat/widget', type='http', auth='public', website=True)
    def chat_widget(self, **kwargs):
        """
        Public chat widget endpoint

        Args:
            agent_id: Optional agent ID to use

        Returns:
            HTML chat widget
        """
        agent_id = kwargs.get('agent_id')

        if agent_id:
            agent = request.env['ai.agent'].sudo().browse(int(agent_id))
        else:
            # Get default web agent
            agent = request.env['ai.agent'].sudo().search([
                ('active', '=', True),
                ('channel_ids.channel_type', '=', 'web')
            ], limit=1)

        if not agent:
            return "No AI agent configured for web chat"

        return request.render('ai_playground.chat_widget_template', {
            'agent': agent,
        })
