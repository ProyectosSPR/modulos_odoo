# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MercadolibreConfig(models.Model):
    _name = 'mercadolibre.config'
    _description = 'Configuración MercadoLibre'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
        help='Nombre descriptivo para esta configuración'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    client_id = fields.Char(
        string='Client ID',
        required=True,
        tracking=True,
        help='App ID de MercadoLibre'
    )
    client_secret = fields.Char(
        string='Client Secret',
        required=True,
        tracking=True,
        help='Secret Key de MercadoLibre'
    )
    redirect_uri = fields.Char(
        string='Redirect URI',
        required=True,
        default=lambda self: self._default_redirect_uri(),
        help='URL de redirección para OAuth'
    )
    country_id = fields.Many2one(
        'res.country',
        string='País',
        required=True,
        default=lambda self: self.env.ref('base.mx'),
        help='País de MercadoLibre (México, Argentina, etc.)'
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True
    )
    account_ids = fields.One2many(
        'mercadolibre.account',
        'config_id',
        string='Cuentas ML',
        help='Cuentas de MercadoLibre asociadas'
    )
    account_count = fields.Integer(
        string='Nro. Cuentas',
        compute='_compute_account_count'
    )

    _sql_constraints = [
        ('client_id_company_uniq', 'unique(client_id, company_id)',
         'Ya existe una configuración con este Client ID para esta compañía.')
    ]

    def _default_redirect_uri(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/mercadolibre/callback"

    @api.depends('account_ids')
    def _compute_account_count(self):
        for record in self:
            record.account_count = len(record.account_ids)

    @api.constrains('client_id', 'client_secret')
    def _check_credentials(self):
        for record in self:
            if not record.client_id or not record.client_secret:
                raise ValidationError(_('Client ID y Client Secret son requeridos.'))

    def get_authorization_url(self):
        """Genera la URL de autorización de MercadoLibre"""
        self.ensure_one()
        country_code = self.country_id.code.lower() if self.country_id else 'mx'
        base_url = f"https://auth.mercadolibre.com.{country_code}/authorization"

        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
        }

        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}?{query_string}"

    def action_view_accounts(self):
        """Acción para ver las cuentas asociadas"""
        self.ensure_one()
        return {
            'name': _('Cuentas MercadoLibre'),
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.account',
            'view_mode': 'tree,form',
            'domain': [('config_id', '=', self.id)],
            'context': {'default_config_id': self.id}
        }
