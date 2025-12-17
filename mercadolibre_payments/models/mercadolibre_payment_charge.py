# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibrePaymentCharge(models.Model):
    _name = 'mercadolibre.payment.charge'
    _description = 'Cargo/Comision de Pago MercadoPago'
    _order = 'payment_id, id'

    name = fields.Char(
        string='Descripcion',
        compute='_compute_name',
        store=True
    )
    payment_id = fields.Many2one(
        'mercadolibre.payment',
        string='Pago',
        required=True,
        ondelete='cascade'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='payment_id.company_id',
        store=True,
        readonly=True
    )

    charge_type = fields.Selection([
        ('mercadopago_fee', 'Comision MercadoPago'),
        ('coupon_fee', 'Comision Cupon'),
        ('financing_fee', 'Comision Financiamiento'),
        ('shipping_fee', 'Comision Envio'),
        ('application_fee', 'Comision Aplicacion'),
        ('discount_fee', 'Comision Descuento'),
        ('other', 'Otro'),
    ], string='Tipo de Cargo', required=True)

    fee_payer = fields.Selection([
        ('collector', 'Vendedor'),
        ('payer', 'Comprador'),
    ], string='Pagado por')

    amount = fields.Float(
        string='Monto',
        digits=(16, 2)
    )

    @api.depends('charge_type', 'amount')
    def _compute_name(self):
        type_labels = {
            'mercadopago_fee': 'Comision MercadoPago',
            'coupon_fee': 'Comision Cupon',
            'financing_fee': 'Comision Financiamiento',
            'shipping_fee': 'Comision Envio',
            'application_fee': 'Comision Aplicacion',
            'discount_fee': 'Comision Descuento',
            'other': 'Otro Cargo',
        }
        for record in self:
            label = type_labels.get(record.charge_type, 'Cargo')
            record.name = f'{label}: ${record.amount:.2f}'
