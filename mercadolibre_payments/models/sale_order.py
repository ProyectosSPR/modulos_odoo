# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class SaleOrderPaymentExtend(models.Model):
    """
    Extiende sale.order para agregar campos de estado de pago y liberación de dinero.
    Estos campos son actualizados cuando se sincroniza mercadolibre.payment.
    """
    _inherit = 'sale.order'

    # =========================================================================
    # CAMPOS DE ESTADO DE PAGO (desde API de pagos)
    # =========================================================================
    ml_payment_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('authorized', 'Autorizado'),
        ('in_process', 'En Proceso'),
        ('in_mediation', 'En Mediación'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Cancelado'),
        ('refunded', 'Reembolsado'),
        ('charged_back', 'Contracargo'),
    ], string='Estado Pago MP', readonly=True, copy=False, tracking=True,
       help='Estado del pago en MercadoPago (sincronizado desde mercadolibre.payment)')

    # =========================================================================
    # CAMPOS DE LIBERACIÓN DE DINERO
    # =========================================================================
    ml_money_release_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('released', 'Liberado'),
        ('not_released', 'No Liberado'),
        ('unavailable', 'No Disponible'),
    ], string='Liberación Dinero', readonly=True, copy=False, tracking=True,
       default='not_released',
       help='Estado de liberación del dinero en MercadoPago. Por defecto "No Liberado" hasta que se sincronice el pago.')

    ml_money_release_date = fields.Datetime(
        string='Fecha Liberación',
        readonly=True,
        copy=False,
        help='Fecha en que el dinero fue liberado a tu cuenta'
    )

    # =========================================================================
    # RELACIÓN CON PAGOS
    # =========================================================================
    ml_payment_ids = fields.One2many(
        'mercadolibre.payment',
        compute='_compute_ml_payments',
        string='Pagos ML',
        help='Pagos de MercadoPago asociados a esta orden'
    )
    ml_payment_count = fields.Integer(
        string='Cantidad de Pagos',
        compute='_compute_ml_payments'
    )

    @api.depends('ml_order_id')
    def _compute_ml_payments(self):
        """Calcula los pagos ML asociados a esta orden"""
        Payment = self.env['mercadolibre.payment']
        for order in self:
            if order.ml_order_id:
                # Buscar pagos que coincidan con el order_id de ML
                payments = Payment.search([
                    '|',
                    ('mp_order_id', '=', order.ml_order_id),
                    ('mp_external_reference', '=', order.ml_order_id),
                ])
                order.ml_payment_ids = payments
                order.ml_payment_count = len(payments)
            else:
                order.ml_payment_ids = Payment
                order.ml_payment_count = 0

    def action_view_ml_payments(self):
        """Abre la vista de pagos ML asociados"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pagos MercadoPago',
            'res_model': 'mercadolibre.payment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.ml_payment_ids.ids)],
            'context': {'default_mp_order_id': self.ml_order_id},
        }

    def _update_from_ml_payment(self, payment):
        """
        Actualiza los campos de la orden desde un pago ML.

        Args:
            payment: mercadolibre.payment record
        """
        self.ensure_one()

        vals = {}

        # Actualizar estado de pago si el pago está aprobado o tiene estado relevante
        if payment.status:
            vals['ml_payment_status'] = payment.status

        # Actualizar estado de liberación
        if payment.money_release_status:
            vals['ml_money_release_status'] = payment.money_release_status

        if payment.money_release_date:
            vals['ml_money_release_date'] = payment.money_release_date

        if vals:
            _logger.info(
                'Actualizando sale.order %s desde pago %s: %s',
                self.name, payment.mp_payment_id, vals
            )
            self.write(vals)

            # Recalcular tags si hay configuración
            self._trigger_payment_tags_update()

    def _trigger_payment_tags_update(self):
        """
        Dispara la actualización de tags basándose en el estado de pago/liberación.
        """
        self.ensure_one()

        # Buscar el tipo logístico asociado
        if not hasattr(self, 'ml_logistic_type_id') or not self.ml_logistic_type_id:
            return

        logistic_type = self.ml_logistic_type_id

        # Llamar al método de cálculo de tags usando el estado de orden
        # Nota: money_release_status se maneja por separado si hay configuración
        try:
            logistic_type.calculate_and_apply_tags(
                self,
                shipment_status=self.ml_shipping_status,
                payment_status=self.ml_status,  # Usar estado de orden ML
            )

            # Agregar tags de money_release si hay configuración
            if self.ml_money_release_status:
                self._apply_money_release_tags()
        except Exception as e:
            _logger.warning(
                'Error actualizando tags de pago para %s: %s',
                self.name, str(e)
            )

    def _apply_money_release_tags(self):
        """
        Aplica tags basados en el estado de liberación de dinero.
        Los tags de money_release se AGREGAN a los existentes (no reemplazan).
        """
        self.ensure_one()

        if not self.ml_money_release_status:
            return

        PaymentConfig = self.env['mercadolibre.payment.status.config']

        # Obtener account_id y company_id de la orden
        account_id = self.ml_account_id.id if hasattr(self, 'ml_account_id') and self.ml_account_id else None
        company_id = self.company_id.id if self.company_id else None

        # Buscar tags para el estado de money_release
        money_release_tags = PaymentConfig.get_tags_for_money_release_status(
            self.ml_money_release_status,
            account_id=account_id,
            company_id=company_id
        )

        if money_release_tags:
            # Agregar tags (no reemplazar)
            current_tags = self.tag_ids
            new_tags = current_tags | money_release_tags

            if new_tags != current_tags:
                _logger.info(
                    '[MONEY_RELEASE_TAGS] Agregando tags a %s para status=%s: %s',
                    self.name, self.ml_money_release_status, money_release_tags.mapped('name')
                )
                self.write({'tag_ids': [(6, 0, new_tags.ids)]})
        else:
            _logger.debug(
                '[MONEY_RELEASE_TAGS] No hay tags configurados para status=%s',
                self.ml_money_release_status
            )
