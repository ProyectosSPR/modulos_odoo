# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    ml_billing_period_id = fields.Many2one(
        'mercadolibre.billing.period',
        string='Periodo ML/MP',
        ondelete='restrict',
        help='Periodo de facturación de MercadoLibre/MercadoPago'
    )
    ml_is_commission_invoice = fields.Boolean(
        string='Es Factura de Comisión ML/MP',
        default=False,
        help='Indica si esta factura es de comisiones de MercadoLibre/MercadoPago'
    )
    ml_billing_detail_ids = fields.Many2many(
        'mercadolibre.billing.detail',
        'account_move_ml_billing_detail_rel',
        'move_id',
        'detail_id',
        string='Detalles de Facturación ML/MP'
    )
    ml_detail_count = fields.Integer(
        string='Nº Detalles ML/MP',
        compute='_compute_ml_detail_count'
    )

    @api.depends('ml_billing_detail_ids')
    def _compute_ml_detail_count(self):
        for move in self:
            move.ml_detail_count = len(move.ml_billing_detail_ids)

    def action_view_ml_billing_details(self):
        """Smart button para ver detalles de facturación ML/MP"""
        self.ensure_one()

        return {
            'name': 'Detalles de Facturación ML/MP',
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.billing.detail',
            'view_mode': 'tree,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {'default_invoice_id': self.id}
        }
