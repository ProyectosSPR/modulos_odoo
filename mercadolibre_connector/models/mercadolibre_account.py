# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MercadoLibreAccount(models.Model):
    _name = 'mercadolibre.account'
    _description = 'Cuenta de Mercado Libre'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'company_id, nickname'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    config_id = fields.Many2one(
        'mercadolibre.config',
        string='Configuración',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        related='config_id.company_id',
        store=True,
        readonly=True
    )
    ml_user_id = fields.Char(
        string='ID Usuario ML',
        required=True,
        readonly=True,
        tracking=True,
        help='ID de usuario en Mercado Libre'
    )
    nickname = fields.Char(
        string='Nickname',
        readonly=True,
        tracking=True
    )
    email = fields.Char(
        string='Email',
        readonly=True
    )
    site_id = fields.Char(
        string='Sitio',
        readonly=True,
        help='MLM, MLA, MLB, etc'
    )
    account_type = fields.Selection(
        selection=[
            ('personal', 'Personal'),
            ('official_store', 'Tienda Oficial'),
            ('brand', 'Marca'),
        ],
        string='Tipo de Cuenta',
        readonly=True
    )
    points = fields.Integer(
        string='Puntos de Reputación',
        readonly=True
    )
    status = fields.Selection(
        selection=[
            ('active', 'Activa'),
            ('inactive', 'Inactiva'),
        ],
        string='Estado en ML',
        default='active',
        readonly=True
    )
    permalink = fields.Char(
        string='Link a Perfil',
        readonly=True
    )
    thumbnail = fields.Char(
        string='Logo URL',
        readonly=True
    )
    is_authorized = fields.Boolean(
        string='Autorizada',
        compute='_compute_is_authorized',
        store=True,
        tracking=True
    )
    authorization_date = fields.Datetime(
        string='Fecha de Autorización',
        readonly=True,
        tracking=True
    )
    last_sync = fields.Datetime(
        string='Última Sincronización',
        readonly=True
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True
    )

    # Relaciones
    token_id = fields.One2many(
        'mercadolibre.token',
        'account_id',
        string='Token',
        limit=1
    )
    token_health = fields.Selection(
        related='token_id.health_status',
        string='Estado del Token',
        store=False
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
        ('unique_company_user', 'UNIQUE(company_id, ml_user_id)',
         'Esta cuenta de ML ya está conectada a esta empresa')
    ]

    @api.depends('nickname', 'ml_user_id')
    def _compute_name(self):
        for record in self:
            if record.nickname:
                record.name = f"{record.nickname} ({record.ml_user_id})"
            else:
                record.name = record.ml_user_id or 'Nueva Cuenta'

    @api.depends('token_id', 'token_id.is_expired')
    def _compute_is_authorized(self):
        for record in self:
            if record.token_id:
                token = record.token_id[0] if isinstance(record.token_id, list) else record.token_id
                record.is_authorized = not token.is_expired
            else:
                record.is_authorized = False

    def write(self, vals):
        result = super(MercadoLibreAccount, self).write(vals)
        self.updated_at = fields.Datetime.now()
        return result

    def action_authorize(self):
        """Iniciar proceso de autorización OAuth"""
        self.ensure_one()

        if not self.config_id:
            raise ValidationError(_('Debe seleccionar una configuración antes de autorizar'))

        # Generar URL de autorización
        import secrets
        state_token = secrets.token_urlsafe(32)

        # Guardar state en sesión (temporal)
        self.env.cr.execute("""
            INSERT INTO ir_config_parameter (key, value, create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, NOW(), %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = NOW()
        """, (f'ml_state_{state_token}', str(self.id), self.env.uid, self.env.uid))

        auth_url = (
            f"{self.config_id.auth_url}"
            f"?response_type=code"
            f"&client_id={self.config_id.client_id}"
            f"&redirect_uri={self.config_id.redirect_uri}"
            f"&state={state_token}"
        )

        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'self',
        }

    def action_refresh_token(self):
        """Refrescar token manualmente"""
        self.ensure_one()

        if not self.token_id:
            raise ValidationError(_('Esta cuenta no tiene un token configurado'))

        try:
            token = self.token_id[0] if isinstance(self.token_id, list) else self.token_id
            token._refresh_token()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Token Refrescado'),
                    'message': _('El token se refrescó correctamente'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f"Error refrescando token: {str(e)}")
            raise ValidationError(_('Error al refrescar token: %s') % str(e))

    def action_sync_user_info(self):
        """Sincronizar información del usuario desde ML"""
        self.ensure_one()

        http = self.env['mercadolibre.http']
        result = http._request(
            account_id=self.id,
            endpoint='/users/me',
            method='GET'
        )

        if result['success']:
            user_data = result['data']
            self.write({
                'nickname': user_data.get('nickname'),
                'email': user_data.get('email'),
                'site_id': user_data.get('site_id'),
                'points': user_data.get('points', 0),
                'permalink': user_data.get('permalink'),
                'thumbnail': user_data.get('thumbnail', {}).get('picture_url') if isinstance(user_data.get('thumbnail'), dict) else user_data.get('thumbnail'),
                'last_sync': fields.Datetime.now(),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronizado'),
                    'message': _('Información actualizada desde Mercado Libre'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise ValidationError(_('Error al sincronizar: %s') % result['error'])

    def action_view_logs(self):
        """Ver logs de esta cuenta"""
        self.ensure_one()
        return {
            'name': _('Logs de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.log',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }
