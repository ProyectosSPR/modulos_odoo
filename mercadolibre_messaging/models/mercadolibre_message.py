# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

ML_MESSAGE_CHAR_LIMIT = 350


class MercadolibreMessage(models.Model):
    _name = 'mercadolibre.message'
    _description = 'Mensaje ML'
    _order = 'create_date desc'

    # Identificadores
    ml_message_id = fields.Char(
        string='ID Mensaje ML',
        index=True,
        readonly=True
    )

    # Relaciones
    conversation_id = fields.Many2one(
        'mercadolibre.conversation',
        string='Conversación',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='cascade',
        index=True
    )
    company_id = fields.Many2one(
        related='account_id.company_id',
        store=True
    )
    ml_order_id = fields.Many2one(
        'mercadolibre.order',
        string='Orden ML',
        ondelete='set null'
    )

    # Contenido
    body = fields.Text(
        string='Mensaje',
        required=True
    )
    body_char_count = fields.Integer(
        string='Caracteres',
        compute='_compute_body_char_count'
    )

    # Plantilla/Regla usada
    template_id = fields.Many2one(
        'mercadolibre.message.template',
        string='Plantilla',
        ondelete='set null'
    )
    rule_id = fields.Many2one(
        'mercadolibre.message.rule',
        string='Regla',
        ondelete='set null'
    )

    # Opción ML
    ml_option_id = fields.Selection([
        ('REQUEST_BILLING_INFO', 'Solicitar Datos de Facturación'),
        ('REQUEST_VARIANTS', 'Solicitar Variantes'),
        ('SEND_INVOICE_LINK', 'Enviar Link de Factura'),
        ('DELIVERY_PROMISE', 'Promesa de Entrega'),
        ('OTHER', 'Otro'),
    ], string='Opción ML', default='OTHER')

    # Dirección y estado
    direction = fields.Selection([
        ('incoming', 'Recibido'),
        ('outgoing', 'Enviado'),
    ], string='Dirección', required=True, default='outgoing')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
        ('failed', 'Fallido'),
        ('received', 'Recibido'),
    ], string='Estado', default='draft', tracking=True)

    # Lectura
    is_read = fields.Boolean(string='Leído', default=False)

    # Fechas
    ml_date_created = fields.Datetime(
        string='Fecha ML',
        readonly=True,
        help='Fecha del mensaje en MercadoLibre'
    )
    sent_date = fields.Datetime(
        string='Fecha Envío',
        readonly=True
    )

    # Error info
    error_message = fields.Text(
        string='Error',
        readonly=True
    )
    retry_count = fields.Integer(
        string='Reintentos',
        default=0
    )

    # Metadatos del remitente (para mensajes entrantes)
    sender_id = fields.Char(string='ID Remitente')
    sender_name = fields.Char(string='Nombre Remitente')

    @api.depends('body')
    def _compute_body_char_count(self):
        for record in self:
            record.body_char_count = len(record.body or '')

    @api.constrains('body')
    def _check_body_length(self):
        for record in self:
            if record.body and len(record.body) > ML_MESSAGE_CHAR_LIMIT:
                raise ValidationError(_(
                    'El mensaje no puede exceder %s caracteres. '
                    'Actualmente tiene %s caracteres.'
                ) % (ML_MESSAGE_CHAR_LIMIT, len(record.body)))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Si es mensaje saliente, establecer estado inicial
            if vals.get('direction') == 'outgoing' and 'state' not in vals:
                vals['state'] = 'draft'
            elif vals.get('direction') == 'incoming' and 'state' not in vals:
                vals['state'] = 'received'

        return super().create(vals_list)

    def action_send(self):
        """Envía el mensaje a MercadoLibre."""
        for record in self:
            if record.direction != 'outgoing':
                raise UserError(_('Solo se pueden enviar mensajes salientes'))

            if record.state == 'sent':
                raise UserError(_('Este mensaje ya fue enviado'))

            record._send_to_ml()

    def _send_to_ml(self):
        """Envía el mensaje a la API de MercadoLibre."""
        self.ensure_one()

        account = self.account_id
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)
        conversation = self.conversation_id

        # Verificar cap_available
        if not conversation.cap_available:
            self.write({
                'state': 'failed',
                'error_message': 'No se puede enviar mensaje (cap_available=false)'
            })
            config._log(
                f'Mensaje bloqueado: cap_available=false para pack {conversation.ml_pack_id}',
                level='warning',
                log_type='message_error',
                conversation_id=conversation.id
            )
            return False

        try:
            # Construir request
            pack_id = conversation.ml_pack_id
            endpoint = f'/messages/action_guide/packs/{pack_id}/option?tag=post_sale'

            payload = {
                'option_id': self.ml_option_id or 'OTHER',
                'text': self.body,
            }

            # Log request si está habilitado
            request_data = str(payload) if config.log_api_requests else None

            # Enviar a ML
            response = account._make_request('POST', endpoint, data=payload)

            if response:
                # Éxito
                self.write({
                    'state': 'sent',
                    'sent_date': fields.Datetime.now(),
                    'ml_message_id': response.get('id'),
                    'error_message': False,
                })

                config._log(
                    f'Mensaje enviado exitosamente a pack {pack_id}',
                    level='info',
                    log_type='message_sent',
                    conversation_id=conversation.id,
                    request_data=request_data,
                    response_data=str(response) if config.log_api_requests else None,
                )

                # Actualizar plantilla si se usó
                if self.template_id:
                    self.template_id.write({'last_used': fields.Datetime.now()})

                return True
            else:
                raise Exception('Respuesta vacía de la API')

        except Exception as e:
            error_msg = str(e)
            self.write({
                'state': 'failed',
                'error_message': error_msg,
                'retry_count': self.retry_count + 1,
            })

            config._log(
                f'Error enviando mensaje a pack {conversation.ml_pack_id}: {error_msg}',
                level='error',
                log_type='message_error',
                conversation_id=conversation.id,
            )

            return False

    def action_retry(self):
        """Reintenta el envío de un mensaje fallido."""
        for record in self:
            if record.state != 'failed':
                raise UserError(_('Solo se pueden reintentar mensajes fallidos'))

            config = self.env['mercadolibre.messaging.config'].get_config_for_account(record.account_id)
            if record.retry_count >= config.max_retries:
                raise UserError(_(
                    'Se alcanzó el máximo de reintentos (%s)'
                ) % config.max_retries)

            record.write({'state': 'pending'})
            record._send_to_ml()

    def action_mark_read(self):
        """Marca el mensaje como leído."""
        self.write({'is_read': True})

    def action_mark_unread(self):
        """Marca el mensaje como no leído."""
        self.write({'is_read': False})

    @api.model
    def cron_process_pending_messages(self):
        """Cron para procesar mensajes pendientes."""
        pending = self.search([
            ('state', '=', 'pending'),
            ('direction', '=', 'outgoing'),
        ], order='create_date asc', limit=50)

        for message in pending:
            try:
                message._send_to_ml()
            except Exception as e:
                _logger.error(f"Error procesando mensaje {message.id}: {e}")

    @api.model
    def cron_retry_failed_messages(self):
        """Cron para reintentar mensajes fallidos."""
        from datetime import timedelta

        failed = self.search([
            ('state', '=', 'failed'),
            ('direction', '=', 'outgoing'),
        ])

        for message in failed:
            config = self.env['mercadolibre.messaging.config'].get_config_for_account(message.account_id)

            # Verificar si puede reintentar
            if message.retry_count >= config.max_retries:
                continue

            # Verificar delay de reintento
            if message.write_date:
                min_retry_time = message.write_date + timedelta(minutes=config.retry_delay_minutes)
                if datetime.now() < min_retry_time:
                    continue

            try:
                message.write({'state': 'pending'})
                message._send_to_ml()
            except Exception as e:
                _logger.error(f"Error reintentando mensaje {message.id}: {e}")
