# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # === RECLAMOS ===
    ml_claim_ids = fields.One2many(
        'mercadolibre.claim',
        compute='_compute_ml_claim_ids',
        string='Reclamos ML'
    )
    ml_claim_count = fields.Integer(
        string='Num. Reclamos',
        compute='_compute_ml_claim_ids'
    )
    has_active_claim = fields.Boolean(
        string='Tiene Reclamo Activo',
        compute='_compute_ml_claim_ids'
    )

    # === DEVOLUCIONES ===
    ml_return_ids = fields.One2many(
        'mercadolibre.return',
        'sale_order_id',
        string='Devoluciones ML'
    )
    ml_return_count = fields.Integer(
        string='Num. Devoluciones',
        compute='_compute_ml_return_count'
    )

    # === ESTADO DE DEVOLUCION ===
    ml_return_status = fields.Selection([
        ('none', 'Sin Devolucion'),
        ('pending', 'Devolucion Pendiente'),
        ('in_transit', 'En Transito'),
        ('received', 'Mercancia Recibida'),
        ('completed', 'Completada'),
    ], string='Estado Devolucion ML', compute='_compute_ml_return_status', store=True)

    @api.depends('ml_order_id')
    def _compute_ml_claim_ids(self):
        ClaimModel = self.env['mercadolibre.claim']
        for record in self:
            if record.ml_order_id:
                claims = ClaimModel.search([
                    ('ml_order_id', '=', record.ml_order_id)
                ])
                record.ml_claim_ids = claims
                record.ml_claim_count = len(claims)
                record.has_active_claim = any(c.status == 'opened' for c in claims)
            else:
                record.ml_claim_ids = ClaimModel
                record.ml_claim_count = 0
                record.has_active_claim = False

    @api.depends('ml_return_ids')
    def _compute_ml_return_count(self):
        for record in self:
            record.ml_return_count = len(record.ml_return_ids)

    @api.depends('ml_return_ids', 'ml_return_ids.odoo_state', 'ml_return_ids.ml_status')
    def _compute_ml_return_status(self):
        for record in self:
            if not record.ml_return_ids:
                record.ml_return_status = 'none'
            else:
                # Obtener el estado mas reciente
                latest_return = record.ml_return_ids.sorted('create_date', reverse=True)[:1]
                if latest_return:
                    state_map = {
                        'pending': 'pending',
                        'return_created': 'pending',
                        'waiting_arrival': 'in_transit',
                        'received': 'received',
                        'reviewed': 'received',
                        'completed': 'completed',
                        'cancelled': 'none',
                        'error': 'pending',
                    }
                    record.ml_return_status = state_map.get(latest_return.odoo_state, 'pending')
                else:
                    record.ml_return_status = 'none'

    def action_view_ml_claims(self):
        """Ver reclamos ML asociados"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reclamos MercadoLibre'),
            'res_model': 'mercadolibre.claim',
            'view_mode': 'tree,form',
            'domain': [('ml_order_id', '=', self.ml_order_id)],
            'context': {'default_ml_order_id': self.ml_order_id},
        }

    def action_view_ml_returns(self):
        """Ver devoluciones ML asociadas"""
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Devoluciones MercadoLibre'),
            'res_model': 'mercadolibre.return',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }

        if len(self.ml_return_ids) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.ml_return_ids[0].id

        return action
