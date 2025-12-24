# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

ML_MESSAGE_CHAR_LIMIT = 350


class MercadolibreMessageCompose(models.TransientModel):
    _name = 'mercadolibre.message.compose'
    _description = 'Wizard Componer Mensaje ML'

    # Contexto
    conversation_id = fields.Many2one(
        'mercadolibre.conversation',
        string='Conversación',
        required=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True
    )
    ml_pack_id = fields.Char(
        string='Pack ID',
        required=True
    )
    ml_order_id = fields.Many2one(
        'mercadolibre.order',
        string='Orden ML'
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta'
    )

    # Información del destinatario
    buyer_nickname = fields.Char(
        string='Comprador',
        related='conversation_id.buyer_nickname',
        readonly=True
    )

    # Estado de capacidad de envío
    can_send = fields.Boolean(
        string='Puede Enviar',
        compute='_compute_can_send'
    )
    cap_warning = fields.Char(
        string='Advertencia',
        compute='_compute_can_send'
    )

    # Plantilla
    template_id = fields.Many2one(
        'mercadolibre.message.template',
        string='Plantilla',
        domain="[('active', '=', True)]"
    )
    available_template_ids = fields.Many2many(
        'mercadolibre.message.template',
        string='Plantillas Disponibles',
        compute='_compute_available_templates'
    )

    # Mensaje
    body = fields.Text(
        string='Mensaje',
        required=True
    )
    char_count = fields.Integer(
        string='Caracteres',
        compute='_compute_char_count'
    )
    char_remaining = fields.Integer(
        string='Caracteres Restantes',
        compute='_compute_char_count'
    )
    char_over_limit = fields.Boolean(
        string='Excede Límite',
        compute='_compute_char_count'
    )

    # Opción ML
    ml_option_id = fields.Selection([
        ('REQUEST_BILLING_INFO', 'Solicitar Datos de Facturación'),
        ('REQUEST_VARIANTS', 'Solicitar Variantes'),
        ('SEND_INVOICE_LINK', 'Enviar Link de Factura'),
        ('DELIVERY_PROMISE', 'Promesa de Entrega'),
        ('OTHER', 'Otro'),
    ], string='Tipo de Mensaje', default='OTHER', required=True,
       help='Clasificación del mensaje requerida por MercadoLibre')

    # Programación
    send_now = fields.Boolean(
        string='Enviar Ahora',
        default=True
    )
    scheduled_time = fields.Datetime(
        string='Programar Para'
    )

    # Historial de mensajes recientes
    recent_messages = fields.Html(
        string='Mensajes Recientes',
        compute='_compute_recent_messages'
    )

    @api.depends('conversation_id')
    def _compute_can_send(self):
        for record in self:
            if record.conversation_id:
                record.can_send = record.conversation_id.cap_available
                if not record.can_send:
                    record.cap_warning = _(
                        'MercadoLibre no permite enviar mensajes a esta conversación en este momento.'
                    )
                else:
                    record.cap_warning = False
            else:
                record.can_send = True
                record.cap_warning = False

    @api.depends('account_id')
    def _compute_available_templates(self):
        for record in self:
            if record.account_id:
                record.available_template_ids = self.env['mercadolibre.message.template'].get_templates_for_account(
                    record.account_id
                )
            else:
                record.available_template_ids = self.env['mercadolibre.message.template']

    @api.depends('body')
    def _compute_char_count(self):
        for record in self:
            count = len(record.body or '')
            record.char_count = count
            record.char_remaining = ML_MESSAGE_CHAR_LIMIT - count
            record.char_over_limit = count > ML_MESSAGE_CHAR_LIMIT

    @api.depends('conversation_id')
    def _compute_recent_messages(self):
        for record in self:
            if record.conversation_id:
                messages = record.conversation_id.ml_message_ids.sorted('create_date', reverse=True)[:5]
                html_parts = []
                for msg in reversed(messages):
                    direction_class = 'sent' if msg.direction == 'outgoing' else 'received'
                    direction_label = '📤 Enviado' if msg.direction == 'outgoing' else '📥 Recibido'
                    date_str = msg.create_date.strftime('%d/%m %H:%M') if msg.create_date else ''
                    html_parts.append(f'''
                        <div class="ml-message {direction_class}" style="
                            padding: 8px;
                            margin: 4px 0;
                            border-radius: 8px;
                            background: {'#e3f2fd' if msg.direction == 'outgoing' else '#f5f5f5'};
                        ">
                            <small style="color: #666;">{direction_label} - {date_str}</small>
                            <p style="margin: 4px 0 0 0;">{msg.body or ''}</p>
                        </div>
                    ''')
                record.recent_messages = ''.join(html_parts) if html_parts else '<p><em>Sin mensajes previos</em></p>'
            else:
                record.recent_messages = ''

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            # Renderizar plantilla con datos de la orden si existe
            if self.ml_order_id:
                self.body = self.template_id.render_for_order(self.ml_order_id)
            else:
                self.body = self.template_id.body

            self.ml_option_id = self.template_id.ml_option_id or 'OTHER'

    @api.constrains('body')
    def _check_body_length(self):
        for record in self:
            if record.body and len(record.body) > ML_MESSAGE_CHAR_LIMIT:
                raise ValidationError(_(
                    'El mensaje no puede exceder %s caracteres. '
                    'Actualmente tiene %s caracteres.'
                ) % (ML_MESSAGE_CHAR_LIMIT, len(record.body)))

    def action_send(self):
        """Envía el mensaje."""
        self.ensure_one()

        if not self.can_send:
            raise UserError(self.cap_warning or _('No se puede enviar el mensaje.'))

        if self.char_over_limit:
            raise UserError(_(
                'El mensaje excede el límite de %s caracteres.'
            ) % ML_MESSAGE_CHAR_LIMIT)

        if self.send_now:
            return self._send_message()
        else:
            return self._queue_message()

    def _send_message(self):
        """Envía el mensaje inmediatamente."""
        message = self.env['mercadolibre.message'].create({
            'conversation_id': self.conversation_id.id,
            'account_id': self.account_id.id,
            'body': self.body,
            'direction': 'outgoing',
            'template_id': self.template_id.id if self.template_id else False,
            'ml_order_id': self.ml_order_id.id if self.ml_order_id else False,
            'ml_option_id': self.ml_option_id,
            'state': 'pending',
        })

        # Intentar enviar
        success = message._send_to_ml()

        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Mensaje Enviado'),
                    'message': _('El mensaje se envió correctamente.'),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': message.error_message or _('Error al enviar el mensaje.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def _queue_message(self):
        """Programa el mensaje para envío posterior."""
        if not self.scheduled_time:
            raise UserError(_('Debe especificar una fecha de envío.'))

        queue_item = self.env['mercadolibre.message.queue'].create({
            'conversation_id': self.conversation_id.id,
            'account_id': self.account_id.id,
            'body': self.body,
            'template_id': self.template_id.id if self.template_id else False,
            'ml_order_id': self.ml_order_id.id if self.ml_order_id else False,
            'ml_option_id': self.ml_option_id,
            'scheduled_time': self.scheduled_time,
            'queue_reason': 'manual',
            'state': 'pending',
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Mensaje Programado'),
                'message': _('El mensaje se enviará el %s.') % self.scheduled_time.strftime('%d/%m/%Y %H:%M'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_preview(self):
        """Vista previa del mensaje."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vista Previa'),
                'message': self.body,
                'type': 'info',
                'sticky': True,
            }
        }
