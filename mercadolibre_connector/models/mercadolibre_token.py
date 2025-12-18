# -*- coding: utf-8 -*-

import requests
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreToken(models.Model):
    _name = 'mercadolibre.token'
    _description = 'Token OAuth MercadoLibre'
    _order = 'create_date desc'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='cascade',
        index=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='account_id.company_id',
        store=True,
        readonly=True
    )
    access_token = fields.Char(
        string='Access Token',
        required=True,
        readonly=True
    )
    refresh_token = fields.Char(
        string='Refresh Token',
        required=True,
        readonly=True
    )
    token_type = fields.Char(
        string='Token Type',
        default='Bearer',
        readonly=True
    )
    expires_in = fields.Integer(
        string='Expira en (segundos)',
        readonly=True,
        help='Tiempo de expiración en segundos'
    )
    expires_at = fields.Datetime(
        string='Expira el',
        required=True,
        readonly=True,
        help='Fecha y hora de expiración del token'
    )
    scope = fields.Char(
        string='Scope',
        readonly=True
    )
    ml_user_id = fields.Char(
        string='ML User ID',
        readonly=True,
        help='ID de usuario de MercadoLibre'
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Solo puede haber un token activo por cuenta'
    )
    is_valid = fields.Boolean(
        string='Válido',
        compute='_compute_is_valid',
        help='El token no ha expirado'
    )
    refresh_count = fields.Integer(
        string='Nro. Refrescos',
        default=0,
        readonly=True,
        help='Cantidad de veces que se ha refrescado este token'
    )
    last_refresh_date = fields.Datetime(
        string='Último Refresco',
        readonly=True
    )

    @api.depends('expires_at')
    def _compute_is_valid(self):
        now = fields.Datetime.now()
        for record in self:
            record.is_valid = record.expires_at > now if record.expires_at else False

    def is_expiring_soon(self, minutes=60):
        """Verifica si el token expirará pronto"""
        self.ensure_one()
        threshold = fields.Datetime.now() + timedelta(minutes=minutes)
        return self.expires_at <= threshold

    @api.model_create_multi
    def create(self, vals_list):
        """Al crear nuevos tokens, desactiva los anteriores de las mismas cuentas"""
        # Obtener todos los account_ids de los registros a crear
        account_ids = [vals['account_id'] for vals in vals_list if 'account_id' in vals]
        if account_ids:
            self.search([
                ('account_id', 'in', account_ids),
                ('active', '=', True)
            ]).write({'active': False})
        return super().create(vals_list)

    def _refresh_token(self):
        """Refresca el token usando el refresh_token"""
        self.ensure_one()

        config = self.account_id.config_id
        url = 'https://api.mercadolibre.com/oauth/token'

        payload = {
            'grant_type': 'refresh_token',
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'refresh_token': self.refresh_token,
        }

        try:
            # Log del intento
            self.env['mercadolibre.log'].create({
                'log_type': 'token_refresh',
                'level': 'info',
                'account_id': self.account_id.id,
                'message': f'Refrescando token para cuenta {self.account_id.name}',
            })

            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Calcula la fecha de expiración
            expires_at = datetime.now() + timedelta(seconds=data['expires_in'])

            # Crea un nuevo token
            new_token = self.create({
                'account_id': self.account_id.id,
                'access_token': data['access_token'],
                'refresh_token': data['refresh_token'],
                'token_type': data.get('token_type', 'Bearer'),
                'expires_in': data['expires_in'],
                'expires_at': expires_at,
                'scope': data.get('scope', ''),
                'ml_user_id': data.get('user_id', self.ml_user_id),
                'refresh_count': self.refresh_count + 1,
                'last_refresh_date': fields.Datetime.now(),
            })

            # Actualiza el estado de la cuenta
            self.account_id.write({'state': 'connected'})

            # Log exitoso
            self.env['mercadolibre.log'].create({
                'log_type': 'token_refresh',
                'level': 'success',
                'account_id': self.account_id.id,
                'message': f'Token refrescado exitosamente (#{new_token.refresh_count})',
            })

            _logger.info(f'Token refrescado para cuenta {self.account_id.name}')

            return new_token

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            _logger.error(f'Error al refrescar token: {error_msg}')

            # Log del error
            self.env['mercadolibre.log'].create({
                'log_type': 'token_refresh',
                'level': 'error',
                'account_id': self.account_id.id,
                'message': f'Error al refrescar token: {error_msg}',
                'error_details': str(e),
            })

            # Actualiza el estado de la cuenta
            self.account_id.write({'state': 'error'})

            raise UserError(_(f'Error al refrescar token: {error_msg}'))

    @api.model
    def cron_refresh_tokens(self):
        """Cron: Refresca todos los tokens que estén próximos a expirar"""
        _logger.info('Ejecutando cron de refresco de tokens')

        tokens = self.search([
            ('active', '=', True),
            ('expires_at', '<=', fields.Datetime.now() + timedelta(minutes=30))
        ])

        _logger.info(f'Encontrados {len(tokens)} tokens para refrescar')

        for token in tokens:
            try:
                token._refresh_token()
            except Exception as e:
                _logger.error(f'Error al refrescar token {token.id}: {str(e)}')
                continue

        _logger.info('Cron de refresco de tokens completado')

    def action_refresh_now(self):
        """Acción manual para refrescar el token"""
        self.ensure_one()
        self._refresh_token()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Token Refrescado'),
                'message': _('El token se ha refrescado correctamente.'),
                'type': 'success',
                'sticky': False,
            }
        }
