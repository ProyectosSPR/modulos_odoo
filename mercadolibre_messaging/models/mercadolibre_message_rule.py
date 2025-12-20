# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MercadolibreMessageRule(models.Model):
    _name = 'mercadolibre.message.rule'
    _description = 'Regla de Mensaje Automático ML'
    _order = 'sequence, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de la regla'
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Plantilla a usar
    template_id = fields.Many2one(
        'mercadolibre.message.template',
        string='Plantilla',
        required=True,
        ondelete='restrict'
    )

    # Trigger - Estado de orden
    trigger_type = fields.Selection([
        ('order_status', 'Estado de Orden'),
        ('shipment_status', 'Estado de Envío'),
        ('both', 'Orden + Envío'),
    ], string='Tipo de Disparador', default='order_status', required=True)

    # Condiciones de orden (basadas en API de ML)
    order_status = fields.Selection([
        ('confirmed', 'Confirmado'),
        ('payment_required', 'Pago Requerido'),
        ('payment_in_process', 'Pago en Proceso'),
        ('partially_paid', 'Parcialmente Pagado'),
        ('paid', 'Pagado'),
        ('partially_refunded', 'Parcialmente Reembolsado'),
        ('pending_cancel', 'Cancelación Pendiente'),
        ('cancelled', 'Cancelado'),
    ], string='Estado de Orden',
       help='Estado de la orden que dispara el mensaje')

    # Condiciones de envío (basadas en API de ML)
    shipment_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('handling', 'En Preparación'),
        ('ready_to_ship', 'Listo para Enviar'),
        ('shipped', 'Enviado'),
        ('in_transit', 'En Tránsito'),
        ('out_for_delivery', 'En Reparto'),
        ('delivered', 'Entregado'),
        ('not_delivered', 'No Entregado'),
        ('returned', 'Devuelto'),
        ('cancelled', 'Cancelado'),
    ], string='Estado de Envío',
       help='Estado del envío que dispara el mensaje')

    # Tipo logístico (opcional)
    logistic_type = fields.Selection([
        ('cross_docking', 'Cross Docking (Mercado Envíos Full)'),
        ('drop_off', 'Drop Off (Dejar en punto)'),
        ('xd_drop_off', 'XD Drop Off'),
        ('custom', 'Custom (Envío propio)'),
        ('not_specified', 'No Especificado'),
    ], string='Tipo Logístico',
       help='Filtrar por tipo de logística. Vacío = Todos')

    # Timing
    delay_minutes = fields.Integer(
        string='Delay (minutos)',
        default=0,
        help='Minutos a esperar después del evento antes de enviar'
    )

    # Restricciones
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    account_ids = fields.Many2many(
        'mercadolibre.account',
        'ml_rule_account_rel',
        'rule_id',
        'account_id',
        string='Cuentas',
        help='Cuentas donde aplica la regla. Vacío = Todas'
    )

    # Control de ejecución
    max_executions_per_order = fields.Integer(
        string='Máx. por Orden',
        default=1,
        help='Máximo de veces que se puede ejecutar esta regla por orden'
    )
    only_first_message = fields.Boolean(
        string='Solo si No Hay Mensajes',
        default=False,
        help='Solo ejecutar si no se ha enviado ningún mensaje a esta conversación'
    )
    respect_schedule = fields.Boolean(
        string='Respetar Horario',
        default=True,
        help='Solo enviar dentro del horario de atención configurado'
    )

    # Estadísticas
    execution_count = fields.Integer(
        string='Ejecuciones',
        compute='_compute_execution_count'
    )
    last_execution = fields.Datetime(
        string='Última Ejecución'
    )

    def _compute_execution_count(self):
        for record in self:
            record.execution_count = self.env['mercadolibre.message'].search_count([
                ('rule_id', '=', record.id)
            ])

    @api.constrains('trigger_type', 'order_status', 'shipment_status')
    def _check_trigger_conditions(self):
        for record in self:
            if record.trigger_type == 'order_status' and not record.order_status:
                raise ValidationError(_(
                    'Debe seleccionar un estado de orden para el disparador'
                ))
            if record.trigger_type == 'shipment_status' and not record.shipment_status:
                raise ValidationError(_(
                    'Debe seleccionar un estado de envío para el disparador'
                ))
            if record.trigger_type == 'both':
                if not record.order_status or not record.shipment_status:
                    raise ValidationError(_(
                        'Debe seleccionar ambos estados (orden y envío) para el disparador'
                    ))

    def check_conditions(self, ml_order):
        """
        Verifica si las condiciones de la regla se cumplen para una orden.

        Args:
            ml_order: mercadolibre.order record

        Returns:
            bool: True si las condiciones se cumplen
        """
        self.ensure_one()

        # Verificar cuenta
        if self.account_ids and ml_order.account_id.id not in self.account_ids.ids:
            return False

        # Verificar tipo logístico
        if self.logistic_type:
            order_logistic = ml_order.logistic_type or 'not_specified'
            if order_logistic != self.logistic_type:
                return False

        # Verificar estado de orden
        if self.trigger_type in ('order_status', 'both'):
            if ml_order.status != self.order_status:
                return False

        # Verificar estado de envío
        if self.trigger_type in ('shipment_status', 'both'):
            shipment = ml_order.shipment_id
            if not shipment:
                return False
            if shipment.status != self.shipment_status:
                return False

        # Verificar ejecuciones previas
        if self.max_executions_per_order > 0:
            execution_count = self.env['mercadolibre.message'].search_count([
                ('rule_id', '=', self.id),
                ('ml_order_id', '=', ml_order.id),
            ])
            if execution_count >= self.max_executions_per_order:
                return False

        # Verificar si ya hay mensajes en la conversación
        if self.only_first_message:
            conversation = self.env['mercadolibre.conversation'].search([
                ('ml_pack_id', '=', ml_order.ml_pack_id),
            ], limit=1)
            if conversation and conversation.message_ids:
                outgoing_count = len(conversation.message_ids.filtered(
                    lambda m: m.direction == 'outgoing'
                ))
                if outgoing_count > 0:
                    return False

        return True

    @api.model
    def get_matching_rules(self, ml_order, trigger_type=None):
        """
        Obtiene todas las reglas que aplican a una orden.

        Args:
            ml_order: mercadolibre.order record
            trigger_type: str opcional para filtrar por tipo

        Returns:
            recordset de reglas que cumplen condiciones
        """
        domain = [('active', '=', True)]

        if trigger_type:
            domain.append(('trigger_type', '=', trigger_type))

        rules = self.search(domain, order='sequence')
        matching = self.env['mercadolibre.message.rule']

        for rule in rules:
            if rule.check_conditions(ml_order):
                matching |= rule

        return matching

    def execute_rule(self, ml_order):
        """
        Ejecuta la regla para una orden.

        Args:
            ml_order: mercadolibre.order record

        Returns:
            mercadolibre.message record o False
        """
        self.ensure_one()

        if not self.check_conditions(ml_order):
            _logger.debug(f"Regla {self.name}: condiciones no cumplidas para orden {ml_order.ml_order_id}")
            return False

        # Obtener o crear conversación
        conversation = self.env['mercadolibre.conversation'].get_or_create_for_order(ml_order)
        if not conversation:
            _logger.warning(f"Regla {self.name}: no se pudo obtener conversación para {ml_order.ml_order_id}")
            return False

        # Renderizar mensaje
        message_body = self.template_id.render_for_order(ml_order)

        # Verificar horario si está configurado
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(ml_order.account_id)

        if self.respect_schedule and config.schedule_id:
            if not config.schedule_id.is_within_schedule():
                # Encolar para envío posterior
                if config.queue_out_of_hours:
                    return self._queue_message(
                        conversation, message_body, ml_order,
                        delay_minutes=self.delay_minutes
                    )
                else:
                    _logger.info(f"Regla {self.name}: fuera de horario, no se envía")
                    return False

        # Crear mensaje en cola o enviar directamente
        if self.delay_minutes > 0:
            return self._queue_message(
                conversation, message_body, ml_order,
                delay_minutes=self.delay_minutes
            )
        else:
            return self._send_message(conversation, message_body, ml_order)

    def _queue_message(self, conversation, body, ml_order, delay_minutes=0):
        """Encola un mensaje para envío posterior."""
        from datetime import datetime, timedelta

        send_at = datetime.now() + timedelta(minutes=delay_minutes)

        queue_item = self.env['mercadolibre.message.queue'].create({
            'conversation_id': conversation.id,
            'account_id': ml_order.account_id.id,
            'body': body,
            'template_id': self.template_id.id,
            'rule_id': self.id,
            'ml_order_id': ml_order.id,
            'ml_option_id': self.template_id.ml_option_id,
            'scheduled_time': send_at,
            'state': 'pending',
        })

        _logger.info(f"Regla {self.name}: mensaje encolado para {send_at}")
        return queue_item

    def _send_message(self, conversation, body, ml_order):
        """Envía un mensaje directamente."""
        message = self.env['mercadolibre.message'].create({
            'conversation_id': conversation.id,
            'account_id': ml_order.account_id.id,
            'body': body,
            'direction': 'outgoing',
            'template_id': self.template_id.id,
            'rule_id': self.id,
            'ml_order_id': ml_order.id,
            'ml_option_id': self.template_id.ml_option_id,
            'state': 'draft',
        })

        # Intentar enviar
        message.action_send()

        # Actualizar última ejecución
        self.write({'last_execution': fields.Datetime.now()})

        return message

    def action_test_rule(self):
        """Wizard para probar la regla con una orden."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Probar Regla'),
            'res_model': 'mercadolibre.message.rule.test',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_rule_id': self.id}
        }
