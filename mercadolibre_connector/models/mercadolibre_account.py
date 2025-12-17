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
        string='Nombre',
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

    def get_valid_token(self):
        """Obtiene un token válido, refrescándolo si es necesario"""
        self.ensure_one()

        if not self.current_token_id:
            raise ValidationError(_('No hay token disponible para esta cuenta.'))

        token = self.current_token_id

        # Si el token está próximo a expirar (menos de 1 hora), refrescarlo
        if token.is_expiring_soon():
            token._refresh_token()
            token = self.current_token_id

        if not token.is_valid:
            raise ValidationError(_('No se pudo obtener un token válido.'))

        return token.access_token

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
