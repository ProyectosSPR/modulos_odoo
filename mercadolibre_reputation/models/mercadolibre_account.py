# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MercadolibreAccountReputation(models.Model):
    """
    Extiende mercadolibre.account para agregar relación con reputación
    y smart buttons.
    """
    _inherit = 'mercadolibre.account'

    # === RELACION CON REPUTACION ===
    reputation_id = fields.Many2one(
        'mercadolibre.seller.reputation',
        string='Reputación',
        compute='_compute_reputation_id',
        store=True
    )
    reputation_level = fields.Selection(
        related='reputation_id.level_id',
        string='Nivel Reputación',
        readonly=True
    )
    reputation_color = fields.Char(
        related='reputation_id.level_color',
        string='Color Reputación',
        readonly=True
    )
    reputation_status = fields.Selection(
        related='reputation_id.overall_status',
        string='Estado Reputación',
        readonly=True
    )

    # Contadores para smart buttons
    items_experience_count = fields.Integer(
        string='Ítems con Experiencia',
        compute='_compute_experience_counts'
    )
    items_bad_experience_count = fields.Integer(
        string='Ítems con Mala Experiencia',
        compute='_compute_experience_counts'
    )

    @api.depends('ml_user_id')
    def _compute_reputation_id(self):
        for record in self:
            reputation = self.env['mercadolibre.seller.reputation'].search([
                ('account_id', '=', record.id)
            ], limit=1)
            record.reputation_id = reputation.id if reputation else False

    def _compute_experience_counts(self):
        ExperienceModel = self.env['mercadolibre.item.experience']
        for record in self:
            experiences = ExperienceModel.search([('account_id', '=', record.id)])
            record.items_experience_count = len(experiences)
            record.items_bad_experience_count = len(experiences.filtered(
                lambda x: x.color in ('red', 'orange')
            ))

    def action_view_reputation(self):
        """Abre la vista de reputación de la cuenta"""
        self.ensure_one()

        # Obtener o crear reputación
        reputation = self.env['mercadolibre.seller.reputation'].get_or_create_for_account(self)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Reputación'),
            'res_model': 'mercadolibre.seller.reputation',
            'res_id': reputation.id,
            'view_mode': 'form',
        }

    def action_view_item_experiences(self):
        """Ver experiencia de todos los ítems"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Experiencia de Compra'),
            'res_model': 'mercadolibre.item.experience',
            'view_mode': 'tree,kanban,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }

    def action_sync_reputation(self):
        """Sincroniza la reputación de la cuenta"""
        self.ensure_one()

        reputation = self.env['mercadolibre.seller.reputation'].get_or_create_for_account(self)
        reputation._sync_from_api()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Reputación sincronizada correctamente'),
                'type': 'success',
                'sticky': False,
            }
        }
