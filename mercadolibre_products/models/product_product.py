# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # =====================================================
    # VINCULACION CON MERCADOLIBRE
    # =====================================================
    ml_item_id = fields.Many2one(
        'mercadolibre.item',
        string='Item ML Principal',
        help='Item de ML vinculado directamente a esta variante'
    )
    ml_variation_ids = fields.One2many(
        'mercadolibre.item.variation',
        'product_id',
        string='Variaciones ML'
    )
    ml_variation_count = fields.Integer(
        string='Variaciones ML',
        compute='_compute_ml_variation_count'
    )

    # SKU para ML
    ml_seller_sku = fields.Char(
        string='SKU MercadoLibre',
        help='SKU especifico para MercadoLibre (SELLER_SKU). Si vacio, usa default_code.'
    )
    ml_effective_sku = fields.Char(
        string='SKU Efectivo ML',
        compute='_compute_ml_effective_sku',
        help='SKU que se usa para vincular con ML'
    )

    # Estado ML
    ml_is_linked = fields.Boolean(
        string='Vinculado a ML',
        compute='_compute_ml_is_linked',
        store=True
    )
    ml_stock = fields.Float(
        string='Stock ML',
        compute='_compute_ml_stock',
        help='Stock en MercadoLibre'
    )
    ml_stock_difference = fields.Float(
        string='Diferencia Stock',
        compute='_compute_ml_stock',
        help='Diferencia entre Odoo y ML'
    )

    @api.depends('ml_variation_ids')
    def _compute_ml_variation_count(self):
        for record in self:
            record.ml_variation_count = len(record.ml_variation_ids)

    @api.depends('ml_seller_sku', 'default_code')
    def _compute_ml_effective_sku(self):
        for record in self:
            record.ml_effective_sku = record.ml_seller_sku or record.default_code or ''

    @api.depends('ml_item_id', 'ml_variation_ids', 'product_tmpl_id.ml_item_ids')
    def _compute_ml_is_linked(self):
        for record in self:
            record.ml_is_linked = bool(
                record.ml_item_id or
                record.ml_variation_ids or
                record.product_tmpl_id.ml_item_ids
            )

    @api.depends('ml_item_id', 'ml_variation_ids', 'ml_item_id.available_quantity',
                 'ml_variation_ids.available_quantity', 'qty_available')
    def _compute_ml_stock(self):
        for record in self:
            ml_stock = 0
            if record.ml_item_id:
                ml_stock = record.ml_item_id.available_quantity
            elif record.ml_variation_ids:
                ml_stock = sum(record.ml_variation_ids.mapped('available_quantity'))

            record.ml_stock = ml_stock
            record.ml_stock_difference = record.qty_available - ml_stock

    # =====================================================
    # OVERRIDE WRITE PARA AUTO-SYNC
    # =====================================================
    def write(self, vals):
        result = super().write(vals)

        # Auto-sync stock a ML si cambia qty_available
        if 'qty_available' in vals or self._context.get('force_ml_sync'):
            self._auto_sync_stock_to_ml()

        # Auto-sync precio a ML si cambia lst_price
        if 'lst_price' in vals:
            self._auto_sync_price_to_ml()

        return result

    def _auto_sync_stock_to_ml(self):
        """Sincroniza automaticamente el stock a ML si esta configurado"""
        for product in self:
            # Verificar si debe sincronizar
            if not product.ml_is_linked:
                continue

            template = product.product_tmpl_id
            if not template.ml_sync_enabled and not template.ml_auto_sync_stock:
                continue

            try:
                # Sincronizar item principal
                if product.ml_item_id and product.ml_item_id.auto_sync_stock:
                    product.ml_item_id.with_context(no_recursive_sync=True).action_sync_stock_to_ml()

                # Sincronizar variaciones
                for variation in product.ml_variation_ids:
                    if variation.item_id.auto_sync_stock:
                        variation.with_context(no_recursive_sync=True).action_sync_stock_to_ml()

                # Sincronizar items del template
                for item in template.ml_item_ids:
                    if item.auto_sync_stock and item.product_id == product:
                        item.with_context(no_recursive_sync=True).action_sync_stock_to_ml()

            except Exception as e:
                _logger.warning('Error en auto-sync stock para %s: %s', product.name, str(e))

    def _auto_sync_price_to_ml(self):
        """Sincroniza automaticamente el precio a ML si esta configurado"""
        for product in self:
            if not product.ml_is_linked:
                continue

            template = product.product_tmpl_id
            if not template.ml_sync_enabled and not template.ml_auto_sync_price:
                continue

            try:
                if product.ml_item_id and product.ml_item_id.auto_sync_price:
                    product.ml_item_id.with_context(no_recursive_sync=True).action_sync_price_to_ml()

                for item in template.ml_item_ids:
                    if item.auto_sync_price and item.product_id == product:
                        item.with_context(no_recursive_sync=True).action_sync_price_to_ml()

            except Exception as e:
                _logger.warning('Error en auto-sync precio para %s: %s', product.name, str(e))

    # =====================================================
    # ACCIONES
    # =====================================================
    def action_view_ml_items(self):
        """Ver items ML vinculados a esta variante"""
        self.ensure_one()

        item_ids = []
        if self.ml_item_id:
            item_ids.append(self.ml_item_id.id)

        # Items donde esta variante es el product_id
        items = self.env['mercadolibre.item'].search([
            ('product_id', '=', self.id)
        ])
        item_ids.extend(items.ids)

        # Items del template
        item_ids.extend(self.product_tmpl_id.ml_item_ids.ids)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Items MercadoLibre'),
            'res_model': 'mercadolibre.item',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', list(set(item_ids)))],
        }

    def action_view_ml_variations(self):
        """Ver variaciones ML vinculadas"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Variaciones MercadoLibre'),
            'res_model': 'mercadolibre.item.variation',
            'view_mode': 'tree,form',
            'domain': [('product_id', '=', self.id)],
        }

    def action_sync_stock_to_ml(self):
        """Sincroniza stock a ML manualmente"""
        errors = []
        success_count = 0

        for product in self:
            if not product.ml_is_linked:
                continue

            try:
                if product.ml_item_id:
                    product.ml_item_id.action_sync_stock_to_ml()
                    success_count += 1

                for variation in product.ml_variation_ids:
                    variation.action_sync_stock_to_ml()
                    success_count += 1

                for item in product.product_tmpl_id.ml_item_ids:
                    if item.product_id == product:
                        item.action_sync_stock_to_ml()
                        success_count += 1

            except Exception as e:
                errors.append(f'{product.name}: {str(e)}')

        if errors:
            raise UserError(_('Errores:\n') + '\n'.join(errors))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stock Sincronizado'),
                'message': _('Se sincronizaron %d items a MercadoLibre.') % success_count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_link_to_ml_item(self):
        """Abre wizard para vincular a item/variacion ML"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vincular a MercadoLibre'),
            'res_model': 'mercadolibre.product.link',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_id': self.id,
                'default_product_tmpl_id': self.product_tmpl_id.id,
                'default_link_mode': 'product_to_item',
            }
        }
