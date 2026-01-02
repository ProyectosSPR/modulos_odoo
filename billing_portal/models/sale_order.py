# -*- coding: utf-8 -*-
"""
Extensión del modelo sale.order para el portal de facturación.
"""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Campos de MercadoLibre
    ml_order_id = fields.Char(
        string='Order ID (ML)',
        index=True
    )

    ml_pack_id = fields.Char(
        string='Pack ID (ML)',
        index=True
    )

    ml_receiver_id = fields.Char(
        string='Receiver ID (ML)',
        index=True
    )

    # Estado de entrega ML
    ml_shipment_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('shipped', 'Enviado'),
        ('delivered', 'Entregado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado Envío ML')

    # Estado de pago ML
    ml_payment_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('released', 'Liberado'),
    ], string='Estado Pago ML')

    # Partner de facturación (diferente al partner original de la orden)
    billing_partner_id = fields.Many2one(
        'res.partner',
        string='Cliente para Facturación',
        help='Cliente al que se emitirá la factura (datos fiscales del CSF)'
    )

    # Solicitudes de facturación relacionadas
    billing_request_ids = fields.Many2many(
        'billing.request',
        'billing_request_sale_order_rel',
        'order_id',
        'request_id',
        string='Solicitudes de Facturación'
    )

    billing_request_count = fields.Integer(
        compute='_compute_billing_request_count',
        string='# Solicitudes'
    )

    # Indica si es facturable desde portal
    is_portal_billable = fields.Boolean(
        compute='_compute_is_portal_billable',
        string='Facturable desde Portal',
        store=True
    )

    def _compute_billing_request_count(self):
        for order in self:
            order.billing_request_count = len(order.billing_request_ids)

    # Campo para indicar si tiene productos excluidos
    has_excluded_products = fields.Boolean(
        compute='_compute_has_excluded_products',
        string='Tiene Productos Excluidos',
        store=True
    )

    @api.depends('order_line.product_id')
    def _compute_has_excluded_products(self):
        """
        Verifica si la orden contiene algún producto excluido de facturación.
        """
        # Obtener IDs de productos excluidos una sola vez
        excluded_product_ids = self.env['billing.excluded.product'].get_excluded_product_ids()

        for order in self:
            if not excluded_product_ids:
                order.has_excluded_products = False
            else:
                # Verificar si alguna línea tiene un producto excluido
                order.has_excluded_products = any(
                    line.product_id.id in excluded_product_ids
                    for line in order.order_line
                    if line.product_id
                )

    @api.depends('state', 'invoice_status', 'ml_shipment_status', 'has_excluded_products')
    def _compute_is_portal_billable(self):
        """
        Una orden es facturable desde el portal si:
        - Estado de la orden es 'sale' o 'done'
        - No está completamente facturada
        - El envío está entregado (si tiene envío ML)
        - No contiene productos excluidos
        """
        for order in self:
            is_billable = (
                order.state in ('sale', 'done') and
                order.invoice_status != 'invoiced'
            )

            # Si tiene estado de envío ML, debe estar entregado
            if order.ml_shipment_status:
                is_billable = is_billable and order.ml_shipment_status == 'delivered'

            # Excluir si tiene productos excluidos
            if order.has_excluded_products:
                is_billable = False

            order.is_portal_billable = is_billable

    def action_view_billing_requests(self):
        """Ver solicitudes de facturación de esta orden"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Solicitudes de Facturación',
            'res_model': 'billing.request',
            'view_mode': 'tree,form',
            'domain': [('order_ids', 'in', self.id)],
        }

    def get_billing_eligibility(self):
        """
        Verifica si una orden es elegible para facturación.
        Retorna: (is_billable: bool, reason: str or None)
        """
        self.ensure_one()

        # Verificar estado de la orden
        if self.state not in ('sale', 'done'):
            state_labels = dict(self._fields['state'].selection)
            return False, f"La orden está en estado '{state_labels.get(self.state, self.state)}'"

        # Verificar si ya está facturada
        if self.invoice_status == 'invoiced':
            return False, "La orden ya está completamente facturada"

        # Verificar estado de envío (OBLIGATORIO para ML)
        if self.ml_shipment_status and self.ml_shipment_status != 'delivered':
            shipment_labels = {
                'pending': 'pendiente',
                'shipped': 'en camino',
                'cancelled': 'cancelado',
            }
            status_text = shipment_labels.get(self.ml_shipment_status, self.ml_shipment_status)
            return False, f"El envío aún no ha sido entregado (estado: {status_text})"

        # Verificar si no tiene nada que facturar
        if self.invoice_status == 'no':
            return False, "No hay nada que facturar en esta orden"

        # Verificar si tiene productos excluidos
        if self.has_excluded_products:
            return False, "La orden contiene productos excluidos de facturación"

        return True, None
