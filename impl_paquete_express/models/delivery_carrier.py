# -*- coding: utf-8 -*-

from odoo import _, fields, models, api


class DeliveryCarrierMondialRelay(models.Model):
    _inherit = 'delivery.carrier'

    is_paquete_express = fields.Boolean(compute='_compute_is_paquete_express', search='_search_is_mondialrelay')

    @api.depends('product_id.default_code')
    def _compute_is_paquete_express(self):
        for c in self:
            c.is_paquete_express = c.product_id.default_code == "PX"