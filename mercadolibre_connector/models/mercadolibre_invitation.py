# -*- coding: utf-8 -*-

import uuid
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MercadolibreInvitation(models.Model):
    _name = 'mercadolibre.invitation'
    _description = 'Invitación MercadoLibre'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        default=lambda self: _('Nueva Invitación'),
        tracking=True
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
    email = fields.Char(
        string='Email',
        required=True,
        tracking=True,
        help='Email del destinatario de la invitación'
    )
    token = fields.Char(
        string='Token',
        default=lambda self: str(uuid.uuid4()),
        required=True,
        readonly=True,
        copy=False,
        help='Token único para identificar esta invitación'
    )
    authorization_url = fields.Char(
        string='URL de Autorización',
        compute='_compute_authorization_url',
        help='URL para autorizar la cuenta de MercadoLibre'
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviada'),
        ('accepted', 'Aceptada'),
        ('expired', 'Expirada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='draft', required=True, tracking=True)

    sent_date = fields.Datetime(
        string='Fecha de Envío',
        readonly=True
    )
    accepted_date = fields.Datetime(
        string='Fecha de Aceptación',
        readonly=True
    )
    expiry_date = fields.Datetime(
        string='Fecha de Expiración',
        compute='_compute_expiry_date',
        store=True,
        help='Las invitaciones expiran 7 días después del envío'
    )
    is_expired = fields.Boolean(
        string='Expirada',
        compute='_compute_is_expired'
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta Creada',
        readonly=True,
        help='Cuenta de MercadoLibre creada a partir de esta invitación'
    )
    notes = fields.Text(
        string='Notas'
    )

    _sql_constraints = [
        ('token_uniq', 'unique(token)',
         'El token de invitación debe ser único.')
    ]

    @api.depends('config_id', 'token')
    def _compute_authorization_url(self):
        for record in self:
            if record.config_id and record.token:
                base_url = record.config_id.get_authorization_url()
                record.authorization_url = f"{base_url}&state={record.token}"
            else:
                record.authorization_url = False

    @api.depends('sent_date')
    def _compute_expiry_date(self):
        for record in self:
            if record.sent_date:
                record.expiry_date = record.sent_date + timedelta(days=7)
            else:
                record.expiry_date = False

    @api.depends('expiry_date', 'state')
    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for record in self:
            if record.state in ['accepted', 'cancelled']:
                record.is_expired = False
            elif record.expiry_date:
                record.is_expired = record.expiry_date < now
            else:
                record.is_expired = False

    def action_send(self):
        """Envía la invitación por correo"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_('Solo se pueden enviar invitaciones en estado borrador.'))

            # Obtiene la plantilla de correo
            template = self.env.ref('mercadolibre_connector.mail_template_mercadolibre_invitation', raise_if_not_found=False)

            if template:
                template.send_mail(record.id, force_send=True)

            record.write({
                'state': 'sent',
                'sent_date': fields.Datetime.now()
            })

            record.message_post(body=_('Invitación enviada a %s') % record.email)

        return True

    def action_cancel(self):
        """Cancela la invitación"""
        for record in self:
            if record.state == 'accepted':
                raise ValidationError(_('No se puede cancelar una invitación aceptada.'))

            record.state = 'cancelled'
            record.message_post(body=_('Invitación cancelada'))

    def action_resend(self):
        """Reenvía la invitación"""
        for record in self:
            if record.state != 'sent':
                raise ValidationError(_('Solo se pueden reenviar invitaciones enviadas.'))

            # Regenera el token
            record.token = str(uuid.uuid4())

            # Envía de nuevo
            record.action_send()

        return True

    @api.model
    def cron_expire_invitations(self):
        """Cron: Marca como expiradas las invitaciones vencidas"""
        now = fields.Datetime.now()
        expired = self.search([
            ('state', '=', 'sent'),
            ('expiry_date', '<', now)
        ])

        if expired:
            expired.write({'state': 'expired'})
            _logger = logging.getLogger(__name__)
            _logger.info(f'Marcadas {len(expired)} invitaciones como expiradas')

    def mark_as_accepted(self, account_id):
        """Marca la invitación como aceptada"""
        self.ensure_one()
        self.write({
            'state': 'accepted',
            'accepted_date': fields.Datetime.now(),
            'account_id': account_id,
        })
        self.message_post(body=_('Invitación aceptada'))
