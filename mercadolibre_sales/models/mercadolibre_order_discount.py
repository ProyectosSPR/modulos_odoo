# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreOrderDiscount(models.Model):
    _name = 'mercadolibre.order.discount'
    _description = 'Descuento de Orden MercadoLibre'
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

    # Discount Type
    discount_type = fields.Selection([
        ('coupon', 'Cupon'),
        ('discount', 'Descuento/Promocion'),
        ('cashback', 'Cashback'),
    ], string='Tipo', required=True)

    # Item Info
    ml_item_id = fields.Char(
        string='Item ID',
        help='ID del item al que aplica el descuento'
    )
    quantity = fields.Integer(
        string='Cantidad',
        default=1
    )

    # Amounts - Esta es la parte clave del co-fondeo
    total_amount = fields.Float(
        string='Descuento Total',
        digits=(16, 2),
        help='Monto total del descuento que recibe el comprador'
    )
    seller_amount = fields.Float(
        string='Aporte Vendedor',
        digits=(16, 2),
        help='Porcion del descuento a cargo del vendedor'
    )
    meli_amount = fields.Float(
        string='Aporte MercadoLibre',
        compute='_compute_meli_amount',
        store=True,
        digits=(16, 2),
        help='Porcion del descuento a cargo de MercadoLibre (co-fondeo)'
    )

    # Percentages (calculated)
    seller_percentage = fields.Float(
        string='% Vendedor',
        compute='_compute_percentages',
        store=True,
        digits=(5, 2)
    )
    meli_percentage = fields.Float(
        string='% MercadoLibre',
        compute='_compute_percentages',
        store=True,
        digits=(5, 2)
    )

    # Campaign/Supplier Info
    meli_campaign = fields.Char(
        string='Campana ML',
        help='ID de la campana de MercadoLibre (ej: P-MLA4944001)'
    )
    offer_id = fields.Char(
        string='ID Oferta',
        help='ID de la oferta aplicada'
    )
    funding_mode = fields.Char(
        string='Modo Fondeo',
        help='Tipo de financiamiento (ej: sale_fee)'
    )

    # Coupon specific
    coupon_id = fields.Char(
        string='ID Cupon',
        help='ID del cupon si aplica'
    )

    # Cashback specific
    cashback_id = fields.Char(
        string='ID Cashback',
        help='ID del cashback si aplica'
    )

    @api.depends('total_amount', 'seller_amount')
    def _compute_meli_amount(self):
        for record in self:
            record.meli_amount = record.total_amount - record.seller_amount

    @api.depends('total_amount', 'seller_amount')
    def _compute_percentages(self):
        for record in self:
            if record.total_amount > 0:
                record.seller_percentage = (record.seller_amount / record.total_amount) * 100
                record.meli_percentage = ((record.total_amount - record.seller_amount) / record.total_amount) * 100
            else:
                record.seller_percentage = 0.0
                record.meli_percentage = 0.0
