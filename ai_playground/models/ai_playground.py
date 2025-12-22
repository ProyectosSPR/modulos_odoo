# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)


class AIPlayground(models.Model):
    _name = 'ai.playground'
    _description = 'AI Testing Playground'
    _order = 'create_date desc'

    name = fields.Char(
        string='Session Name',
        default=lambda self: f"Test Session {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    # Agent configuration
    agent_id = fields.Many2one(
        'ai.agent',
        string='Agent',
        required=True,
        domain=[('active', '=', True)]
    )

    # Simulated channel
    simulated_channel = fields.Selection([
        ('mercadolibre', 'MercadoLibre'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('email', 'Email'),
        ('web', 'Web'),
    ], string='Simulate Channel', default='web')

    # Test context
    test_partner_id = fields.Many2one(
        'res.partner',
        string='Test Customer',
        help='Simulate conversation with this customer'
    )

    test_context = fields.Text(
        string='Additional Context',
        help='JSON with additional context variables',
        default='{}'
    )

    # Chat history
    message_ids = fields.One2many(
        'ai.playground.message',
        'playground_id',
        string='Messages'
    )

    # Linked conversation
    conversation_id = fields.Many2one(
        'ai.conversation',
        string='Conversation',
        readonly=True
    )

    # Debug options
    show_debug = fields.Boolean(
        string='Show Debug Info',
        default=True
    )

    # Debug output
    last_system_prompt = fields.Text(
        string='Last System Prompt',
        readonly=True
    )
    last_tools_called = fields.Text(
        string='Last Tools Called',
        readonly=True
    )
    last_raw_response = fields.Text(
        string='Last Raw Response',
        readonly=True
    )
    last_triggered_rules = fields.Text(
        string='Triggered Rules',
        readonly=True
    )
    last_processing_time = fields.Float(
        string='Processing Time (s)',
        readonly=True
    )

    def action_send_message(self):
        """Open wizard to send a message"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Send Message',
            'res_model': 'ai.playground.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_playground_id': self.id,
            }
        }

    def send_message(self, message_text):
        """
        Send a message to the AI agent and get response

        Args:
            message_text: User message

        Returns:
            Response dictionary
        """
        self.ensure_one()

        if not message_text:
            return {'error': 'Empty message'}

        # Create user message
        self.env['ai.playground.message'].create({
            'playground_id': self.id,
            'role': 'user',
            'content': message_text
        })

        # Build context
        context_data = {
            'channel': self.simulated_channel,
            'channel_reference': f'playground_{self.id}',
        }

        if self.test_partner_id:
            context_data['partner_id'] = self.test_partner_id.id
            context_data['partner_name'] = self.test_partner_id.name
            context_data['external_user_name'] = self.test_partner_id.name

        # Merge additional context
        if self.test_context:
            try:
                extra = json.loads(self.test_context)
                context_data.update(extra)
            except json.JSONDecodeError:
                pass

        # Process with agent
        try:
            result = self.agent_id.process_message(
                message=message_text,
                context=context_data,
                conversation=self.conversation_id
            )

            response_text = result.get('response', 'No response generated')

            # Store conversation reference
            if result.get('conversation_id') and not self.conversation_id:
                self.conversation_id = result.get('conversation_id')

            # Create assistant message
            self.env['ai.playground.message'].create({
                'playground_id': self.id,
                'role': 'assistant',
                'content': response_text,
                'processing_time': result.get('processing_time', 0),
                'tools_called': json.dumps(result.get('tools_called', []), indent=2),
            })

            # Store debug info
            if self.show_debug:
                debug = result.get('debug', {})
                self.write({
                    'last_system_prompt': debug.get('system_prompt', ''),
                    'last_tools_called': json.dumps(result.get('tools_called', []), indent=2),
                    'last_raw_response': debug.get('raw_result', str(result)),
                    'last_triggered_rules': ', '.join(result.get('triggered_rules', [])),
                    'last_processing_time': result.get('processing_time', 0),
                })

            return {
                'success': True,
                'response': response_text,
                'processing_time': result.get('processing_time', 0),
            }

        except Exception as e:
            _logger.exception(f"Playground error: {e}")

            # Create error message
            self.env['ai.playground.message'].create({
                'playground_id': self.id,
                'role': 'system',
                'content': f"Error: {str(e)}"
            })

            return {
                'success': False,
                'error': str(e)
            }

    def action_clear_chat(self):
        """Clear all messages"""
        self.ensure_one()
        self.message_ids.unlink()
        self.conversation_id = False
        self.write({
            'last_system_prompt': False,
            'last_tools_called': False,
            'last_raw_response': False,
            'last_triggered_rules': False,
            'last_processing_time': 0,
        })
        return True

    def action_preview_prompt(self):
        """Preview the system prompt"""
        self.ensure_one()

        context_data = {
            'channel': self.simulated_channel,
            'partner_name': self.test_partner_id.name if self.test_partner_id else 'Test Customer',
        }

        if self.test_context:
            try:
                extra = json.loads(self.test_context)
                context_data.update(extra)
            except json.JSONDecodeError:
                pass

        prompt = self.agent_id.build_system_prompt(context_data)

        return {
            'type': 'ir.actions.act_window',
            'name': 'System Prompt Preview',
            'res_model': 'ai.agent.prompt.preview',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_agent_id': self.agent_id.id,
                'default_prompt_preview': prompt,
            }
        }

    def action_view_conversation(self):
        """View the linked conversation"""
        self.ensure_one()
        if not self.conversation_id:
            return {'type': 'ir.actions.act_window_close'}

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.conversation',
            'res_id': self.conversation_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class AIPlaygroundMessage(models.Model):
    _name = 'ai.playground.message'
    _description = 'AI Playground Message'
    _order = 'create_date, id'

    playground_id = fields.Many2one(
        'ai.playground',
        string='Playground',
        required=True,
        ondelete='cascade'
    )

    role = fields.Selection([
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ], string='Role', required=True)

    content = fields.Text(string='Content', required=True)

    # Debug info
    processing_time = fields.Float(string='Processing Time (s)')
    tools_called = fields.Text(string='Tools Called')

    create_date = fields.Datetime(string='Time', readonly=True)


class AIPlaygroundSendWizard(models.TransientModel):
    _name = 'ai.playground.send.wizard'
    _description = 'Send Message Wizard'

    playground_id = fields.Many2one(
        'ai.playground',
        string='Playground',
        required=True
    )

    message = fields.Text(
        string='Message',
        required=True,
        help='Enter your message to send to the AI agent'
    )

    # Quick message options
    quick_message = fields.Selection([
        ('greeting', 'Hola, buenos días'),
        ('product', '¿Tienen disponible el producto X?'),
        ('order', '¿Cuál es el estado de mi pedido?'),
        ('invoice', 'Necesito mi factura'),
        ('price', '¿Cuánto cuesta?'),
        ('stock', '¿Tienen stock disponible?'),
        ('help', 'Necesito ayuda'),
    ], string='Quick Message')

    @api.onchange('quick_message')
    def _onchange_quick_message(self):
        if self.quick_message:
            messages = {
                'greeting': 'Hola, buenos días',
                'product': '¿Tienen disponible el producto laptop HP?',
                'order': '¿Cuál es el estado de mi pedido SO001?',
                'invoice': 'Necesito que me envíen la factura de mi última compra',
                'price': '¿Cuánto cuesta el producto más vendido?',
                'stock': '¿Tienen stock disponible del producto ABC?',
                'help': 'Necesito ayuda con mi cuenta',
            }
            self.message = messages.get(self.quick_message, '')

    def action_send(self):
        """Send the message"""
        self.ensure_one()
        result = self.playground_id.send_message(self.message)

        # Refresh the playground view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.playground',
            'res_id': self.playground_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
