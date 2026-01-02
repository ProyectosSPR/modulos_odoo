# -*- coding: utf-8 -*-
"""
Modelo para configurar productos excluidos del portal de facturación.
"""

from odoo import models, fields, api


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
