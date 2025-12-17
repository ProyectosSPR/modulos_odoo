# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MercadoLibreConfig(models.Model):
    _name = 'mercadolibre.config'
    _description = 'Configuración de Aplicación Mercado Libre'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'company_id, site_id'

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
        help='Nombre descriptivo de esta configuración'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    client_id = fields.Char(
        string='Client ID',
        required=True,
        tracking=True,
        help='App ID de Mercado Libre'
    )
    client_secret = fields.Char(
        string='Client Secret',
        required=True,
        tracking=True,
        help='Secret de la aplicación'
    )
    redirect_uri = fields.Char(
        string='Redirect URI',
        required=True,
        tracking=True,
        help='URL de callback configurada en ML (ej: https://tudominio.com/mercadolibre/callback)'
    )
    country_id = fields.Many2one(
        'res.country',
        string='País',
        tracking=True,
        help='País de Mercado Libre'
    )
    site_id = fields.Selection(
        selection=[
            ('MLA', 'Argentina'),
            ('MLB', 'Brasil'),
            ('MCO', 'Colombia'),
            ('MCR', 'Costa Rica'),
            ('MEC', 'Ecuador'),
            ('MLC', 'Chile'),
            ('MLM', 'México'),
            ('MLU', 'Uruguay'),
            ('MLV', 'Venezuela'),
            ('MPA', 'Panamá'),
            ('MPE', 'Perú'),
            ('MPT', 'Portugal'),
            ('MRD', 'República Dominicana'),
        ],
        string='Sitio ML',
        required=True,
        default='MLM',
        tracking=True,
        help='Sitio de Mercado Libre'
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True
    )

    # Relaciones
    account_ids = fields.One2many(
        'mercadolibre.account',
        'config_id',
        string='Cuentas Conectadas'
    )
    account_count = fields.Integer(
        string='Total Cuentas',
        compute='_compute_account_count'
    )
    invitation_ids = fields.One2many(
        'mercadolibre.invitation',
        'config_id',
        string='Invitaciones'
    )

    # URLs
    auth_url = fields.Char(
        string='URL de Autorización',
        compute='_compute_auth_url',
        help='URL base para autorización OAuth'
    )

    # Timestamps
    created_at = fields.Datetime(
        string='Creado el',
        default=fields.Datetime.now,
        readonly=True
    )
    updated_at = fields.Datetime(
        string='Actualizado el',
        default=fields.Datetime.now,
        readonly=True
    )

    _sql_constraints = [
        ('unique_company_site', 'UNIQUE(company_id, site_id)',
         'Ya existe una configuración para esta empresa y sitio de ML')
    ]

    @api.depends('account_ids')
    def _compute_account_count(self):
        for record in self:
            record.account_count = len(record.account_ids)

    @api.depends('site_id')
    def _compute_auth_url(self):
        auth_urls = {
            'MLA': 'https://auth.mercadolibre.com.ar/authorization',
            'MLB': 'https://auth.mercadolibre.com.br/authorization',
            'MCO': 'https://auth.mercadolibre.com.co/authorization',
            'MCR': 'https://auth.mercadolibre.com.cr/authorization',
            'MEC': 'https://auth.mercadolibre.com.ec/authorization',
            'MLC': 'https://auth.mercadolibre.cl/authorization',
            'MLM': 'https://auth.mercadolibre.com.mx/authorization',
            'MLU': 'https://auth.mercadolibre.com.uy/authorization',
            'MLV': 'https://auth.mercadolibre.com.ve/authorization',
            'MPA': 'https://auth.mercadolibre.com.pa/authorization',
            'MPE': 'https://auth.mercadolibre.com.pe/authorization',
            'MPT': 'https://auth.mercadolibre.pt/authorization',
            'MRD': 'https://auth.mercadolibre.com.do/authorization',
        }
        for record in self:
            record.auth_url = auth_urls.get(record.site_id, '')

    @api.model
    def create(self, vals):
        result = super(MercadoLibreConfig, self).create(vals)
        result.updated_at = fields.Datetime.now()

        # Log de creación
        self.env['mercadolibre.log'].create({
            'log_type': 'system',
            'level': 'info',
            'operation': 'config_created',
            'message': f'Configuración creada: {result.name} ({result.site_id})',
            'company_id': result.company_id.id,
            'user_id': self.env.user.id,
        })

        return result

    def write(self, vals):
        result = super(MercadoLibreConfig, self).write(vals)
        self.updated_at = fields.Datetime.now()
        return result

    @api.constrains('redirect_uri')
    def _check_redirect_uri(self):
        for record in self:
            if record.redirect_uri:
                if not record.redirect_uri.startswith(('http://', 'https://')):
                    raise ValidationError(_('La URL de redirección debe comenzar con http:// o https://'))

    def action_view_accounts(self):
        """Acción para ver las cuentas conectadas"""
        self.ensure_one()
        return {
            'name': _('Cuentas de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.account',
            'view_mode': 'kanban,tree,form',
            'domain': [('config_id', '=', self.id)],
            'context': {'default_config_id': self.id},
        }

    def action_test_connection(self):
        """Probar conexión con ML"""
        self.ensure_one()
        # TODO: Implementar test de conexión
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Prueba de Conexión'),
                'message': _('Funcionalidad en desarrollo'),
                'type': 'info',
                'sticky': False,
            }
        }
