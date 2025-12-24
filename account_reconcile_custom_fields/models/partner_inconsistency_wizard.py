# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PartnerInconsistencyWizard(models.TransientModel):
    """
    Wizard to launch the partner inconsistency detection with user-defined filters.
    """
    _name = "partner.inconsistency.wizard"
    _description = "Partner Inconsistency Detection Wizard"

    account_ids = fields.Many2many(
        "account.account",
        string="Cuentas Contables",
        required=True,
        help="Seleccione una o más cuentas para analizar. Esto es crucial para evitar mezclar clientes y proveedores.",
    )
    mapping_id = fields.Many2one(
        "reconcile.field.mapping",
        string="Mapeo a Utilizar",
        required=True,
        domain=[("active", "=", True)],
        help="Seleccione la regla de mapeo a utilizar para esta búsqueda.",
    )
    date_from = fields.Date(string="Desde")
    date_to = fields.Date(string="Hasta")
    include_reconciled = fields.Boolean(
        string="Incluir Apuntes Conciliados",
        default=False,
        help="Si se marca, la búsqueda incluirá apuntes que ya han sido conciliados, "
             "lo cual puede ser útil para auditorías pero es significativamente más lento.",
    )

    def action_find_inconsistencies(self):
        """
        Gathers the wizard parameters and calls the main inconsistency detection method.
        """
        self.ensure_one()
        
        # Llama a la función principal en el otro modelo, pasando los filtros.
        action = self.env["partner.inconsistency"].find_inconsistencies(
            account_ids=self.account_ids.ids,
            mapping_id=self.mapping_id.id,
            date_from=self.date_from,
            date_to=self.date_to,
            include_reconciled=self.include_reconciled,
        )
        return action