# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreAccount(models.Model):
    _inherit = 'mercadolibre.account'

    # Orders
    order_ids = fields.One2many(
        'mercadolibre.order',
        'account_id',
        string='Ordenes ML'
    )
    order_count = fields.Integer(
        string='Cantidad Ordenes',
        compute='_compute_order_count'
    )

    # Buyers
    buyer_ids = fields.One2many(
        'mercadolibre.buyer',
        'account_id',
        string='Compradores'
    )
    buyer_count = fields.Integer(
        string='Cantidad Compradores',
        compute='_compute_buyer_count'
    )

    # Sync Configs
    order_sync_config_ids = fields.One2many(
        'mercadolibre.order.sync.config',
        'account_id',
        string='Configuraciones de Sync'
    )

    def _compute_order_count(self):
        for record in self:
            record.order_count = self.env['mercadolibre.order'].search_count([
                ('account_id', '=', record.id)
            ])

    def _compute_buyer_count(self):
        for record in self:
            record.buyer_count = self.env['mercadolibre.buyer'].search_count([
                ('account_id', '=', record.id)
            ])

    def action_view_orders(self):
        """Ver ordenes de la cuenta"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Ordenes - {self.name}',
            'res_model': 'mercadolibre.order',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }

    def action_view_buyers(self):
        """Ver compradores de la cuenta"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Compradores - {self.name}',
            'res_model': 'mercadolibre.buyer',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }

    def action_sync_orders(self):
        """Abre el wizard para sincronizar ordenes"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sincronizar Ordenes',
            'res_model': 'mercadolibre.order.sync',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_account_id': self.id},
        }
