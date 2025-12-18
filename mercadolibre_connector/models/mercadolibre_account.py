# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MercadolibreAccount(models.Model):
    _name = 'mercadolibre.account'
    _description = 'Cuenta MercadoLibre'
    _inherit = ['mail.thread', 'mail.activity.mixin']

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
        string='Compañía',
        related='config_id.company_id',
        store=True,
        readonly=True
    )
    ml_user_id = fields.Char(
        string='ML User ID',
        required=True,
        readonly=True,
        tracking=True,
        help='ID de usuario de MercadoLibre'
    )
    ml_nickname = fields.Char(
        string='Nickname',
        readonly=True,
        help='Nickname del usuario en MercadoLibre'
    )
    ml_email = fields.Char(
        string='Email ML',
        readonly=True,
        help='Email del usuario en MercadoLibre'
    )
    ml_first_name = fields.Char(
        string='Primer Nombre',
        readonly=True
    )
    ml_last_name = fields.Char(
        string='Apellido',
        readonly=True
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('connected', 'Conectado'),
        ('disconnected', 'Desconectado'),
        ('error', 'Error')
    ], string='Estado', default='draft', required=True, tracking=True)

    token_ids = fields.One2many(
        'mercadolibre.token',
        'account_id',
        string='Tokens'
    )
    current_token_id = fields.Many2one(
        'mercadolibre.token',
        string='Token Actual',
        compute='_compute_current_token',
        help='Token activo más reciente'
    )
    has_valid_token = fields.Boolean(
        string='Token Válido',
        compute='_compute_current_token'
    )
    notes = fields.Text(
        string='Notas'
    )

    _sql_constraints = [
        ('ml_user_id_config_uniq', 'unique(ml_user_id, config_id)',
         'Esta cuenta de MercadoLibre ya está registrada en esta configuración.')
    ]

    @api.depends('ml_nickname', 'ml_user_id')
    def _compute_name(self):
        for record in self:
            if record.ml_nickname:
                record.name = record.ml_nickname
            elif record.ml_user_id:
                record.name = f'ML-{record.ml_user_id}'
            else:
                record.name = 'Nueva Cuenta'

    @api.depends('token_ids', 'token_ids.active', 'token_ids.expires_at')
    def _compute_current_token(self):
        for record in self:
            valid_token = record.token_ids.filtered(
                lambda t: t.active and t.is_valid
            ).sorted(key=lambda t: t.expires_at, reverse=True)

            if valid_token:
                record.current_token_id = valid_token[0]
                record.has_valid_token = True
            else:
                record.current_token_id = False
                record.has_valid_token = False

    def get_valid_token(self, force_refresh=False):
        """
        Obtiene un token válido, refrescándolo si es necesario.

        Args:
            force_refresh: Forzar refresh aunque el token sea válido

        Returns:
            access_token string

        Raises:
            ValidationError si no hay token o no se puede refrescar
        """
        self.ensure_one()

        # Buscar token activo (incluso si expiró, para intentar refresh)
        token = self.token_ids.filtered(lambda t: t.active).sorted(
            key=lambda t: t.expires_at, reverse=True
        )
        token = token[0] if token else None

        if not token:
            raise ValidationError(_(
                'No hay token disponible para la cuenta %s. '
                'Por favor reconecte la cuenta.'
            ) % self.name)

        # Si el token expiró o está próximo a expirar, intentar refrescar
        if force_refresh or not token.is_valid or token.is_expiring_soon():
            try:
                new_token = token._refresh_token()
                if new_token:
                    token = new_token
            except Exception as e:
                # Si falla el refresh, verificar si el token aún es válido
                if not token.is_valid:
                    # Marcar cuenta con error
                    self.write({'state': 'error'})
                    raise ValidationError(_(
                        'El token de la cuenta %s ha expirado y no se pudo refrescar. '
                        'Por favor reconecte la cuenta. Error: %s'
                    ) % (self.name, str(e)))

        if not token.is_valid:
            self.write({'state': 'error'})
            raise ValidationError(_(
                'El token de la cuenta %s no es válido. '
                'Por favor reconecte la cuenta.'
            ) % self.name)

        return token.access_token

    def get_valid_token_with_retry(self, max_retries=2):
        """
        Obtiene token con reintentos automáticos.
        Útil para llamadas desde crons o procesos automáticos.

        Args:
            max_retries: Número máximo de reintentos

        Returns:
            access_token string o False si falla
        """
        self.ensure_one()

        for attempt in range(max_retries + 1):
            try:
                return self.get_valid_token(force_refresh=(attempt > 0))
            except ValidationError as e:
                if attempt < max_retries:
                    # Log del reintento
                    self.env['mercadolibre.log'].sudo().create({
                        'log_type': 'token_refresh',
                        'level': 'warning',
                        'account_id': self.id,
                        'message': f'Reintentando obtener token (intento {attempt + 2}/{max_retries + 1})',
                    })
                    continue
                else:
                    # Log del error final
                    self.env['mercadolibre.log'].sudo().create({
                        'log_type': 'token_refresh',
                        'level': 'error',
                        'account_id': self.id,
                        'message': f'No se pudo obtener token después de {max_retries + 1} intentos: {str(e)}',
                    })
                    return False
        return False

    def action_refresh_token(self):
        """Refresca el token manualmente"""
        self.ensure_one()

        if not self.current_token_id:
            raise ValidationError(_('No hay token disponible para refrescar.'))

        self.current_token_id._refresh_token()

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

    def action_disconnect(self):
        """Desconecta la cuenta"""
        for record in self:
            record.token_ids.write({'active': False})
            record.state = 'disconnected'
            record.message_post(body=_('Cuenta desconectada'))

    def action_reconnect(self):
        """Genera una nueva invitación para reconectar"""
        self.ensure_one()
        invitation = self.env['mercadolibre.invitation'].create({
            'config_id': self.config_id.id,
            'email': self.ml_email or '',
            'notes': f'Reconexión de cuenta {self.name}'
        })
        invitation.action_send()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invitación Enviada'),
                'message': _('Se ha enviado una nueva invitación de autorización.'),
                'type': 'success',
                'sticky': False,
            }
        }
