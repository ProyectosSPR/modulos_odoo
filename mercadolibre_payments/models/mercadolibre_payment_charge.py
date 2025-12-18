# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibrePaymentCharge(models.Model):
    _name = 'mercadolibre.payment.charge'
    _description = 'Cargo/Comision de Pago MercadoPago'
    _order = 'payment_id, id'

    # Mapping of charge types to friendly labels
    CHARGE_TYPE_LABELS = {
        # MercadoPago/MercadoLibre fees
        'mercadopago_fee': 'Comision MercadoPago',
        'meli_fee': 'Comision MercadoLibre',
        'ml_fee': 'Comision MercadoLibre',
        'application_fee': 'Comision Aplicacion',
        'financing_fee': 'Comision Financiamiento',

        # Shipping fees
        'shipping_fee': 'Comision Envio',
        'shp_fulfillment': 'Fulfillment (Envio Full)',
        'shp_cross_docking': 'Cross Docking',
        'shp_colect': 'Colecta Envio',

        # Cards and payments
        'cards_spread': 'Spread Tarjetas',
        'card_fee': 'Comision Tarjeta',

        # Coupons and discounts
        'coupon_fee': 'Comision Cupon',
        'coupon_rebate': 'Descuento Cupon',
        'coupon_code': 'Codigo Cupon',
        'discount_fee': 'Comision Descuento',
        'discount': 'Descuento',

        # Cashback and rewards
        'cashback': 'Cashback',
        'cashback-crypto': 'Cashback Crypto',
        'loyalty': 'Puntos Lealtad',

        # Other
        'tax': 'Impuesto',
        'other': 'Otro',
    }

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

    # Changed from Selection to Char to accept any charge type from API
    charge_type = fields.Char(
        string='Tipo de Cargo',
        required=True,
        index=True,
        help='Tipo de cargo segun MercadoPago API'
    )

    charge_type_display = fields.Char(
        string='Tipo',
        compute='_compute_charge_type_display',
        store=True,
        help='Etiqueta amigable del tipo de cargo'
    )

    fee_payer = fields.Char(
        string='Pagado por',
        help='Quien paga este cargo (collector/payer/ml)'
    )

    fee_payer_display = fields.Char(
        string='Pagador',
        compute='_compute_fee_payer_display',
        store=True
    )

    amount = fields.Float(
        string='Monto',
        digits=(16, 2)
    )

    @api.depends('charge_type')
    def _compute_charge_type_display(self):
        for record in self:
            record.charge_type_display = self.CHARGE_TYPE_LABELS.get(
                record.charge_type,
                record.charge_type.replace('_', ' ').title() if record.charge_type else 'Desconocido'
            )

    @api.depends('fee_payer')
    def _compute_fee_payer_display(self):
        payer_labels = {
            'collector': 'Vendedor',
            'payer': 'Comprador',
            'ml': 'MercadoLibre',
        }
        for record in self:
            record.fee_payer_display = payer_labels.get(
                record.fee_payer,
                record.fee_payer.title() if record.fee_payer else ''
            )

    @api.depends('charge_type', 'charge_type_display', 'amount')
    def _compute_name(self):
        for record in self:
            label = record.charge_type_display or 'Cargo'
            record.name = f'{label}: ${record.amount:.2f}'
