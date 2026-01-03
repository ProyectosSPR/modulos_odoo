# -*- coding: utf-8 -*-
"""
Modelo para configurar productos excluidos del portal de facturación.
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class BillingExcludedProduct(models.Model):
    _name = 'billing.excluded.product'
    _description = 'Productos excluidos de facturación portal'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        ondelete='cascade',
        index=True
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Plantilla de Producto',
        related='product_id.product_tmpl_id',
        store=True
    )

    reason = fields.Text(
        string='Motivo de Exclusión',
        help='Razón por la cual este producto está excluido de facturación'
    )

    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está desmarcado, el producto no será excluido'
    )

    create_uid = fields.Many2one('res.users', string='Creado por', readonly=True)
    create_date = fields.Datetime(string='Fecha Creación', readonly=True)

    _sql_constraints = [
        ('product_unique', 'UNIQUE(product_id)',
         'Este producto ya está en la lista de excluidos.')
    ]

    def name_get(self):
        result = []
        for record in self:
            name = record.product_id.display_name or 'Sin producto'
            result.append((record.id, name))
        return result

    @api.model
    def get_excluded_product_ids(self):
        """
        Obtiene los IDs de productos excluidos activos.
        Método de utilidad para usar en otros modelos.
        """
        return self.search([('active', '=', True)]).mapped('product_id').ids

    @api.model
    def is_product_excluded(self, product_id):
        """
        Verifica si un producto específico está excluido.
        """
        return self.search_count([
            ('product_id', '=', product_id),
            ('active', '=', True)
        ]) > 0

    # =========================================
    # Triggers para recalcular órdenes afectadas
    # =========================================

    @api.model_create_multi
    def create(self, vals_list):
        """Al crear productos excluidos, recalcular órdenes afectadas."""
        records = super().create(vals_list)
        # Recalcular órdenes que contienen estos productos
        product_ids = records.filtered('active').mapped('product_id').ids
        if product_ids:
            self._recalculate_orders_for_products(product_ids, exclude=True)
        return records

    def write(self, vals):
        """Al modificar productos excluidos, recalcular órdenes afectadas."""
        # Guardar estado anterior para saber qué cambió
        products_before_active = self.filtered('active').mapped('product_id').ids

        result = super().write(vals)

        # Si cambió 'active' o 'product_id', recalcular
        if 'active' in vals or 'product_id' in vals:
            products_after_active = self.filtered('active').mapped('product_id').ids

            # Productos que fueron activados (excluir órdenes)
            newly_excluded = set(products_after_active) - set(products_before_active)
            if newly_excluded:
                self._recalculate_orders_for_products(list(newly_excluded), exclude=True)

            # Productos que fueron desactivados (re-habilitar órdenes)
            newly_included = set(products_before_active) - set(products_after_active)
            if newly_included:
                self._recalculate_orders_for_products(list(newly_included), exclude=False)

        return result

    def unlink(self):
        """Al eliminar productos excluidos, recalcular órdenes afectadas."""
        product_ids = self.filtered('active').mapped('product_id').ids
        result = super().unlink()
        # Re-habilitar órdenes que ya no tienen productos excluidos
        if product_ids:
            self._recalculate_orders_for_products(product_ids, exclude=False)
        return result

    @api.model
    def _recalculate_orders_for_products(self, product_ids, exclude=True):
        """
        Recalcula has_excluded_products e is_portal_billable para órdenes
        que contienen los productos especificados.

        Args:
            product_ids: Lista de IDs de productos
            exclude: True si los productos ahora están excluidos, False si fueron removidos
        """
        if not product_ids:
            return

        _logger.info(
            "Recalculando órdenes para productos %s (exclude=%s)",
            product_ids, exclude
        )

        # Buscar órdenes que contienen estos productos
        orders = self.env['sale.order'].search([
            ('order_line.product_id', 'in', product_ids)
        ])

        if not orders:
            _logger.info("No hay órdenes que contengan los productos especificados")
            return

        _logger.info("Encontradas %d órdenes para recalcular", len(orders))

        # Obtener lista completa de productos excluidos activos
        all_excluded_ids = self.get_excluded_product_ids()

        for order in orders:
            # Verificar si alguna línea tiene producto excluido
            has_excluded = any(
                line.product_id.id in all_excluded_ids
                for line in order.order_line
                if line.product_id
            )

            # Solo actualizar si cambió
            if order.has_excluded_products != has_excluded:
                order.write({'has_excluded_products': has_excluded})
                _logger.debug(
                    "Orden %s: has_excluded_products = %s",
                    order.name, has_excluded
                )

        _logger.info("Recálculo completado para %d órdenes", len(orders))

    def action_recalculate_all_orders(self):
        """
        Acción manual para recalcular todas las órdenes.
        Útil para sincronizar datos después de cambios masivos.
        """
        excluded_ids = self.get_excluded_product_ids()

        # Órdenes con productos excluidos que NO tienen la marca
        orders_to_mark = self.env['sale.order'].search([
            ('order_line.product_id', 'in', excluded_ids),
            ('has_excluded_products', '=', False)
        ])

        if orders_to_mark:
            orders_to_mark.write({'has_excluded_products': True})
            _logger.info("Marcadas %d órdenes con has_excluded_products=True", len(orders_to_mark))

        # Órdenes marcadas que ya NO tienen productos excluidos
        orders_to_unmark = self.env['sale.order'].search([
            ('has_excluded_products', '=', True)
        ]).filtered(
            lambda o: not any(
                line.product_id.id in excluded_ids
                for line in o.order_line
                if line.product_id
            )
        )

        if orders_to_unmark:
            orders_to_unmark.write({'has_excluded_products': False})
            _logger.info("Desmarcadas %d órdenes con has_excluded_products=False", len(orders_to_unmark))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Recálculo completado',
                'message': f'Marcadas: {len(orders_to_mark)}, Desmarcadas: {len(orders_to_unmark)}',
                'type': 'success',
                'sticky': False,
            }
        }
