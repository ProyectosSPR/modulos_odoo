# -*- coding: utf-8 -*-

from odoo import models, fields, api


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

    @api.depends('state', 'invoice_status', 'ml_shipment_status')
    def _compute_is_portal_billable(self):
        """
        Una orden es facturable desde el portal si:
        - Estado de la orden es 'sale' o 'done'
        - No está completamente facturada
        - El envío está entregado (si tiene envío ML)
        """
        for order in self:
            is_billable = (
                order.state in ('sale', 'done') and
                order.invoice_status != 'invoiced'
            )

            # Si tiene estado de envío ML, debe estar entregado
            if order.ml_shipment_status:
                is_billable = is_billable and order.ml_shipment_status == 'delivered'

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

    @api.model
    def search_for_billing_portal(self, search_term, receiver_id=None, limit=50):
        """
        Busca órdenes para el portal de facturación.
        Busca en client_order_ref, name, ml_order_id, ml_pack_id
        """
        domain = [
            ('is_portal_billable', '=', True),
            '|', '|', '|',
            ('client_order_ref', 'ilike', search_term),
            ('name', 'ilike', search_term),
            ('ml_order_id', 'ilike', search_term),
            ('ml_pack_id', 'ilike', search_term),
        ]

        if receiver_id:
            domain = [('ml_receiver_id', '=', receiver_id)] + domain

        orders = self.search(domain, limit=limit)

        return [{
            'id': order.id,
            'name': order.name,
            'client_order_ref': order.client_order_ref,
            'ml_order_id': order.ml_order_id,
            'amount_total': order.amount_total,
            'date_order': order.date_order.strftime('%Y-%m-%d') if order.date_order else '',
            'invoice_status': order.invoice_status,
            'ml_shipment_status': order.ml_shipment_status,
            'is_billable': order.is_portal_billable,
        } for order in orders]
