# -*- coding: utf-8 -*-

from odoo import models, fields


class MercadolibreLog(models.Model):
    """Extensión del modelo de logs para mensajería"""
    _inherit = 'mercadolibre.log'

    log_type = fields.Selection(
        selection_add=[
            ('messaging', 'Mensajería'),
            ('message_sent', 'Mensaje Enviado'),
            ('message_received', 'Mensaje Recibido'),
            ('message_sync', 'Sincronización Mensajes'),
            ('message_error', 'Error Mensajería'),
            ('schedule_check', 'Verificación Horario'),
            ('auto_message', 'Mensaje Automático'),
        ],
        ondelete={
            'messaging': 'set default',
            'message_sent': 'set default',
            'message_received': 'set default',
            'message_sync': 'set default',
            'message_error': 'set default',
            'schedule_check': 'set default',
            'auto_message': 'set default',
        }
    )

    # Campos adicionales para mensajería
    conversation_id = fields.Many2one(
        'mercadolibre.conversation',
        string='Conversación',
        ondelete='set null',
        index=True
    )
    message_rule_id = fields.Many2one(
        'mercadolibre.message.rule',
        string='Regla de Mensaje',
        ondelete='set null'
    )
    ml_pack_id = fields.Char(
        string='Pack ID',
        index=True
    )
