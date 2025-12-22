# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Campos para integración con MercadoLibre
    ml_receiver_id = fields.Char(
        string='Receiver ID (MercadoLibre)',
        index=True,
        help='ID del comprador en MercadoLibre'
    )

    ml_nickname = fields.Char(
        string='Nickname ML'
    )

    # Contador de solicitudes de facturación
    billing_request_count = fields.Integer(
        string='Solicitudes de Facturación',
        compute='_compute_billing_request_count'
    )

    billing_request_ids = fields.One2many(
        'billing.request',
        'partner_id',
        string='Solicitudes'
    )

    # Datos fiscales adicionales
    csf_validated = fields.Boolean(
        string='CSF Validado',
        default=False,
        help='Indica si los datos fiscales fueron validados con CSF'
    )

    csf_validation_date = fields.Datetime(
        string='Fecha Validación CSF'
    )

    def _compute_billing_request_count(self):
        for partner in self:
            partner.billing_request_count = self.env['billing.request'].search_count([
                ('partner_id', '=', partner.id)
            ])

    def action_view_billing_requests(self):
        """Acción para ver las solicitudes de facturación del cliente"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Solicitudes de Facturación',
            'res_model': 'billing.request',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id}
        }
