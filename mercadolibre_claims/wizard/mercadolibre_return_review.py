# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MercadolibreReturnReviewWizard(models.TransientModel):
    _name = 'mercadolibre.return.review.wizard'
    _description = 'Wizard Revision de Devolucion'

    return_id = fields.Many2one(
        'mercadolibre.return',
        string='Devolucion',
        required=True
    )

    review_status = fields.Selection([
        ('ok', 'OK - Buen Estado'),
        ('damaged', 'Danado'),
        ('incomplete', 'Incompleto'),
        ('different', 'Producto Diferente'),
        ('not_received', 'No Llego'),
    ], string='Estado del Producto', required=True, default='ok')

    notes = fields.Text(string='Notas de Revision')

    move_to_scrap = fields.Boolean(
        string='Mover a Merma/Scrap',
        default=False,
        help='Si esta marcado, el producto sera movido a la ubicacion de scrap'
    )

    @api.onchange('review_status')
    def _onchange_review_status(self):
        if self.review_status == 'damaged':
            self.move_to_scrap = True
        else:
            self.move_to_scrap = False

    def action_confirm(self):
        """Confirma la revision"""
        self.ensure_one()

        if not self.return_id:
            raise UserError(_('No hay devolucion seleccionada'))

        # Marcar como revisado
        self.return_id.action_mark_reviewed(
            review_status=self.review_status,
            notes=self.notes
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Revision completada correctamente'),
                'type': 'success',
                'sticky': False,
            }
        }
