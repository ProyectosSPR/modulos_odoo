# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreMessagingSync(models.TransientModel):
    _name = 'mercadolibre.messaging.sync'
    _description = 'Wizard Sincronización Mensajería ML'

    # Selección de cuenta
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        domain="[('active', '=', True)]"
    )
    all_accounts = fields.Boolean(
        string='Todas las Cuentas',
        default=True
    )

    # Tipo de sincronización
    sync_type = fields.Selection([
        ('conversations', 'Solo Conversaciones'),
        ('messages', 'Solo Mensajes'),
        ('both', 'Conversaciones y Mensajes'),
    ], string='Tipo', default='both', required=True)

    # Opciones
    days_back = fields.Integer(
        string='Días Hacia Atrás',
        default=7,
        help='Sincronizar conversaciones de los últimos N días'
    )
    force_resync = fields.Boolean(
        string='Forzar Re-sincronización',
        default=False,
        help='Re-sincronizar aunque ya se haya sincronizado recientemente'
    )

    # Resultados
    result_message = fields.Text(
        string='Resultado',
        readonly=True
    )
    conversations_synced = fields.Integer(
        string='Conversaciones Sincronizadas',
        readonly=True
    )
    messages_synced = fields.Integer(
        string='Mensajes Sincronizados',
        readonly=True
    )
    errors_count = fields.Integer(
        string='Errores',
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Configurar'),
        ('running', 'Ejecutando'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], default='draft')

    @api.onchange('all_accounts')
    def _onchange_all_accounts(self):
        if self.all_accounts:
            self.account_id = False

    def action_sync(self):
        """Ejecuta la sincronización."""
        self.ensure_one()

        if not self.all_accounts and not self.account_id:
            raise UserError(_('Debe seleccionar una cuenta o marcar "Todas las Cuentas".'))

        self.write({
            'state': 'running',
            'conversations_synced': 0,
            'messages_synced': 0,
            'errors_count': 0,
            'result_message': '',
        })

        # Obtener cuentas a sincronizar
        if self.all_accounts:
            accounts = self.env['mercadolibre.account'].search([('active', '=', True)])
        else:
            accounts = self.account_id

        results = []
        total_conversations = 0
        total_messages = 0
        total_errors = 0

        for account in accounts:
            try:
                conv_count, msg_count = self._sync_account(account)
                total_conversations += conv_count
                total_messages += msg_count
                results.append(f"✓ {account.name}: {conv_count} conversaciones, {msg_count} mensajes")
            except Exception as e:
                total_errors += 1
                results.append(f"✗ {account.name}: Error - {str(e)}")
                _logger.error(f"Error sincronizando cuenta {account.name}: {e}")

        self.write({
            'state': 'done' if total_errors == 0 else 'error',
            'conversations_synced': total_conversations,
            'messages_synced': total_messages,
            'errors_count': total_errors,
            'result_message': '\n'.join(results),
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.messaging.sync',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _sync_account(self, account):
        """
        Sincroniza una cuenta específica.

        Args:
            account: mercadolibre.account record

        Returns:
            tuple: (conversations_count, messages_count)
        """
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)
        conversations_synced = 0
        messages_synced = 0

        if self.sync_type in ('conversations', 'both'):
            # Sincronizar conversaciones
            conversations_synced = self._sync_conversations(account)

        if self.sync_type in ('messages', 'both'):
            # Sincronizar mensajes de conversaciones existentes
            messages_synced = self._sync_messages(account)

        # Actualizar última sincronización
        config.write({'last_sync_date': fields.Datetime.now()})

        return conversations_synced, messages_synced

    def _sync_conversations(self, account):
        """Sincroniza conversaciones de una cuenta."""
        from datetime import datetime, timedelta

        # Calcular fecha límite
        date_from = datetime.now() - timedelta(days=self.days_back)

        # Obtener órdenes recientes con pack_id
        orders = self.env['mercadolibre.order'].search([
            ('account_id', '=', account.id),
            ('ml_pack_id', '!=', False),
            ('create_date', '>=', date_from.strftime('%Y-%m-%d')),
        ])

        count = 0
        for order in orders:
            try:
                conversation = self.env['mercadolibre.conversation'].get_or_create_for_order(order)
                if conversation:
                    count += 1
            except Exception as e:
                _logger.error(f"Error creando conversación para orden {order.ml_order_id}: {e}")

        return count

    def _sync_messages(self, account):
        """Sincroniza mensajes de conversaciones existentes."""
        # Obtener conversaciones activas
        conversations = self.env['mercadolibre.conversation'].search([
            ('account_id', '=', account.id),
            ('active', '=', True),
        ])

        count = 0
        for conversation in conversations:
            try:
                before_count = len(conversation.ml_message_ids)
                conversation._sync_messages_from_ml()
                after_count = len(conversation.ml_message_ids)
                count += (after_count - before_count)
            except Exception as e:
                _logger.error(f"Error sincronizando mensajes de conversación {conversation.id}: {e}")

        return count

    def action_close(self):
        """Cierra el wizard."""
        return {'type': 'ir.actions.act_window_close'}

    def action_view_conversations(self):
        """Abre la lista de conversaciones."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversaciones'),
            'res_model': 'mercadolibre.conversation',
            'view_mode': 'tree,form',
            'target': 'current',
        }
