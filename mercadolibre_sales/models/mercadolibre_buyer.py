# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreBuyer(models.Model):
    _name = 'mercadolibre.buyer'
    _description = 'Comprador MercadoLibre'
    _order = 'nickname'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='restrict'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='account_id.company_id',
        store=True
    )

    # MercadoLibre Info
    ml_buyer_id = fields.Char(
        string='Buyer ID',
        required=True,
        index=True,
        help='ID del comprador en MercadoLibre'
    )
    nickname = fields.Char(
        string='Nickname',
        index=True
    )
    first_name = fields.Char(
        string='Primer Nombre'
    )
    last_name = fields.Char(
        string='Apellido'
    )
    full_name = fields.Char(
        string='Nombre Completo',
        compute='_compute_full_name',
        store=True
    )
    email = fields.Char(
        string='Email',
        index=True
    )

    # Phone
    phone = fields.Char(
        string='Telefono'
    )
    phone_area_code = fields.Char(
        string='Codigo Area'
    )

    # Address
    street = fields.Char(
        string='Direccion'
    )
    street_number = fields.Char(
        string='Numero'
    )
    city = fields.Char(
        string='Ciudad'
    )
    state = fields.Char(
        string='Estado/Provincia'
    )
    zip_code = fields.Char(
        string='Codigo Postal'
    )
    country_code = fields.Char(
        string='Codigo Pais'
    )

    # Odoo Integration
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente Odoo',
        help='Cliente vinculado en Odoo'
    )

    # Orders
    order_ids = fields.One2many(
        'mercadolibre.order',
        'buyer_id',
        string='Ordenes'
    )
    order_count = fields.Integer(
        string='Cantidad Ordenes',
        compute='_compute_order_count',
        store=True
    )
    total_purchases = fields.Float(
        string='Total Compras',
        compute='_compute_total_purchases',
        store=True,
        digits=(16, 2)
    )

    _sql_constraints = [
        ('ml_buyer_id_uniq', 'unique(ml_buyer_id, account_id)',
         'Este comprador ya existe para esta cuenta.')
    ]

    @api.depends('first_name', 'last_name', 'nickname')
    def _compute_name(self):
        for record in self:
            if record.first_name or record.last_name:
                record.name = f'{record.first_name or ""} {record.last_name or ""}'.strip()
            elif record.nickname:
                record.name = record.nickname
            else:
                record.name = f'Comprador {record.ml_buyer_id}'

    @api.depends('first_name', 'last_name')
    def _compute_full_name(self):
        for record in self:
            parts = [record.first_name, record.last_name]
            record.full_name = ' '.join(filter(None, parts))

    @api.depends('order_ids')
    def _compute_order_count(self):
        for record in self:
            record.order_count = len(record.order_ids)

    @api.depends('order_ids.total_amount')
    def _compute_total_purchases(self):
        for record in self:
            record.total_purchases = sum(record.order_ids.mapped('total_amount'))

    def action_create_partner(self):
        """Crea un partner de Odoo para este comprador"""
        self.ensure_one()

        if self.partner_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
                'view_mode': 'form',
            }

        partner_vals = {
            'name': self.full_name or self.nickname or f'Comprador ML {self.ml_buyer_id}',
            'email': self.email,
            'phone': f'{self.phone_area_code or ""}{self.phone or ""}'.strip() or False,
            'street': f'{self.street or ""} {self.street_number or ""}'.strip() or False,
            'city': self.city,
            'zip': self.zip_code,
            'company_id': self.company_id.id,
            'customer_rank': 1,
            'comment': f'Creado desde MercadoLibre. Buyer ID: {self.ml_buyer_id}\nNickname: {self.nickname}',
        }

        partner = self.env['res.partner'].create(partner_vals)
        self.partner_id = partner.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
        }

    def action_view_orders(self):
        """Ver ordenes del comprador"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Ordenes de {self.name}',
            'res_model': 'mercadolibre.order',
            'view_mode': 'tree,form',
            'domain': [('buyer_id', '=', self.id)],
        }
