# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Extensión de sale.order para mensajería ML"""
    _inherit = 'sale.order'

    # Relación con conversación ML
    ml_conversation_id = fields.Many2one(
        'mercadolibre.conversation',
        string='Conversación ML',
        compute='_compute_ml_conversation',
        store=True
    )
    ml_message_count = fields.Integer(
        string='Mensajes ML',
        compute='_compute_ml_message_count'
    )
    ml_unread_count = fields.Integer(
        string='ML Sin Leer',
        compute='_compute_ml_message_count'
    )

    # Último mensaje
    ml_last_message_date = fields.Datetime(
        string='Último Mensaje ML',
        compute='_compute_ml_last_message'
    )
    ml_last_message_preview = fields.Char(
        string='Último Mensaje ML',
        compute='_compute_ml_last_message'
    )

    # Indicador visual
    ml_has_unread = fields.Boolean(
        string='Tiene Mensajes Sin Leer',
        compute='_compute_ml_message_count'
    )

    @api.depends('ml_order_ids', 'ml_order_ids.conversation_id')
    def _compute_ml_conversation(self):
        for record in self:
            if record.ml_order_ids:
                # Tomar la conversación de la primera orden ML con conversación
                for ml_order in record.ml_order_ids:
                    if ml_order.conversation_id:
                        record.ml_conversation_id = ml_order.conversation_id
                        break
                else:
                    record.ml_conversation_id = False
            else:
                record.ml_conversation_id = False

    def _compute_ml_message_count(self):
        for record in self:
            if record.ml_conversation_id:
                record.ml_message_count = len(record.ml_conversation_id.message_ids)
                unread = record.ml_conversation_id.message_ids.filtered(
                    lambda m: not m.is_read and m.direction == 'incoming'
                )
                record.ml_unread_count = len(unread)
                record.ml_has_unread = record.ml_unread_count > 0
            else:
                record.ml_message_count = 0
                record.ml_unread_count = 0
                record.ml_has_unread = False

    def _compute_ml_last_message(self):
        for record in self:
            if record.ml_conversation_id and record.ml_conversation_id.message_ids:
                last_msg = record.ml_conversation_id.message_ids.sorted('create_date', reverse=True)[:1]
                if last_msg:
                    record.ml_last_message_date = last_msg.create_date
                    record.ml_last_message_preview = (last_msg.body or '')[:100]
                else:
                    record.ml_last_message_date = False
                    record.ml_last_message_preview = ''
            else:
                record.ml_last_message_date = False
                record.ml_last_message_preview = ''

    def action_view_ml_conversation(self):
        """Abre la conversación ML asociada."""
        self.ensure_one()

        if not self.ml_conversation_id:
            # Intentar crear conversación desde orden ML
            if self.ml_order_ids:
                ml_order = self.ml_order_ids[0]
                conversation = self.env['mercadolibre.conversation'].get_or_create_for_order(ml_order)
                if conversation:
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Conversación MercadoLibre'),
                        'res_model': 'mercadolibre.conversation',
                        'res_id': conversation.id,
                        'view_mode': 'form',
                        'target': 'current',
                    }

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Conversación'),
                    'message': _('Esta orden no tiene una conversación ML asociada.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversación MercadoLibre'),
            'res_model': 'mercadolibre.conversation',
            'res_id': self.ml_conversation_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_ml_messages(self):
        """Abre los mensajes ML en vista lista."""
        self.ensure_one()

        if not self.ml_conversation_id:
            return self.action_view_ml_conversation()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Mensajes MercadoLibre'),
            'res_model': 'mercadolibre.message',
            'view_mode': 'tree,form',
            'domain': [('conversation_id', '=', self.ml_conversation_id.id)],
            'context': {
                'default_conversation_id': self.ml_conversation_id.id,
            },
        }

    def action_send_ml_message(self):
        """Abre wizard para enviar mensaje ML."""
        self.ensure_one()

        # Verificar que sea orden ML
        if not self.ml_order_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No es Orden ML'),
                    'message': _('Esta orden de venta no está asociada a MercadoLibre.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        ml_order = self.ml_order_ids[0]

        # Obtener o crear conversación
        if not self.ml_conversation_id:
            conversation = self.env['mercadolibre.conversation'].get_or_create_for_order(ml_order)
        else:
            conversation = self.ml_conversation_id

        if not conversation:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Pack ID'),
                    'message': _('No se puede crear conversación sin Pack ID.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Enviar Mensaje MercadoLibre'),
            'res_model': 'mercadolibre.message.compose',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': conversation.id,
                'default_account_id': ml_order.account_id.id,
                'default_ml_pack_id': ml_order.ml_pack_id,
                'default_ml_order_id': ml_order.id,
                'default_sale_order_id': self.id,
            },
        }

    def action_sync_ml_messages(self):
        """Sincroniza mensajes de ML."""
        self.ensure_one()

        if self.ml_conversation_id:
            self.ml_conversation_id._sync_messages_from_ml()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Completada'),
                    'message': _('Mensajes de MercadoLibre sincronizados.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        elif self.ml_order_ids:
            ml_order = self.ml_order_ids[0]
            conversation = self.env['mercadolibre.conversation'].get_or_create_for_order(ml_order)
            if conversation:
                conversation._sync_messages_from_ml()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sincronización Completada'),
                        'message': _('Mensajes de MercadoLibre sincronizados.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sin Datos'),
                'message': _('No hay datos de MercadoLibre para sincronizar.'),
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_mark_ml_read(self):
        """Marca los mensajes ML como leídos."""
        self.ensure_one()

        if self.ml_conversation_id:
            self.ml_conversation_id.action_mark_read()
