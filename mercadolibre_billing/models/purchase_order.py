# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    ml_billing_period_id = fields.Many2one(
        'mercadolibre.billing.period',
        string='Periodo ML/MP',
        ondelete='restrict',
        help='Periodo de facturación de MercadoLibre/MercadoPago'
    )
    ml_billing_detail_ids = fields.One2many(
        'mercadolibre.billing.detail',
        'purchase_order_id',
        string='Detalles de Facturación ML/MP'
    )
    ml_total_commission = fields.Monetary(
        string='Total Comisiones ML/MP',
        compute='_compute_ml_total_commission',
        store=True,
        currency_field='currency_id'
    )
    ml_detail_count = fields.Integer(
        string='Nº Detalles ML/MP',
        compute='_compute_ml_detail_count'
    )

    @api.depends('ml_billing_detail_ids', 'ml_billing_detail_ids.detail_amount')
    def _compute_ml_total_commission(self):
        for order in self:
            order.ml_total_commission = sum(
                order.ml_billing_detail_ids.mapped('detail_amount')
            )

    @api.depends('ml_billing_detail_ids')
    def _compute_ml_detail_count(self):
        for order in self:
            order.ml_detail_count = len(order.ml_billing_detail_ids)

    def action_view_ml_billing_details(self):
        """Smart button para ver detalles de facturación ML/MP"""
        self.ensure_one()

        return {
            'name': 'Detalles de Facturación ML/MP',
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.billing.detail',
            'view_mode': 'tree,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id}
        }

    def action_view_ml_billing_period(self):
        """Acción para ver el periodo de facturación"""
        self.ensure_one()

        if not self.ml_billing_period_id:
            return

        return {
            'name': 'Periodo de Facturación',
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.billing.period',
            'view_mode': 'form',
            'res_id': self.ml_billing_period_id.id,
        }
