# -*- coding: utf-8 -*-

import logging
from datetime import datetime
import pytz
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreConversation(models.Model):
    _name = 'mercadolibre.conversation'
    _description = 'Conversación ML'
    _order = 'last_message_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Conversación',
        compute='_compute_name',
        store=True
    )
    active = fields.Boolean(default=True)

    # Identificadores ML
    ml_conversation_id = fields.Char(
        string='ID Conversación ML',
        index=True,
        readonly=True
    )
    ml_pack_id = fields.Char(
        string='Pack ID',
        index=True,
        required=True
    )

    # Relaciones
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
        ondelete='set null',
        index=True
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        compute='_compute_sale_order',
        store=True
    )

    # Participantes - Comprador
    buyer_id = fields.Char(
        string='ID Comprador ML',
        readonly=True,
        index=True,
        help='user_id del comprador en MercadoLibre'
    )
    buyer_nickname = fields.Char(
        string='Nickname Comprador',
        readonly=True
    )
    buyer_first_name = fields.Char(
        string='Nombre Comprador',
        compute='_compute_buyer_info',
        store=True
    )
    buyer_email = fields.Char(
        string='Email Comprador',
        compute='_compute_buyer_info',
        store=True
    )

    # Participantes - Vendedor
    seller_id = fields.Char(
        string='ID Vendedor ML',
        readonly=True,
        help='user_id del vendedor (cuenta ML)'
    )

    # Partner de Odoo (si existe)
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        compute='_compute_partner',
        store=True
    )

    # Estado
    state = fields.Selection([
        ('open', 'Abierta'),
        ('waiting', 'Esperando Respuesta'),
        ('answered', 'Respondida'),
        ('closed', 'Cerrada'),
    ], string='Estado', default='open', tracking=True)

    is_unread = fields.Boolean(
        string='Sin Leer',
        compute='_compute_is_unread',
        store=True
    )
    unread_count = fields.Integer(
        string='Mensajes Sin Leer',
        compute='_compute_is_unread',
        store=True
    )

    # Mensajes
    ml_message_ids = fields.One2many(
        'mercadolibre.message',
        'conversation_id',
        string='Mensajes'
    )
    message_count = fields.Integer(
        string='Total Mensajes',
        compute='_compute_message_count'
    )
    last_message_date = fields.Datetime(
        string='Último Mensaje',
        compute='_compute_last_message',
        store=True
    )
    last_message_preview = fields.Char(
        string='Último Mensaje',
        compute='_compute_last_message',
        store=True
    )
    last_message_direction = fields.Selection([
        ('incoming', 'Recibido'),
        ('outgoing', 'Enviado'),
    ], compute='_compute_last_message', store=True)

    # Campo HTML para vista tipo chat
    chat_messages_html = fields.Html(
        string='Chat',
        compute='_compute_chat_messages_html',
        sanitize=False
    )

    # Campo para envío rápido de mensaje
    quick_message = fields.Text(
        string='Mensaje Rápido',
        help='Escribe tu mensaje aquí (máx 350 caracteres)'
    )

    # Capacidad de envío (API ML)
    cap_available = fields.Boolean(
        string='Puede Enviar',
        default=True,
        help='Indica si se puede enviar mensajes (cap_available de ML)'
    )
    cap_checked_at = fields.Datetime(string='Cap Verificado')

    # Datos del pedido (para referencia rápida)
    order_status = fields.Char(
        string='Estado Orden',
        compute='_compute_order_info',
        store=True
    )
    shipment_status = fields.Char(
        string='Estado Envío',
        compute='_compute_order_info',
        store=True
    )
    total_amount = fields.Float(
        string='Monto',
        compute='_compute_order_info',
        store=True
    )

    @api.depends('buyer_nickname', 'ml_pack_id')
    def _compute_name(self):
        for record in self:
            buyer = record.buyer_nickname or 'Comprador'
            record.name = f"{buyer} - {record.ml_pack_id or 'Nueva'}"

    @api.depends('ml_order_id', 'ml_order_id.sale_order_id')
    def _compute_sale_order(self):
        for record in self:
            if record.ml_order_id and record.ml_order_id.sale_order_id:
                record.sale_order_id = record.ml_order_id.sale_order_id
            else:
                record.sale_order_id = False

    @api.depends('ml_order_id', 'ml_order_id.buyer_id', 'ml_order_id.buyer_id.first_name', 'ml_order_id.buyer_id.email')
    def _compute_buyer_info(self):
        """Obtiene información del comprador desde la orden ML."""
        for record in self:
            if record.ml_order_id and record.ml_order_id.buyer_id:
                record.buyer_first_name = record.ml_order_id.buyer_id.first_name or ''
                record.buyer_email = record.ml_order_id.buyer_id.email or ''
            else:
                record.buyer_first_name = ''
                record.buyer_email = ''

    @api.depends('ml_order_id', 'ml_order_id.partner_id', 'sale_order_id', 'sale_order_id.partner_id')
    def _compute_partner(self):
        """Obtiene el partner de Odoo asociado."""
        for record in self:
            partner = False
            if record.sale_order_id and record.sale_order_id.partner_id:
                partner = record.sale_order_id.partner_id
            elif record.ml_order_id and hasattr(record.ml_order_id, 'partner_id'):
                partner = record.ml_order_id.partner_id
            record.partner_id = partner

    @api.depends('ml_message_ids', 'ml_message_ids.is_read', 'ml_message_ids.direction')
    def _compute_is_unread(self):
        for record in self:
            unread = record.ml_message_ids.filtered(
                lambda m: not m.is_read and m.direction == 'incoming'
            )
            record.unread_count = len(unread)
            record.is_unread = record.unread_count > 0

    def _compute_message_count(self):
        for record in self:
            record.message_count = len(record.ml_message_ids)

    @api.depends('ml_message_ids', 'ml_message_ids.create_date', 'ml_message_ids.body')
    def _compute_last_message(self):
        for record in self:
            last_msg = record.ml_message_ids.sorted('create_date', reverse=True)[:1]
            if last_msg:
                record.last_message_date = last_msg.create_date
                record.last_message_preview = (last_msg.body or '')[:100]
                record.last_message_direction = last_msg.direction
            else:
                record.last_message_date = False
                record.last_message_preview = ''
                record.last_message_direction = False

    @api.depends('ml_message_ids', 'ml_message_ids.body', 'ml_message_ids.direction',
                 'ml_message_ids.message_date', 'ml_message_ids.state', 'ml_message_ids.is_read')
    def _compute_chat_messages_html(self):
        """Genera HTML tipo chat para los mensajes."""
        for record in self:
            if not record.ml_message_ids:
                record.chat_messages_html = '''
                    <div class="ml-chat-empty">
                        <i class="fa fa-comments-o fa-3x text-muted"></i>
                        <p class="text-muted mt-2">No hay mensajes en esta conversación</p>
                    </div>
                '''
                continue

            # Ordenar por message_date (campo stored que siempre tiene valor)
            # reverse=True para que los más nuevos estén al final (scroll down)
            messages = record.ml_message_ids.sorted('message_date', reverse=True)
            html_parts = ['<div class="ml-chat-container" id="ml-chat-messages">']

            current_date = None
            for msg in messages:
                # Usar message_date (siempre tiene valor)
                msg_datetime = msg.message_date
                msg_date = msg_datetime.date() if msg_datetime else None
                if msg_date and msg_date != current_date:
                    current_date = msg_date
                    date_str = msg_date.strftime('%d/%m/%Y')
                    html_parts.append(f'''
                        <div class="ml-chat-date-separator">
                            <span>{date_str}</span>
                        </div>
                    ''')

                # Determinar clase y estilo según dirección
                if msg.direction == 'outgoing':
                    bubble_class = 'ml-chat-bubble-outgoing'
                    sender = 'Tú'
                    icon = 'fa-arrow-up'
                else:
                    bubble_class = 'ml-chat-bubble-incoming'
                    sender = record.buyer_nickname or 'Comprador'
                    icon = 'fa-arrow-down'

                # Estado del mensaje
                state_icon = ''
                if msg.direction == 'outgoing':
                    if msg.state == 'sent':
                        state_icon = '<i class="fa fa-check text-muted" title="Enviado"></i>'
                    elif msg.state == 'delivered':
                        state_icon = '<i class="fa fa-check-double text-success" title="Entregado"></i>'
                    elif msg.state == 'failed':
                        state_icon = '<i class="fa fa-exclamation-circle text-danger" title="Error"></i>'
                    elif msg.state == 'pending':
                        state_icon = '<i class="fa fa-clock-o text-warning" title="Pendiente"></i>'

                # Indicador de no leído
                unread_class = 'ml-chat-unread' if not msg.is_read and msg.direction == 'incoming' else ''

                # Hora del mensaje
                time_str = msg.message_date.strftime('%H:%M') if msg.message_date else ''

                # Escapar HTML en el cuerpo del mensaje
                body_escaped = (msg.body or '').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>')

                html_parts.append(f'''
                    <div class="ml-chat-bubble {bubble_class} {unread_class}">
                        <div class="ml-chat-bubble-content">
                            <div class="ml-chat-bubble-header">
                                <span class="ml-chat-sender">
                                    <i class="fa {icon}"></i> {sender}
                                </span>
                            </div>
                            <div class="ml-chat-bubble-body">{body_escaped}</div>
                            <div class="ml-chat-bubble-footer">
                                <span class="ml-chat-time">{time_str}</span>
                                {state_icon}
                            </div>
                        </div>
                    </div>
                ''')

            html_parts.append('</div>')
            record.chat_messages_html = ''.join(html_parts)

    @api.depends('ml_order_id', 'ml_order_id.status', 'ml_order_id.shipment_id.status', 'ml_order_id.total_amount')
    def _compute_order_info(self):
        for record in self:
            if record.ml_order_id:
                record.order_status = record.ml_order_id.status
                record.total_amount = record.ml_order_id.total_amount
                if record.ml_order_id.shipment_id:
                    record.shipment_status = record.ml_order_id.shipment_id.status
                else:
                    record.shipment_status = False
            else:
                record.order_status = False
                record.shipment_status = False
                record.total_amount = 0

    @api.model
    def get_or_create_for_order(self, ml_order):
        """
        Obtiene o crea una conversación para una orden ML.

        Args:
            ml_order: mercadolibre.order record

        Returns:
            mercadolibre.conversation record
        """
        if not ml_order.ml_pack_id:
            _logger.warning(f"Orden {ml_order.ml_order_id} sin pack_id")
            return False

        conversation = self.search([
            ('ml_pack_id', '=', ml_order.ml_pack_id),
            ('account_id', '=', ml_order.account_id.id),
        ], limit=1)

        if not conversation:
            conversation = self.create({
                'ml_pack_id': ml_order.ml_pack_id,
                'account_id': ml_order.account_id.id,
                'ml_order_id': ml_order.id,
                'buyer_id': ml_order.buyer_id,
                'buyer_nickname': ml_order.buyer_nickname,
                'seller_id': ml_order.account_id.ml_user_id,
            })
            _logger.info(f"Conversación creada para pack {ml_order.ml_pack_id}")

        return conversation

    def action_open_messages(self):
        """Abre la vista de mensajes de la conversación."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mensajes'),
            'res_model': 'mercadolibre.message',
            'view_mode': 'tree,form',
            'domain': [('conversation_id', '=', self.id)],
            'context': {'default_conversation_id': self.id},
        }

    def action_compose_message(self):
        """Abre wizard para componer mensaje."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enviar Mensaje'),
            'res_model': 'mercadolibre.message.compose',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': self.id,
                'default_account_id': self.account_id.id,
                'default_ml_pack_id': self.ml_pack_id,
            },
        }

    def action_mark_read(self):
        """Marca todos los mensajes como leídos."""
        self.ensure_one()
        self.ml_message_ids.filtered(
            lambda m: not m.is_read and m.direction == 'incoming'
        ).write({'is_read': True})

    def action_send_quick_message(self):
        """Envía el mensaje rápido escrito en el campo quick_message."""
        self.ensure_one()

        if not self.quick_message or not self.quick_message.strip():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Mensaje Vacío'),
                    'message': _('Escribe un mensaje antes de enviar.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if not self.cap_available:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Cap Disponible'),
                    'message': _('Debes esperar respuesta del comprador antes de enviar otro mensaje.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        message_text = self.quick_message.strip()[:350]  # Límite ML

        # Crear y enviar el mensaje
        message = self.env['mercadolibre.message'].create({
            'conversation_id': self.id,
            'account_id': self.account_id.id,
            'body': message_text,
            'direction': 'outgoing',
            'state': 'pending',
            'ml_option_id': 'OTHER',
        })

        # Intentar enviar
        try:
            message._send_to_ml()
            # Limpiar el campo de mensaje rápido
            self.write({'quick_message': False})

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Mensaje Enviado'),
                    'message': _('Tu mensaje ha sido enviado correctamente.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error al Enviar'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_refresh_caps(self):
        """
        Verifica los caps disponibles para esta conversación.

        Endpoint: GET /messages/action_guide/packs/{PACK_ID}/caps_available?tag=post_sale
        """
        self.ensure_one()

        if not self.ml_pack_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Esta conversación no tiene Pack ID.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        account = self.account_id

        try:
            endpoint = f'/messages/action_guide/packs/{self.ml_pack_id}/caps_available?tag=post_sale'
            response = account._make_request('GET', endpoint)

            if response:
                # Verificar si hay cap disponible para OTHER (el más común)
                caps = response if isinstance(response, list) else []
                other_cap = next(
                    (c for c in caps if c.get('option_id') == 'OTHER'),
                    None
                )

                cap_available = other_cap.get('cap_available', 0) > 0 if other_cap else False

                self.write({
                    'cap_available': cap_available,
                    'cap_checked_at': fields.Datetime.now(),
                })

                # Construir mensaje de resultado
                caps_info = ', '.join([
                    f"{c.get('option_id')}: {c.get('cap_available', 0)}"
                    for c in caps
                ])

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Caps Verificados'),
                        'message': caps_info or _('Sin información de caps'),
                        'type': 'success' if cap_available else 'warning',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sin Respuesta'),
                        'message': _('No se pudo obtener información de caps.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_view_partner(self):
        """Abre el formulario del partner asociado."""
        self.ensure_one()
        if not self.partner_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cliente'),
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_sync_messages(self):
        """Sincroniza mensajes de la conversación desde ML."""
        self.ensure_one()
        self._sync_messages_from_ml()
        # Recalcular message_date para todos los mensajes
        self.ml_message_ids._compute_message_date()

    def action_fix_message_order(self):
        """Recalcula las fechas de ordenamiento de los mensajes."""
        self.ensure_one()
        self.ml_message_ids._compute_message_date()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Orden Corregido'),
                'message': _('Se recalcularon las fechas de %s mensajes.') % len(self.ml_message_ids),
                'type': 'success',
                'sticky': False,
            }
        }

    def _sync_messages_from_ml(self):
        """Sincroniza mensajes desde la API de ML con paginación completa."""
        self.ensure_one()

        if not self.ml_pack_id:
            return

        account = self.account_id
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)

        try:
            total_synced = 0
            offset = 0
            limit = 100  # Máximo por request
            has_more = True

            while has_more:
                # Obtener mensajes de la API con paginación
                endpoint = f'/messages/packs/{self.ml_pack_id}/sellers/{account.ml_user_id}?tag=post_sale&mark_as_read=false&limit={limit}&offset={offset}'
                response = account._make_request('GET', endpoint)

                if not response:
                    config._log(
                        f'Sin respuesta para pack {self.ml_pack_id}',
                        level='debug',
                        log_type='message_sync'
                    )
                    break

                # Actualizar cap_available (solo en primera iteración)
                if offset == 0 and 'conversation' in response:
                    conv_data = response['conversation']
                    self.write({
                        'cap_available': conv_data.get('cap_available', True),
                        'cap_checked_at': fields.Datetime.now(),
                    })

                # Procesar mensajes
                messages = response.get('messages', [])
                for msg_data in messages:
                    self._process_message_from_api(msg_data)

                total_synced += len(messages)

                # Verificar si hay más mensajes (paginación)
                paging = response.get('paging', {})
                total = paging.get('total', len(messages))

                # Calcular si hay más páginas
                offset += limit
                has_more = offset < total and len(messages) == limit

                _logger.debug(f"Pack {self.ml_pack_id}: sincronizados {total_synced}/{total} mensajes")

            config._log(
                f'Sincronizados {total_synced} mensajes para pack {self.ml_pack_id}',
                level='info',
                log_type='message_sync',
                conversation_id=self.id
            )

        except Exception as e:
            config._log(
                f'Error sincronizando mensajes pack {self.ml_pack_id}: {str(e)}',
                level='error',
                log_type='message_error',
                conversation_id=self.id
            )
            raise

    def _process_message_from_api(self, msg_data):
        """
        Procesa un mensaje de la API y lo guarda.

        Args:
            msg_data: dict con datos del mensaje de la API
        """
        ml_message_id = msg_data.get('id')

        # Verificar si ya existe
        existing = self.env['mercadolibre.message'].search([
            ('ml_message_id', '=', ml_message_id),
        ], limit=1)

        if existing:
            return existing

        # Determinar dirección
        from_id = str(msg_data.get('from', {}).get('user_id', ''))
        direction = 'incoming' if from_id != self.account_id.ml_user_id else 'outgoing'

        # Parsear fecha de ML (varios formatos posibles)
        date_created = None
        date_str = msg_data.get('date_created') or msg_data.get('date')
        if date_str:
            try:
                # Formato ISO con Z
                date_created = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                try:
                    # Formato alternativo
                    from dateutil import parser
                    date_created = parser.parse(date_str)
                except Exception:
                    _logger.warning(f"No se pudo parsear fecha: {date_str}")

        message = self.env['mercadolibre.message'].create({
            'ml_message_id': ml_message_id,
            'conversation_id': self.id,
            'account_id': self.account_id.id,
            'body': msg_data.get('text', ''),
            'direction': direction,
            'state': 'sent' if direction == 'outgoing' else 'received',
            'is_read': direction == 'outgoing',
            'ml_date_created': date_created,
        })

        # Sincronizar al chatter si está configurado
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(self.account_id)
        if config.sync_to_chatter and self.sale_order_id and direction == 'incoming':
            self._sync_message_to_chatter(message)

        return message

    def _sync_message_to_chatter(self, message):
        """Sincroniza un mensaje al chatter de sale.order."""
        if not self.sale_order_id:
            return

        body = f"""
        <p><strong>📩 Mensaje de MercadoLibre</strong></p>
        <p><em>De: {self.buyer_nickname}</em></p>
        <p>{message.body}</p>
        <p><small>Pack: {self.ml_pack_id}</small></p>
        """

        self.sale_order_id.message_post(
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

    def action_close(self):
        """Cierra la conversación."""
        self.write({'state': 'closed'})

    def action_reopen(self):
        """Reabre la conversación."""
        self.write({'state': 'open'})

    # =========================================================================
    # NOTIFICACIONES (integración con mercadolibre_connector)
    # =========================================================================

    @api.model
    def process_notification(self, account, data):
        """
        Procesa una notificación de mensajes desde el webhook central.

        Este método es llamado por el controller de mercadolibre_connector
        cuando recibe una notificación con topic='messages'.

        Args:
            account: mercadolibre.account record
            data: dict con la notificación de ML
                {
                    "resource": "message_id",
                    "user_id": 123456789,
                    "topic": "messages",
                    "actions": ["created"],  # o ["read"]
                    "application_id": 89745685555,
                    "attempts": 1,
                    "sent": "2024-01-15T10:30:00.000Z",
                    "received": "2024-01-15T10:30:01.000Z"
                }

        Returns:
            dict con resultado del procesamiento
        """
        resource = data.get('resource')  # message_id
        actions = data.get('actions', [])

        _logger.info(f"Procesando notificación mensaje - Resource: {resource}, Actions: {actions}")

        if 'created' in actions:
            return self._handle_new_message_notification(account, resource, data)
        elif 'read' in actions:
            return self._handle_message_read_notification(account, resource, data)
        else:
            _logger.debug(f"Acción no manejada: {actions}")
            return {'status': 'ignored', 'reason': f'actions {actions} not handled'}

    def _handle_new_message_notification(self, account, message_id, notification_data):
        """
        Maneja la notificación de un nuevo mensaje recibido.

        Args:
            account: mercadolibre.account record
            message_id: ID del mensaje en ML
            notification_data: datos completos de la notificación
        """
        try:
            # Obtener detalles del mensaje desde la API
            endpoint = f'/messages/{message_id}?tag=post_sale'
            message_data = account._make_request('GET', endpoint)

            if not message_data:
                _logger.error(f"No se pudo obtener mensaje {message_id}")
                return {'status': 'error', 'reason': 'could not fetch message'}

            # Obtener pack_id del mensaje
            pack_id = None
            for resource in message_data.get('message_resources', []):
                if resource.get('name') == 'packs':
                    pack_id = resource.get('id')
                    break

            if not pack_id:
                _logger.warning(f"Mensaje {message_id} sin pack_id")
                return {'status': 'ignored', 'reason': 'no pack_id'}

            # Buscar o crear conversación
            conversation = self.search([
                ('ml_pack_id', '=', str(pack_id)),
                ('account_id', '=', account.id),
            ], limit=1)

            if not conversation:
                conversation = self._create_conversation_from_notification(account, pack_id, message_data)

            if not conversation:
                return {'status': 'error', 'reason': 'could not create conversation'}

            # Verificar si el mensaje ya existe
            existing_msg = self.env['mercadolibre.message'].search([
                ('ml_message_id', '=', message_id),
            ], limit=1)

            if existing_msg:
                _logger.debug(f"Mensaje {message_id} ya existe")
                return {'status': 'ok', 'action': 'already_exists'}

            # Crear mensaje en Odoo
            message = conversation._create_message_from_notification(message_data, account)

            if message:
                # Log de éxito
                config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)
                config._log(
                    f'Mensaje recibido via webhook: {message_id}',
                    level='info',
                    log_type='message_received',
                    conversation_id=conversation.id
                )

                # Sincronizar al chatter si está configurado
                if config.sync_to_chatter and conversation.sale_order_id:
                    conversation._sync_message_to_chatter(message)

                return {'status': 'ok', 'action': 'created', 'message_id': message.id}

            return {'status': 'error', 'reason': 'could not create message'}

        except Exception as e:
            _logger.error(f"Error procesando nuevo mensaje: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _create_conversation_from_notification(self, account, pack_id, message_data):
        """
        Crea una conversación a partir de datos de notificación de mensaje.

        Args:
            account: mercadolibre.account record
            pack_id: ID del pack
            message_data: datos del mensaje de la API
        """
        try:
            # Identificar comprador y vendedor
            from_user = message_data.get('from', {}).get('user_id')
            to_user = message_data.get('to', {}).get('user_id')

            seller_id = account.ml_user_id

            # El que no es el vendedor es el comprador
            if str(from_user) == seller_id:
                buyer_id = str(to_user)
            else:
                buyer_id = str(from_user)

            # Buscar orden ML asociada al pack
            ml_order = self.env['mercadolibre.order'].search([
                ('ml_pack_id', '=', str(pack_id)),
                ('account_id', '=', account.id),
            ], limit=1)

            # Obtener nickname del comprador si existe la orden
            buyer_nickname = ''
            if ml_order:
                buyer_nickname = ml_order.buyer_nickname or ml_order.buyer_first_name or ''

            # Crear conversación
            conversation = self.create({
                'ml_pack_id': str(pack_id),
                'account_id': account.id,
                'ml_order_id': ml_order.id if ml_order else False,
                'buyer_id': buyer_id,
                'buyer_nickname': buyer_nickname,
                'seller_id': seller_id,
                'state': 'open',
            })

            _logger.info(f"Conversación creada para pack {pack_id}")
            return conversation

        except Exception as e:
            _logger.error(f"Error creando conversación: {str(e)}")
            return None

    def _create_message_from_notification(self, message_data, account):
        """
        Crea un mensaje en Odoo a partir de datos de la API.

        Args:
            message_data: datos del mensaje de la API
            account: mercadolibre.account record
        """
        try:
            from_user = str(message_data.get('from', {}).get('user_id', ''))
            seller_id = account.ml_user_id

            # Determinar dirección
            direction = 'outgoing' if from_user == seller_id else 'incoming'

            # Parsear fechas
            message_dates = message_data.get('message_date', {})
            created_date = message_dates.get('created')

            if created_date:
                created_date = datetime.fromisoformat(created_date.replace('Z', '+00:00'))

            message = self.env['mercadolibre.message'].create({
                'ml_message_id': message_data.get('id'),
                'conversation_id': self.id,
                'account_id': account.id,
                'body': message_data.get('text', ''),
                'direction': direction,
                'state': 'received' if direction == 'incoming' else 'sent',
                'is_read': direction == 'outgoing',
                'ml_date_created': created_date,
                'sender_id': from_user,
            })

            # Actualizar estado de conversación
            if direction == 'incoming':
                self.write({
                    'state': 'waiting',
                })

            return message

        except Exception as e:
            _logger.error(f"Error creando mensaje: {str(e)}")
            return None

    def _handle_message_read_notification(self, account, message_id, notification_data):
        """
        Maneja la notificación de mensaje leído.

        Args:
            account: mercadolibre.account record
            message_id: ID del mensaje en ML
            notification_data: datos de la notificación
        """
        try:
            # Buscar mensaje en Odoo
            message = self.env['mercadolibre.message'].search([
                ('ml_message_id', '=', message_id),
            ], limit=1)

            if message:
                message.write({
                    'is_read': True,
                    'state': 'delivered' if message.direction == 'outgoing' else 'received',
                })
                _logger.debug(f"Mensaje {message_id} marcado como leído")
                return {'status': 'ok', 'action': 'marked_read'}

            return {'status': 'ignored', 'reason': 'message not found'}

        except Exception as e:
            _logger.error(f"Error marcando mensaje como leído: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # =========================================================================
    # CRON JOBS
    # =========================================================================

    @api.model
    def cron_sync_conversations(self):
        """Cron para sincronizar conversaciones desde ML."""
        accounts = self.env['mercadolibre.account'].search([('active', '=', True)])

        for account in accounts:
            try:
                self._sync_conversations_for_account(account)
            except Exception as e:
                _logger.error(f"Error sincronizando conversaciones cuenta {account.name}: {e}")

    def _sync_conversations_for_account(self, account):
        """
        Sincroniza conversaciones de una cuenta desde ML.

        Args:
            account: mercadolibre.account record
        """
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)

        try:
            # Obtener packs recientes con mensajes
            endpoint = f'/messages/packs?seller_id={account.ml_user_id}'
            response = account._make_request('GET', endpoint)

            if not response or 'results' not in response:
                return

            for pack_data in response.get('results', []):
                pack_id = pack_data.get('pack_id') or pack_data.get('id')
                if pack_id:
                    # Buscar orden asociada
                    ml_order = self.env['mercadolibre.order'].search([
                        ('ml_pack_id', '=', str(pack_id)),
                        ('account_id', '=', account.id),
                    ], limit=1)

                    if ml_order:
                        conversation = self.get_or_create_for_order(ml_order)
                        if conversation:
                            conversation._sync_messages_from_ml()

            config.write({'last_sync_date': fields.Datetime.now()})

        except Exception as e:
            config._log(
                f'Error sincronizando conversaciones: {str(e)}',
                level='error',
                log_type='message_error'
            )
            raise
