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
    _order = 'message_date desc, id desc'

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
    # Campo para ordenamiento (siempre tiene valor)
    message_date = fields.Datetime(
        string='Fecha Mensaje',
        compute='_compute_message_date',
        store=True,
        index=True,
        help='Fecha usada para ordenar mensajes (ML o creación)'
    )

    @api.depends('ml_date_created', 'create_date')
    def _compute_message_date(self):
        for record in self:
            record.message_date = record.ml_date_created or record.create_date or fields.Datetime.now()

    def init(self):
        """Recalcula message_date para mensajes sin ese campo al actualizar módulo."""
        self.env.cr.execute("""
            UPDATE mercadolibre_message
            SET message_date = COALESCE(ml_date_created, create_date, NOW())
            WHERE message_date IS NULL
        """)

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
        """
        Envía el mensaje a la API de MercadoLibre usando action_guide.

        MercadoLibre requiere usar el endpoint action_guide para iniciar conversaciones
        en órdenes con Mercado Envíos 2 (Fulfillment, Cross docking, Drop off, Flex).

        Endpoint: POST /messages/action_guide/packs/{PACK_ID}/option?tag=post_sale

        Opciones disponibles:
        - REQUEST_BILLING_INFO: Solicitar datos de facturación (template)
        - REQUEST_VARIANTS: Solicitar variantes del producto (template)
        - SEND_INVOICE_LINK: Enviar link de factura (free text, 350 chars)
        - DELIVERY_PROMISE: Promesa de entrega - solo Flex (template)
        - OTHER: Comunicación general (free text, 350 chars)
        """
        self.ensure_one()

        account = self.account_id
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)
        conversation = self.conversation_id
        pack_id = conversation.ml_pack_id

        # Verificar caps_available antes de enviar
        caps_check = self._check_caps_available(account, pack_id)
        if not caps_check['can_send']:
            self.write({
                'state': 'failed',
                'error_message': caps_check['reason']
            })
            config._log(
                f'Mensaje bloqueado: {caps_check["reason"]} para pack {pack_id}',
                level='warning',
                log_type='message_error',
                conversation_id=conversation.id
            )
            return False

        try:
            # Construir payload según tipo de opción
            option_id = self.ml_option_id or 'OTHER'
            payload = self._build_message_payload(option_id)

            # Endpoint de action_guide
            endpoint = f'/messages/action_guide/packs/{pack_id}/option?tag=post_sale'

            # Log request si está habilitado
            request_data = str(payload) if config.log_api_requests else None

            config._log(
                f'Enviando mensaje a pack {pack_id} con opción {option_id}',
                level='debug',
                log_type='messaging',
                conversation_id=conversation.id,
                request_url=endpoint,
                request_data=request_data
            )

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

                # Actualizar conversación
                conversation.write({
                    'state': 'answered',
                    'cap_available': caps_check.get('remaining_cap', 0) > 0,
                    'cap_checked_at': fields.Datetime.now(),
                })

                config._log(
                    f'Mensaje enviado exitosamente a pack {pack_id} - ID: {response.get("id")}',
                    level='info',
                    log_type='message_sent',
                    conversation_id=conversation.id,
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

            # Detectar errores específicos de ML
            if 'blocked_by_conversation_started_by_seller' in error_msg:
                error_msg = 'Debes esperar respuesta del comprador antes de enviar otro mensaje'
            elif 'cap_exceeded' in error_msg:
                error_msg = 'Has excedido el límite de mensajes. Espera respuesta del comprador.'

            self.write({
                'state': 'failed',
                'error_message': error_msg,
                'retry_count': self.retry_count + 1,
            })

            config._log(
                f'Error enviando mensaje a pack {pack_id}: {error_msg}',
                level='error',
                log_type='message_error',
                conversation_id=conversation.id,
            )

            return False

    def _check_caps_available(self, account, pack_id):
        """
        Verifica los caps disponibles para enviar mensajes.

        Endpoint: GET /messages/action_guide/packs/{PACK_ID}/caps_available?tag=post_sale

        Response ejemplo:
        [
            {"option_id": "REQUEST_VARIANTS", "cap_available": 1},
            {"option_id": "REQUEST_BILLING_INFO", "cap_available": 1},
            {"option_id": "SEND_INVOICE_LINK", "cap_available": 1},
            {"option_id": "OTHER", "cap_available": 1}
        ]

        Returns:
            dict: {
                'can_send': bool,
                'reason': str (si no puede enviar),
                'remaining_cap': int,
                'caps': list (datos crudos de la API)
            }
        """
        option_id = self.ml_option_id or 'OTHER'

        try:
            endpoint = f'/messages/action_guide/packs/{pack_id}/caps_available?tag=post_sale'
            response = account._make_request('GET', endpoint)

            if not response:
                # Si no hay respuesta, permitir envío (puede ser orden antigua)
                return {'can_send': True, 'remaining_cap': 1, 'caps': []}

            # Buscar cap para la opción seleccionada
            caps = response if isinstance(response, list) else []
            option_cap = next(
                (c for c in caps if c.get('option_id') == option_id),
                None
            )

            if option_cap is None:
                # Opción no disponible para este pack
                return {
                    'can_send': False,
                    'reason': f'La opción {option_id} no está disponible para este pack',
                    'remaining_cap': 0,
                    'caps': caps
                }

            cap_available = option_cap.get('cap_available', 0)

            if cap_available <= 0:
                return {
                    'can_send': False,
                    'reason': f'Sin mensajes disponibles para {option_id}. Espera respuesta del comprador.',
                    'remaining_cap': 0,
                    'caps': caps
                }

            return {
                'can_send': True,
                'remaining_cap': cap_available - 1,  # Restamos el que vamos a enviar
                'caps': caps
            }

        except Exception as e:
            _logger.warning(f"Error verificando caps para pack {pack_id}: {e}")
            # En caso de error, permitir el intento (el error se manejará en el envío)
            return {'can_send': True, 'remaining_cap': 1, 'caps': []}

    def _build_message_payload(self, option_id):
        """
        Construye el payload del mensaje según el tipo de opción.

        Tipos de opción:
        - Template: REQUEST_BILLING_INFO, REQUEST_VARIANTS, DELIVERY_PROMISE
        - Free text: SEND_INVOICE_LINK, OTHER (máx 350 caracteres)

        Args:
            option_id: str con la opción seleccionada

        Returns:
            dict: payload para la API
        """
        # Opciones tipo template (sin texto libre obligatorio)
        template_options = {
            'REQUEST_BILLING_INFO': 'TEMPLATE___REQUEST_BILLING_INFO___1',
            'REQUEST_VARIANTS': 'TEMPLATE___REQUEST_VARIANTS___1',
        }

        if option_id in template_options:
            payload = {
                'option_id': option_id,
                'template_id': template_options[option_id],
            }
            # Si hay texto adicional, agregarlo
            if self.body and self.body.strip():
                payload['text'] = self.body[:ML_MESSAGE_CHAR_LIMIT]
        else:
            # Opciones de texto libre (SEND_INVOICE_LINK, OTHER)
            payload = {
                'option_id': option_id,
                'text': self.body[:ML_MESSAGE_CHAR_LIMIT] if self.body else '',
            }

        return payload

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
