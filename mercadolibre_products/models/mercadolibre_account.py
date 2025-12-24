# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MercadolibreAccount(models.Model):
    _inherit = 'mercadolibre.account'

    # =====================================================
    # RELACIONES CON PRODUCTOS
    # =====================================================
    item_ids = fields.One2many(
        'mercadolibre.item',
        'account_id',
        string='Items ML'
    )
    item_count = fields.Integer(
        string='Items',
        compute='_compute_item_count'
    )
    item_active_count = fields.Integer(
        string='Items Activos',
        compute='_compute_item_count'
    )
    item_linked_count = fields.Integer(
        string='Items Vinculados',
        compute='_compute_item_count'
    )

    product_sync_config_ids = fields.One2many(
        'mercadolibre.product.sync.config',
        'account_id',
        string='Configuraciones Sync Productos'
    )
    product_sync_config_count = fields.Integer(
        string='Configs Sync',
        compute='_compute_product_sync_config_count'
    )

    # =====================================================
    # ESTADISTICAS DE STOCK
    # =====================================================
    items_with_stock_alert = fields.Integer(
        string='Alertas Stock',
        compute='_compute_stock_alerts',
        help='Items con diferencia de stock entre ML y Odoo'
    )

    @api.depends('item_ids', 'item_ids.status', 'item_ids.is_linked')
    def _compute_item_count(self):
        for record in self:
            items = record.item_ids
            record.item_count = len(items)
            record.item_active_count = len(items.filtered(lambda i: i.status == 'active'))
            record.item_linked_count = len(items.filtered(lambda i: i.is_linked))

    @api.depends('product_sync_config_ids')
    def _compute_product_sync_config_count(self):
        for record in self:
            record.product_sync_config_count = len(record.product_sync_config_ids)

    @api.depends('item_ids', 'item_ids.stock_alert')
    def _compute_stock_alerts(self):
        for record in self:
            record.items_with_stock_alert = len(
                record.item_ids.filtered(lambda i: i.stock_alert)
            )

    # =====================================================
    # ACCIONES
    # =====================================================
    def action_view_items(self):
        """Ver items de esta cuenta"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Items MercadoLibre'),
            'res_model': 'mercadolibre.item',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }

    def action_view_product_sync_configs(self):
        """Ver configuraciones de sync de esta cuenta"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Configuraciones Sync Productos'),
            'res_model': 'mercadolibre.product.sync.config',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }

    def action_view_stock_alerts(self):
        """Ver items con alertas de stock"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alertas de Stock'),
            'res_model': 'mercadolibre.item',
            'view_mode': 'tree,form',
            'domain': [
                ('account_id', '=', self.id),
                ('stock_alert', '=', True),
            ],
            'context': {'default_account_id': self.id},
        }

    def action_sync_all_items(self):
        """Sincroniza todos los items desde ML"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizar Items'),
            'res_model': 'mercadolibre.product.sync',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_account_id': self.id,
            }
        }

    def action_auto_link_all_items(self):
        """Intenta vincular automaticamente todos los items"""
        self.ensure_one()
        items = self.item_ids.filtered(lambda i: not i.is_linked)
        result = items.action_auto_link_by_sku()
        return result
