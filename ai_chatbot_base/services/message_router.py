# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class AIMessageRouter(models.AbstractModel):
    _name = 'ai.message.router'
    _description = 'AI Message Router Service'

    @api.model
    def route_message(self, channel_type, message_data, agent=None):
        """
        Route incoming message to appropriate agent and return formatted response

        Args:
            channel_type: Source channel type
            message_data: Raw message data from channel
            agent: Specific agent to use (optional)

        Returns:
            Formatted response for the channel
        """
        # Get adapter for channel
        adapter = self.env['ai.channel.adapter'].get_adapter(channel_type)

        # Parse incoming message
        parsed = adapter.parse_incoming(message_data)

        if not parsed.get('text'):
            _logger.warning(f"Empty message received from {channel_type}")
            return adapter.format_outgoing("No se recibió ningún mensaje.")

        # Find appropriate agent
        if not agent:
            agent = self._find_agent(channel_type, parsed)

        if not agent:
            _logger.error(f"No agent found for channel {channel_type}")
            return adapter.format_outgoing(
                "Lo siento, no hay un agente disponible para atender tu consulta."
            )

        # Build context
        context = {
            'channel': channel_type,
            'channel_reference': parsed.get('conversation_id'),
            'external_user_id': parsed.get('sender_id'),
            'external_user_name': parsed.get('metadata', {}).get('from_username'),
            'attachments': parsed.get('attachments', []),
        }

        # Add any metadata to context
        for key, value in parsed.get('metadata', {}).items():
            if key not in context:
                context[key] = value

        try:
            # Process with agent
            result = agent.process_message(
                message=parsed['text'],
                context=context
            )

            response_text = result.get('response', '')

            # Format response for channel
            return adapter.format_outgoing(response_text, context)

        except Exception as e:
            _logger.exception(f"Error routing message: {e}")
            return adapter.format_outgoing(
                "Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta nuevamente."
            )

    def _find_agent(self, channel_type, parsed_message):
        """
        Find the best agent for the message

        Args:
            channel_type: Channel type
            parsed_message: Parsed message data

        Returns:
            ai.agent record or False
        """
        # First try to find agent by channel
        channel = self.env['ai.channel'].search([
            ('channel_type', '=', channel_type),
            ('active', '=', True)
        ], limit=1)

        if channel and channel.agent_ids:
            # Return first active agent assigned to channel
            return channel.agent_ids.filtered('active')[:1]

        # Fallback to default agent for channel type
        return self.env['ai.agent'].get_default_agent_for_channel(channel_type)

    @api.model
    def send_response(self, channel_type, conversation_id, response_data):
        """
        Send a response back to a channel

        This method should be overridden by channel-specific modules
        to actually send the response through the channel's API.

        Args:
            channel_type: Target channel type
            conversation_id: Channel-specific conversation ID
            response_data: Formatted response from route_message

        Returns:
            Boolean success
        """
        # This is a hook for channel modules to implement actual sending
        method_name = f'_send_to_{channel_type}'
        if hasattr(self, method_name):
            return getattr(self, method_name)(conversation_id, response_data)

        _logger.warning(f"No send method implemented for channel {channel_type}")
        return False

    @api.model
    def process_webhook(self, webhook_token, payload, headers=None):
        """
        Process incoming webhook request

        Args:
            webhook_token: Webhook authentication token
            payload: Request payload (dict)
            headers: Request headers (dict)

        Returns:
            Response dict
        """
        # Find webhook configuration
        webhook = self.env['ai.webhook'].sudo().search([
            ('webhook_token', '=', webhook_token),
            ('active', '=', True)
        ], limit=1)

        if not webhook:
            _logger.warning(f"Unknown webhook token: {webhook_token}")
            return {'success': False, 'error': 'Invalid webhook token'}

        # Verify signature if required
        if webhook.auth_type == 'signature':
            import json
            signature = headers.get('X-Signature') or headers.get('X-Hub-Signature')
            if not webhook.verify_signature(json.dumps(payload).encode(), signature or ''):
                return {'success': False, 'error': 'Invalid signature'}

        # Process through webhook
        return webhook.process_incoming(payload, headers)

    @api.model
    def broadcast_message(self, channel_types, message, agent=None):
        """
        Send a message to multiple channels

        Args:
            channel_types: List of channel types
            message: Message to send
            agent: Agent to attribute message to

        Returns:
            Dict with results per channel
        """
        results = {}
        for channel_type in channel_types:
            adapter = self.env['ai.channel.adapter'].get_adapter(channel_type)
            formatted = adapter.format_outgoing(message)
            results[channel_type] = {
                'formatted': formatted,
                'sent': False,  # Would be True after actual send
            }
        return results
