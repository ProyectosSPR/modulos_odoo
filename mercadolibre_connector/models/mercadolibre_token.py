# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class MercadoLibreToken(models.Model):
    _name = 'mercadolibre.token'
    _description = 'Token OAuth de Mercado Libre'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'created_at desc'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        related='account_id.company_id',
        store=True,
        readonly=True
    )
    access_token = fields.Text(
        string='Access Token',
        required=True,
        groups='mercadolibre_connector.group_mercadolibre_manager'
    )
    token_type = fields.Char(
        string='Tipo de Token',
        default='Bearer',
        readonly=True
    )
    refresh_token = fields.Text(
        string='Refresh Token',
        required=True,
        groups='mercadolibre_connector.group_mercadolibre_manager'
    )
    scope = fields.Char(
        string='Alcance',
        readonly=True,
        help='offline_access read write'
    )
    expires_in = fields.Integer(
        string='Expira en (segundos)',
        required=True,
        default=21600,
        help='Tiempo de validez en segundos (default: 21600 = 6 horas)'
    )
    expires_at = fields.Datetime(
        string='Expira el',
        compute='_compute_expires_at',
        store=True,
        tracking=True,
        help='Fecha y hora exacta de expiración'
    )
    is_expired = fields.Boolean(
        string='Expirado',
        compute='_compute_is_expired',
        store=False
    )
    minutes_to_expire = fields.Integer(
        string='Minutos para Expirar',
        compute='_compute_minutes_to_expire',
        store=False
    )

    # Configuración de refresh
    auto_refresh = fields.Boolean(
        string='Refresh Automático',
        default=True,
        tracking=True,
        help='Si está activo, el cron refrescará automáticamente el token'
    )
    refresh_before_minutes = fields.Integer(
        string='Refrescar Antes de (minutos)',
        default=30,
        help='Minutos antes de expirar para ejecutar el refresh automático'
    )
    next_refresh_at = fields.Datetime(
        string='Próximo Refresh',
        compute='_compute_next_refresh_at',
        store=True
    )

    # Control de errores
    last_refresh = fields.Datetime(
        string='Último Refresh',
        readonly=True,
        tracking=True
    )
    refresh_count = fields.Integer(
        string='Contador de Refreshes',
        default=0,
        readonly=True
    )
    last_error = fields.Text(
        string='Último Error',
        readonly=True
    )
    consecutive_errors = fields.Integer(
        string='Errores Consecutivos',
        default=0,
        readonly=True
    )

    # Health status
    health_status = fields.Selection(
        selection=[
            ('healthy', 'Saludable'),
            ('warning', 'Advertencia'),
            ('critical', 'Crítico'),
            ('disabled', 'Deshabilitado'),
        ],
        string='Estado de Salud',
        compute='_compute_health_status',
        store=True
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
        ('unique_account', 'UNIQUE(account_id)',
         'Una cuenta solo puede tener un token activo')
    ]

    @api.depends('created_at', 'expires_in')
    def _compute_expires_at(self):
        for record in self:
            if record.created_at and record.expires_in:
                record.expires_at = record.created_at + timedelta(seconds=record.expires_in)
            else:
                record.expires_at = False

    @api.depends('expires_at')
    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for record in self:
            if record.expires_at:
                record.is_expired = now >= record.expires_at
            else:
                record.is_expired = True

    @api.depends('expires_at')
    def _compute_minutes_to_expire(self):
        now = fields.Datetime.now()
        for record in self:
            if record.expires_at and not record.is_expired:
                delta = record.expires_at - now
                record.minutes_to_expire = int(delta.total_seconds() / 60)
            else:
                record.minutes_to_expire = 0

    @api.depends('expires_at', 'refresh_before_minutes')
    def _compute_next_refresh_at(self):
        for record in self:
            if record.expires_at and record.refresh_before_minutes:
                record.next_refresh_at = record.expires_at - timedelta(minutes=record.refresh_before_minutes)
            else:
                record.next_refresh_at = False

    @api.depends('is_expired', 'consecutive_errors', 'auto_refresh', 'minutes_to_expire')
    def _compute_health_status(self):
        for record in self:
            if not record.auto_refresh:
                record.health_status = 'disabled'
            elif record.is_expired:
                record.health_status = 'critical'
            elif record.consecutive_errors >= 3:
                record.health_status = 'critical'
            elif record.minutes_to_expire < 30 or record.consecutive_errors > 0:
                record.health_status = 'warning'
            else:
                record.health_status = 'healthy'

    @api.model
    def create(self, vals):
        result = super(MercadoLibreToken, self).create(vals)
        result.updated_at = fields.Datetime.now()

        # Log
        self.env['mercadolibre.log'].create({
            'account_id': result.account_id.id,
            'log_type': 'auth',
            'level': 'info',
            'operation': 'token_created',
            'message': f'Token creado para cuenta {result.account_id.nickname}',
            'company_id': result.company_id.id,
            'user_id': self.env.user.id,
        })

        return result

    def write(self, vals):
        result = super(MercadoLibreToken, self).write(vals)
        self.updated_at = fields.Datetime.now()
        return result

    def _refresh_token(self):
        """Refrescar el token usando refresh_token"""
        self.ensure_one()

        config = self.account_id.config_id
        if not config:
            raise ValidationError(_('La cuenta no tiene configuración asociada'))

        url = 'https://api.mercadolibre.com/oauth/token'
        payload = {
            'grant_type': 'refresh_token',
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'refresh_token': self.refresh_token,
        }

        # Log request
        log_vals = {
            'account_id': self.account_id.id,
            'log_type': 'token_refresh',
            'operation': 'refresh_token',
            'endpoint': url,
            'http_method': 'post',
            'request_body': json.dumps({k: v for k, v in payload.items() if k != 'client_secret'}),
            'company_id': self.company_id.id,
            'user_id': self.env.user.id,
        }

        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Actualizar token
            self.write({
                'access_token': data['access_token'],
                'token_type': data.get('token_type', 'Bearer'),
                'refresh_token': data['refresh_token'],
                'scope': data.get('scope'),
                'expires_in': data.get('expires_in', 21600),
                'created_at': fields.Datetime.now(),  # Reset created_at para recalcular expires_at
                'last_refresh': fields.Datetime.now(),
                'refresh_count': self.refresh_count + 1,
                'consecutive_errors': 0,
                'last_error': False,
            })

            # Log success
            log_vals.update({
                'level': 'info',
                'message': f'Token refrescado correctamente. Refresh #{self.refresh_count}',
                'status_code': response.status_code,
                'response_body': json.dumps(data),
            })
            self.env['mercadolibre.log'].create(log_vals)

            # Mensaje en chatter
            self.account_id.message_post(
                body=_('Token refrescado correctamente. Expira en %s minutos.') % self.minutes_to_expire
            )

            _logger.info(f"Token refrescado para cuenta {self.account_id.nickname} (ID: {self.account_id.id})")

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            try:
                error_data = e.response.json() if hasattr(e, 'response') and e.response else {}
                error_msg = error_data.get('message', error_msg)
            except:
                pass

            # Incrementar errores
            self.write({
                'consecutive_errors': self.consecutive_errors + 1,
                'last_error': error_msg,
            })

            # Log error
            log_vals.update({
                'level': 'error',
                'log_type': 'error',
                'message': f'Error al refrescar token: {error_msg}',
                'error_message': error_msg,
                'status_code': e.response.status_code if hasattr(e, 'response') else 0,
            })
            self.env['mercadolibre.log'].create(log_vals)

            _logger.error(f"Error refrescando token para cuenta {self.account_id.nickname}: {error_msg}")

            raise ValidationError(_('Error al refrescar token: %s') % error_msg)

    @api.model
    def _cron_refresh_tokens(self):
        """Cron job para refrescar tokens automáticamente"""
        now = fields.Datetime.now()

        # Buscar tokens que necesitan refresh
        tokens = self.search([
            ('auto_refresh', '=', True),
            ('next_refresh_at', '<=', now),
            ('consecutive_errors', '<', 5),
            ('account_id.active', '=', True),
        ])

        _logger.info(f"Cron refresh: Encontrados {len(tokens)} tokens para refrescar")

        success_count = 0
        error_count = 0

        for token in tokens:
            try:
                token._refresh_token()
                success_count += 1
            except Exception as e:
                error_count += 1
                _logger.error(f"Error en cron refresh para token {token.id}: {str(e)}")

        # Log del cron
        self.env['mercadolibre.log'].create({
            'log_type': 'cron',
            'level': 'info',
            'operation': 'cron_refresh_tokens',
            'message': f'Cron ejecutado: {success_count} éxitos, {error_count} errores',
            'user_id': self.env.uid,
        })

        _logger.info(f"Cron refresh completado: {success_count} éxitos, {error_count} errores")

        return True
