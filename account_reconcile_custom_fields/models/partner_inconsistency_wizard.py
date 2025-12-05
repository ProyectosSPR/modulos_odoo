# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class PartnerInconsistencyWizard(models.TransientModel):
    """
    Wizard simple para ejecutar la búsqueda de inconsistencias
    """
    _name = "partner.inconsistency.wizard"
    _description = "Wizard to Search for Partner Inconsistencies"

    def action_find_inconsistencies(self):
        """
        Ejecuta la búsqueda de inconsistencias
        """
        return self.env['partner.inconsistency'].find_inconsistencies()
