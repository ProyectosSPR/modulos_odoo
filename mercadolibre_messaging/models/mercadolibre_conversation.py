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

    # Participantes
    buyer_id = fields.Char(string='ID Comprador', readonly=True)
    buyer_nickname = fields.Char(string='Nickname Comprador', readonly=True)
    seller_id = fields.Char(string='ID Vendedor', readonly=True)

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
    message_ids = fields.One2many(
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

    @api.depends('message_ids', 'message_ids.is_read', 'message_ids.direction')
    def _compute_is_unread(self):
        for record in self:
            unread = record.message_ids.filtered(
                lambda m: not m.is_read and m.direction == 'incoming'
            )
            record.unread_count = len(unread)
            record.is_unread = record.unread_count > 0

    def _compute_message_count(self):
        for record in self:
            record.message_count = len(record.message_ids)

    @api.depends('message_ids', 'message_ids.create_date', 'message_ids.body')
    def _compute_last_message(self):
        for record in self:
            last_msg = record.message_ids.sorted('create_date', reverse=True)[:1]
            if last_msg:
                record.last_message_date = last_msg.create_date
                record.last_message_preview = (last_msg.body or '')[:100]
                record.last_message_direction = last_msg.direction
            else:
                record.last_message_date = False
                record.last_message_preview = ''
                record.last_message_direction = False

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
                'seller_id': ml_order.account_id.ml_seller_id,
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
        self.message_ids.filtered(
            lambda m: not m.is_read and m.direction == 'incoming'
        ).write({'is_read': True})

    def action_sync_messages(self):
        """Sincroniza mensajes de la conversación desde ML."""
        self.ensure_one()
        self._sync_messages_from_ml()

    def _sync_messages_from_ml(self):
        """Sincroniza mensajes desde la API de ML."""
        self.ensure_one()

        if not self.ml_pack_id:
            return

        account = self.account_id
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)

        try:
            # Obtener mensajes de la API
            endpoint = f'/messages/packs/{self.ml_pack_id}/sellers/{account.ml_seller_id}'
            response = account._make_request('GET', endpoint)

            if not response or 'messages' not in response:
                config._log(
                    f'Sin mensajes para pack {self.ml_pack_id}',
                    level='debug',
                    log_type='message_sync'
                )
                return

            # Actualizar cap_available
            if 'conversation' in response:
                conv_data = response['conversation']
                self.write({
                    'cap_available': conv_data.get('cap_available', True),
                    'cap_checked_at': fields.Datetime.now(),
                })

            # Procesar mensajes
            for msg_data in response.get('messages', []):
                self._process_message_from_api(msg_data)

            config._log(
                f'Sincronizados {len(response.get("messages", []))} mensajes para pack {self.ml_pack_id}',
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
        direction = 'incoming' if from_id != self.account_id.ml_seller_id else 'outgoing'

        # Parsear fecha
        date_created = msg_data.get('date_created')
        if date_created:
            date_created = datetime.fromisoformat(date_created.replace('Z', '+00:00'))

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
            endpoint = f'/messages/packs?seller_id={account.ml_seller_id}'
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
