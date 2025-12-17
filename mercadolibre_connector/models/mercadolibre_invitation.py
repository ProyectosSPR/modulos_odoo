# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import secrets
import logging

_logger = logging.getLogger(__name__)


class MercadoLibreInvitation(models.Model):
    _name = 'mercadolibre.invitation'
    _description = 'Invitación para Conectar Cuenta ML'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sent_at desc, created_at desc'

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
    email = fields.Char(
        string='Email Destinatario',
        required=True,
        tracking=True
    )
    recipient_name = fields.Char(
        string='Nombre Destinatario',
        tracking=True
    )
    invitation_token = fields.Char(
        string='Token de Invitación',
        required=True,
        readonly=True,
        default=lambda self: secrets.token_urlsafe(32),
        copy=False,
        index=True
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('sent', 'Enviada'),
            ('opened', 'Abierta'),
            ('completed', 'Completada'),
            ('expired', 'Expirada'),
            ('cancelled', 'Cancelada'),
        ],
        string='Estado',
        default='draft',
        required=True,
        tracking=True
    )
    authorization_url = fields.Text(
        string='URL de Autorización',
        compute='_compute_authorization_url'
    )
    invitation_url = fields.Text(
        string='URL de Invitación',
        compute='_compute_invitation_url',
        help='URL que se envía por email'
    )

    # Fechas
    expires_at = fields.Datetime(
        string='Expira el',
        default=lambda self: fields.Datetime.now() + timedelta(days=7),
        required=True,
        tracking=True
    )
    sent_at = fields.Datetime(
        string='Enviada el',
        readonly=True,
        tracking=True
    )
    opened_at = fields.Datetime(
        string='Abierta el',
        readonly=True,
        tracking=True
    )
    completed_at = fields.Datetime(
        string='Completada el',
        readonly=True,
        tracking=True
    )

    # Relaciones
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta Creada',
        readonly=True,
        tracking=True
    )
    sent_by = fields.Many2one(
        'res.users',
        string='Enviada por',
        readonly=True,
        default=lambda self: self.env.user
    )
    notes = fields.Text(
        string='Notas Internas'
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
        ('unique_token', 'UNIQUE(invitation_token)',
         'El token de invitación debe ser único')
    ]

    @api.depends('email', 'recipient_name')
    def _compute_name(self):
        for record in self:
            if record.recipient_name:
                record.name = f"{record.recipient_name} <{record.email}>"
            else:
                record.name = record.email

    @api.depends('config_id', 'invitation_token')
    def _compute_authorization_url(self):
        for record in self:
            if record.config_id and record.invitation_token:
                auth_url = record.config_id.auth_url
                record.authorization_url = (
                    f"{auth_url}"
                    f"?response_type=code"
                    f"&client_id={record.config_id.client_id}"
                    f"&redirect_uri={record.config_id.redirect_uri}"
                    f"&state={record.invitation_token}"
                )
            else:
                record.authorization_url = False

    @api.depends('invitation_token')
    def _compute_invitation_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.invitation_token:
                record.invitation_url = f"{base_url}/mercadolibre/invite/{record.invitation_token}"
            else:
                record.invitation_url = False

    def write(self, vals):
        result = super(MercadoLibreInvitation, self).write(vals)
        self.updated_at = fields.Datetime.now()
        return result

    @api.model
    def _cron_expire_invitations(self):
        """Marcar invitaciones expiradas"""
        now = fields.Datetime.now()
        expired = self.search([
            ('state', 'in', ['draft', 'sent', 'opened']),
            ('expires_at', '<', now)
        ])

        for invitation in expired:
            invitation.write({'state': 'expired'})
            invitation.message_post(body=_('Invitación expirada automáticamente'))

        _logger.info(f"Cron expire: {len(expired)} invitaciones marcadas como expiradas")

        return True

    def action_send_invitation(self):
        """Enviar invitación por email"""
        self.ensure_one()

        if self.state not in ['draft', 'sent']:
            raise ValidationError(_('Solo se pueden enviar invitaciones en estado Borrador o Enviada'))

        # Validar que no esté expirada
        if fields.Datetime.now() >= self.expires_at:
            raise ValidationError(_('Esta invitación ya expiró'))

        # Obtener template de email
        template = self.env.ref('mercadolibre_connector.mail_template_invitation', raise_if_not_found=False)
        if not template:
            raise ValidationError(_('No se encontró la plantilla de email'))

        # Enviar email
        try:
            template.send_mail(self.id, force_send=True)

            self.write({
                'state': 'sent',
                'sent_at': fields.Datetime.now(),
            })

            # Log
            self.env['mercadolibre.log'].create({
                'log_type': 'email',
                'level': 'info',
                'operation': 'invitation_sent',
                'message': f'Invitación enviada a {self.email}',
                'company_id': self.company_id.id,
                'user_id': self.env.user.id,
            })

            self.message_post(body=_('Invitación enviada a %s') % self.email)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Invitación Enviada'),
                    'message': _('La invitación fue enviada a %s') % self.email,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f"Error enviando invitación: {str(e)}")
            raise ValidationError(_('Error al enviar invitación: %s') % str(e))

    def action_resend_invitation(self):
        """Reenviar invitación"""
        self.ensure_one()

        if self.state == 'completed':
            raise ValidationError(_('Esta invitación ya fue completada'))

        if self.state == 'expired':
            # Extender fecha de expiración
            self.write({
                'expires_at': fields.Datetime.now() + timedelta(days=7),
                'state': 'draft'
            })

        return self.action_send_invitation()

    def action_cancel_invitation(self):
        """Cancelar invitación"""
        self.ensure_one()

        if self.state == 'completed':
            raise ValidationError(_('No se puede cancelar una invitación completada'))

        self.write({'state': 'cancelled'})
        self.message_post(body=_('Invitación cancelada'))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invitación Cancelada'),
                'message': _('La invitación fue cancelada'),
                'type': 'info',
                'sticky': False,
            }
        }

    def mark_as_opened(self):
        """Marcar como abierta (llamado desde controller)"""
        self.ensure_one()

        if self.state == 'sent' and not self.opened_at:
            self.write({
                'state': 'opened',
                'opened_at': fields.Datetime.now()
            })
            self.message_post(body=_('Invitación abierta por el destinatario'))

    def mark_as_completed(self, account_id):
        """Marcar como completada (llamado desde controller)"""
        self.ensure_one()

        self.write({
            'state': 'completed',
            'completed_at': fields.Datetime.now(),
            'account_id': account_id
        })

        # Enviar email de confirmación
        template = self.env.ref('mercadolibre_connector.mail_template_connected', raise_if_not_found=False)
        if template:
            try:
                template.send_mail(self.id, force_send=True)
            except Exception as e:
                _logger.error(f"Error enviando email de confirmación: {str(e)}")

        self.message_post(body=_('Cuenta conectada exitosamente: %s') % account_id.name)
