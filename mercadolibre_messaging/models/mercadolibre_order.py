# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MercadolibreOrder(models.Model):
    """Extensión de mercadolibre.order para mensajería"""
    _inherit = 'mercadolibre.order'

    # Relación con conversación
    conversation_id = fields.Many2one(
        'mercadolibre.conversation',
        string='Conversación',
        compute='_compute_conversation',
        store=True
    )
    conversation_count = fields.Integer(
        string='Conversaciones',
        compute='_compute_conversation_count'
    )
    message_count = fields.Integer(
        string='Mensajes',
        compute='_compute_message_count'
    )
    unread_message_count = fields.Integer(
        string='Mensajes Sin Leer',
        compute='_compute_message_count'
    )

    # Último mensaje
    last_message_date = fields.Datetime(
        string='Último Mensaje',
        compute='_compute_last_message'
    )
    last_message_preview = fields.Char(
        string='Último Mensaje',
        compute='_compute_last_message'
    )

    @api.depends('ml_pack_id', 'account_id')
    def _compute_conversation(self):
        for record in self:
            if record.ml_pack_id and record.account_id:
                conversation = self.env['mercadolibre.conversation'].search([
                    ('ml_pack_id', '=', record.ml_pack_id),
                    ('account_id', '=', record.account_id.id),
                ], limit=1)
                record.conversation_id = conversation
            else:
                record.conversation_id = False

    def _compute_conversation_count(self):
        for record in self:
            record.conversation_count = 1 if record.conversation_id else 0

    def _compute_message_count(self):
        for record in self:
            if record.conversation_id:
                record.message_count = len(record.conversation_id.message_ids)
                record.unread_message_count = len(record.conversation_id.message_ids.filtered(
                    lambda m: not m.is_read and m.direction == 'incoming'
                ))
            else:
                record.message_count = 0
                record.unread_message_count = 0

    def _compute_last_message(self):
        for record in self:
            if record.conversation_id and record.conversation_id.message_ids:
                last_msg = record.conversation_id.message_ids.sorted('create_date', reverse=True)[:1]
                if last_msg:
                    record.last_message_date = last_msg.create_date
                    record.last_message_preview = (last_msg.body or '')[:80]
                else:
                    record.last_message_date = False
                    record.last_message_preview = ''
            else:
                record.last_message_date = False
                record.last_message_preview = ''

    def action_view_conversation(self):
        """Abre la conversación de la orden."""
        self.ensure_one()

        # Obtener o crear conversación
        if not self.conversation_id:
            conversation = self.env['mercadolibre.conversation'].get_or_create_for_order(self)
        else:
            conversation = self.conversation_id

        if not conversation:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Pack ID'),
                    'message': _('Esta orden no tiene un Pack ID asociado para mensajería.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversación'),
            'res_model': 'mercadolibre.conversation',
            'res_id': conversation.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_messages(self):
        """Abre los mensajes de la orden."""
        self.ensure_one()

        if not self.conversation_id:
            return self.action_view_conversation()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Mensajes'),
            'res_model': 'mercadolibre.message',
            'view_mode': 'tree,form',
            'domain': [('conversation_id', '=', self.conversation_id.id)],
            'context': {
                'default_conversation_id': self.conversation_id.id,
                'default_account_id': self.account_id.id,
            },
        }

    def action_send_message(self):
        """Abre wizard para enviar mensaje."""
        self.ensure_one()

        # Obtener o crear conversación
        if not self.conversation_id:
            conversation = self.env['mercadolibre.conversation'].get_or_create_for_order(self)
        else:
            conversation = self.conversation_id

        if not conversation:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Pack ID'),
                    'message': _('Esta orden no tiene un Pack ID asociado para mensajería.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Enviar Mensaje ML'),
            'res_model': 'mercadolibre.message.compose',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': conversation.id,
                'default_account_id': self.account_id.id,
                'default_ml_pack_id': self.ml_pack_id,
                'default_ml_order_id': self.id,
            },
        }

    def action_sync_messages(self):
        """Sincroniza mensajes de la orden."""
        self.ensure_one()

        if not self.conversation_id:
            conversation = self.env['mercadolibre.conversation'].get_or_create_for_order(self)
        else:
            conversation = self.conversation_id

        if conversation:
            conversation._sync_messages_from_ml()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Completada'),
                    'message': _('Mensajes sincronizados correctamente.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

    def write(self, vals):
        """Override para detectar cambios de estado y ejecutar reglas."""
        result = super().write(vals)

        # Si cambió el estado de la orden, verificar reglas
        if 'status' in vals:
            self._check_message_rules('order_status')

        return result

    def _check_message_rules(self, trigger_type):
        """
        Verifica y ejecuta reglas de mensajes automáticos.

        Args:
            trigger_type: 'order_status' o 'shipment_status'
        """
        for record in self:
            # Verificar si mensajería automática está habilitada
            config = self.env['mercadolibre.messaging.config'].get_config_for_account(record.account_id)
            if not config.auto_messages_enabled:
                continue

            # Obtener reglas aplicables
            matching_rules = self.env['mercadolibre.message.rule'].get_matching_rules(
                record,
                trigger_type=trigger_type if trigger_type != 'both' else None
            )

            for rule in matching_rules:
                try:
                    rule.execute_rule(record)
                except Exception as e:
                    _logger.error(f"Error ejecutando regla {rule.name} para orden {record.ml_order_id}: {e}")
                    config._log(
                        f'Error ejecutando regla {rule.name}: {str(e)}',
                        level='error',
                        log_type='message_error',
                        message_rule_id=rule.id,
                        ml_pack_id=record.ml_pack_id,
                    )
