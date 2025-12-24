# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PartnerInconsistencyCancelWizard(models.TransientModel):
    _name = "partner.inconsistency.cancel.wizard"
    _description = "Wizard para Cancelar Inconsistencias"

    inconsistency_ids = fields.Many2many(
        "partner.inconsistency",
        string="Inconsistencias a Cancelar"
    )
    notas = fields.Text(
        string="Razón de Cancelación",
        required=True,
        help="Explique por qué esta inconsistencia no se corregirá (ej: 'Se aplicará nota de crédito a la factura')"
    )

    def action_cancel_inconsistencies(self):
        """
        Marcar las inconsistencias seleccionadas como canceladas
        """
        if not self.inconsistency_ids:
            raise UserError(_("No hay inconsistencias seleccionadas para cancelar."))

        # Marcar como canceladas
        self.inconsistency_ids.mark_as_cancelled(notas=self.notas)

        # Mostrar notificación
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Inconsistencias Canceladas'),
                'message': _('%d inconsistencia(s) marcada(s) como canceladas.') % len(self.inconsistency_ids),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
