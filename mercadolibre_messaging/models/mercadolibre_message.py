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

    # Imágenes/Attachments
    attachment_urls = fields.Text(
        string='URLs de Adjuntos',
        help='URLs de imágenes adjuntas (separadas por coma)'
    )
    has_attachments = fields.Boolean(
        string='Tiene Adjuntos',
        compute='_compute_has_attachments',
        store=True
    )

    @api.depends('attachment_urls')
    def _compute_has_attachments(self):
        for record in self:
            record.has_attachments = bool(record.attachment_urls and record.attachment_urls.strip())

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
        """Inicializa campos faltantes al actualizar módulo."""
        # Crear columna attachment_urls si no existe
        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'mercadolibre_message'
            AND column_name = 'attachment_urls'
        """)
        if not self.env.cr.fetchone():
            self.env.cr.execute("""
                ALTER TABLE mercadolibre_message
                ADD COLUMN attachment_urls TEXT
            """)

        # Crear columna has_attachments si no existe
        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'mercadolibre_message'
            AND column_name = 'has_attachments'
        """)
        if not self.env.cr.fetchone():
            self.env.cr.execute("""
                ALTER TABLE mercadolibre_message
                ADD COLUMN has_attachments BOOLEAN DEFAULT FALSE
            """)

        # Recalcula message_date para mensajes sin ese campo
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
        Envía el mensaje a la API de MercadoLibre.

        Usa el endpoint correcto según el estado de la conversación:
        - Si la conversación ya existe (tiene mensajes): usa /messages/packs/{pack}/sellers/{seller}
        - Si es primera comunicación: usa /messages/action_guide/packs/{pack}/option

        Endpoint normal: POST /messages/packs/{PACK_ID}/sellers/{SELLER_ID}?tag=post_sale
        Endpoint action_guide: POST /messages/action_guide/packs/{PACK_ID}/option?tag=post_sale
        """
        self.ensure_one()

        account = self.account_id
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)
        conversation = self.conversation_id
        pack_id = conversation.ml_pack_id
        seller_id = account.ml_user_id

        _logger.info(f"=== INICIO ENVÍO MENSAJE ===")
        _logger.info(f"Pack ID: {pack_id}")
        _logger.info(f"Account: {account.name} (ML User: {seller_id})")
        _logger.info(f"Mensaje: {self.body[:100]}...")

        buyer_id = conversation.buyer_id
        _logger.info(f"Buyer ID: {buyer_id}")
        _logger.info(f"Seller ID: {seller_id}")

        # Verificar que buyer_id sea válido (no corrupto)
        if not buyer_id or 'mercadolibre' in str(buyer_id).lower():
            _logger.error(f"buyer_id inválido: {buyer_id}. Ejecuta 'Sincronizar Mensajes' para corregirlo.")
            raise Exception(f"buyer_id inválido: {buyer_id}. Sincroniza la conversación primero.")

        try:
            # Verificar si la conversación ya tiene mensajes (determina qué endpoint usar)
            has_messages = len(conversation.ml_message_ids) > 0
            _logger.info(f"Conversación tiene mensajes previos: {has_messages}")

            if has_messages:
                # Conversación existente: usar endpoint de mensajes directo
                # POST /messages/packs/{pack}/sellers/{seller}?tag=post_sale
                endpoint = f'/messages/packs/{pack_id}/sellers/{seller_id}?tag=post_sale'
                payload = {
                    'from': {
                        'user_id': int(seller_id)  # ML espera integer
                    },
                    'to': {
                        'user_id': int(buyer_id)  # ML espera integer
                    },
                    'text': self.body[:ML_MESSAGE_CHAR_LIMIT]
                }
            else:
                # Primera comunicación: usar action_guide
                option_id = self.ml_option_id or 'OTHER'
                endpoint = f'/messages/action_guide/packs/{pack_id}/option?tag=post_sale'
                payload = self._build_message_payload(option_id)

            _logger.info(f"Endpoint: POST {endpoint}")
            _logger.info(f"Payload: {payload}")

            config._log(
                f'Enviando mensaje a pack {pack_id}',
                level='debug',
                log_type='messaging',
                conversation_id=conversation.id,
                request_url=endpoint,
                request_data=str(payload)
            )

            # Enviar a ML
            _logger.info(f"Ejecutando request a ML...")
            response = account._make_request('POST', endpoint, data=payload)
            _logger.info(f"Respuesta ML: {response}")

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
        _logger.info(f"=== CHECK CAPS ===")
        _logger.info(f"Pack ID: {pack_id}, Option ID: {option_id}")

        try:
            endpoint = f'/messages/action_guide/packs/{pack_id}/caps_available?tag=post_sale'
            _logger.info(f"Endpoint caps: GET {endpoint}")
            response = account._make_request('GET', endpoint)
            _logger.info(f"Respuesta caps: {response}")

            if not response:
                # Si no hay respuesta, permitir envío (puede ser orden antigua)
                _logger.info("Sin respuesta de caps, permitiendo envío")
                return {'can_send': True, 'remaining_cap': 1, 'caps': []}

            # Buscar cap para la opción seleccionada
            caps = response if isinstance(response, list) else []
            _logger.info(f"Caps disponibles: {caps}")

            option_cap = next(
                (c for c in caps if c.get('option_id') == option_id),
                None
            )
            _logger.info(f"Cap para opción {option_id}: {option_cap}")

            if option_cap is None:
                # Opción no disponible para este pack
                _logger.warning(f"Opción {option_id} no disponible en caps")
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
