# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreOrderItem(models.Model):
    _name = 'mercadolibre.order.item'
    _description = 'Item de Orden MercadoLibre'
    _order = 'id'

    order_id = fields.Many2one(
        'mercadolibre.order',
        string='Orden',
        required=True,
        ondelete='cascade'
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        related='order_id.account_id',
        store=True
    )

    # Item Info
    ml_item_id = fields.Char(
        string='Item ID',
        index=True,
        help='ID del item/publicacion en MercadoLibre'
    )
    title = fields.Char(
        string='Titulo',
        help='Titulo del producto'
    )
    category_id = fields.Char(
        string='Categoria ML',
        help='ID de categoria en MercadoLibre'
    )
    variation_id = fields.Char(
        string='Variacion ID',
        help='ID de la variacion del producto'
    )
    seller_sku = fields.Char(
        string='SKU',
        index=True,
        help='SKU del vendedor'
    )
    condition = fields.Selection([
        ('new', 'Nuevo'),
        ('used', 'Usado'),
        ('refurbished', 'Reacondicionado'),
    ], string='Condicion')

    # Quantities and Prices
    quantity = fields.Integer(
        string='Cantidad',
        default=1
    )
    unit_price = fields.Float(
        string='Precio Unitario',
        digits=(16, 2),
        help='Precio unitario final (con descuentos aplicados)'
    )
    full_unit_price = fields.Float(
        string='Precio Original',
        digits=(16, 2),
        help='Precio unitario original (sin descuentos)'
    )
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        digits=(16, 2)
    )

    # Fees
    sale_fee = fields.Float(
        string='Comision',
        digits=(16, 2),
        help='Comision de venta de MercadoLibre'
    )
    listing_type_id = fields.Char(
        string='Tipo Publicacion',
        help='Tipo de publicacion (gold_special, gold_pro, etc.)'
    )

    # Discount info
    has_discount = fields.Boolean(
        string='Tiene Descuento',
        compute='_compute_has_discount',
        store=True
    )
    discount_amount = fields.Float(
        string='Monto Descuento',
        compute='_compute_has_discount',
        store=True,
        digits=(16, 2)
    )

    # Product Link
    product_id = fields.Many2one(
        'product.product',
        string='Producto Odoo',
        compute='_compute_product_id',
        store=True
    )

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.quantity * record.unit_price

    @api.depends('unit_price', 'full_unit_price')
    def _compute_has_discount(self):
        for record in self:
            if record.full_unit_price and record.full_unit_price > record.unit_price:
                record.has_discount = True
                record.discount_amount = (record.full_unit_price - record.unit_price) * record.quantity
            else:
                record.has_discount = False
                record.discount_amount = 0.0

    @api.depends('seller_sku')
    def _compute_product_id(self):
        """Busca el producto de Odoo por SKU"""
        for record in self:
            if record.seller_sku:
                product = self.env['product.product'].search([
                    ('default_code', '=', record.seller_sku)
                ], limit=1)
                record.product_id = product.id if product else False
            else:
                record.product_id = False
