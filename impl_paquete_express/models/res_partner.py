# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class ResPartnerMondialRelay(models.Model):
    _inherit = 'res.partner'

    is_paquete_express = fields.Boolean(compute='_compute_is_paquete_express')

    @api.depends('ref')
    def _compute_is_paquete_express(self):
        for p in self:
            p.is_paquete_express = p.ref and p.ref.startswith('PX#')

    @api.model
    def _paquete_express_search_or_create(self, data):
        ref = 'PX#%s' % data['id']
        partner = self.search([
            ('id', 'child_of', self.commercial_partner_id.ids),
            ('ref', '=', ref),
            # fast check that address always the same
            ('street', '=', data['street']),
            ('zip', '=', data['zip']),
        ])
        if not partner:
            partner = self.create({
                'ref': ref,
                'name': data['name'],
                'street': data['street'],
                'street2': data['street2'],
                'zip': data['zip'],
                'state_id': data['state_id'],
                'email': data['email'],
                'phone': data['phone'],
                'country_id': self.env.ref('base.%s' % data['country_code']).id,
                'type': 'delivery',
                'parent_id': self.id,
            })
        return partner
