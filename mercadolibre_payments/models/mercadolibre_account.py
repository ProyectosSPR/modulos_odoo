# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MercadolibreAccountExtend(models.Model):
    _inherit = 'mercadolibre.account'

    # Usuario de Odoo vinculado a esta cuenta ML
    odoo_user_id = fields.Many2one(
        'res.users',
        string='Usuario Odoo',
        readonly=True,
        help='Usuario de Odoo creado automaticamente para esta cuenta ML'
    )

    auto_create_user = fields.Boolean(
        string='Crear Usuario Automaticamente',
        default=True,
        help='Crear un usuario interno de Odoo cuando la cuenta se conecte'
    )

    def write(self, vals):
        """Override write para crear usuario cuando la cuenta se conecta"""
        result = super().write(vals)

        # Si el estado cambia a 'connected' y no tiene usuario, crear uno
        if vals.get('state') == 'connected':
            for record in self:
                if record.auto_create_user and not record.odoo_user_id:
                    record._create_odoo_user()

        return result

    def _create_odoo_user(self):
        """
        Crea un usuario interno de Odoo basado en la informacion de MercadoLibre.

        El usuario se crea con:
        - Login: ml_<ml_user_id> o email de ML
        - Nombre: nombre completo de ML o nickname
        - Email: email de ML
        - Grupo: Usuario interno basico
        """
        self.ensure_one()

        if self.odoo_user_id:
            _logger.info('Cuenta ML %s ya tiene usuario Odoo: %s',
                        self.name, self.odoo_user_id.login)
            return self.odoo_user_id

        # Verificar que tengamos la info necesaria
        if not self.ml_user_id:
            _logger.warning('No se puede crear usuario: falta ml_user_id')
            return False

        # Preparar datos del usuario
        login = self.ml_email or f'ml_{self.ml_user_id}'

        # Verificar si el login ya existe
        existing_user = self.env['res.users'].sudo().search([
            ('login', '=', login)
        ], limit=1)

        if existing_user:
            _logger.info('Usuario con login %s ya existe, vinculando a cuenta ML', login)
            self.odoo_user_id = existing_user.id
            return existing_user

        # Construir nombre completo
        name_parts = []
        if self.ml_first_name:
            name_parts.append(self.ml_first_name)
        if self.ml_last_name:
            name_parts.append(self.ml_last_name)

        if name_parts:
            name = ' '.join(name_parts)
        elif self.ml_nickname:
            name = self.ml_nickname
        else:
            name = f'MercadoLibre {self.ml_user_id}'

        try:
            # Crear el usuario
            user_vals = {
                'name': name,
                'login': login,
                'email': self.ml_email or '',
                'active': True,
                'company_id': self.company_id.id,
                'company_ids': [(4, self.company_id.id)],
                # Usuario interno basico
                'groups_id': [(4, self.env.ref('base.group_user').id)],
            }

            new_user = self.env['res.users'].sudo().create(user_vals)

            _logger.info('Usuario Odoo creado para cuenta ML %s: %s (%s)',
                        self.name, new_user.name, new_user.login)

            # Vincular usuario a la cuenta
            self.odoo_user_id = new_user.id

            # Notificar
            self.message_post(
                body=_('Usuario Odoo creado automaticamente: %s (%s)') % (new_user.name, new_user.login),
                message_type='notification'
            )

            return new_user

        except Exception as e:
            _logger.error('Error creando usuario Odoo para cuenta ML %s: %s',
                         self.name, str(e))
            self.message_post(
                body=_('Error al crear usuario Odoo: %s') % str(e),
                message_type='notification'
            )
            return False

    def action_create_odoo_user(self):
        """Accion manual para crear el usuario de Odoo"""
        self.ensure_one()

        if self.odoo_user_id:
            raise ValidationError(_('Esta cuenta ya tiene un usuario de Odoo vinculado: %s') % self.odoo_user_id.name)

        user = self._create_odoo_user()

        if user:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Usuario Creado'),
                    'message': _('Se ha creado el usuario: %s') % user.name,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise ValidationError(_('No se pudo crear el usuario. Revise los logs para mas detalles.'))

    def action_view_odoo_user(self):
        """Abre el usuario de Odoo vinculado"""
        self.ensure_one()

        if not self.odoo_user_id:
            raise ValidationError(_('Esta cuenta no tiene un usuario de Odoo vinculado.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Usuario Odoo'),
            'res_model': 'res.users',
            'res_id': self.odoo_user_id.id,
            'view_mode': 'form',
        }
