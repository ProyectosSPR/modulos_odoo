# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountAccountReconcile(models.Model):
    _inherit = "account.account.reconcile"

    # Campo para almacenar el mapeo de campos personalizado seleccionado
    custom_field_mapping_id = fields.Many2one(
        "reconcile.field.mapping",
        string="Custom Field Mapping",
        compute="_compute_custom_filter_fields",
        inverse="_inverse_custom_field_mapping_id",
        domain="[('active', '=', True), ('target_model', '=', 'account.move.line')]",
    )

    # Campos de filtro dinámicos
    custom_filter_value = fields.Char(
        string="Filter Value",
        compute="_compute_custom_filter_fields",
        inverse="_inverse_custom_filter_value",
        help="Enter the value to search for in the source model",
    )

    @api.depends("id")
    def _compute_custom_filter_fields(self):
        """Obtener los valores de filtro desde el modelo de datos"""
        data_obj = self.env["account.account.reconcile.data"]
        for record in self:
            data_record = data_obj.search(
                [("user_id", "=", self.env.user.id), ("reconcile_id", "=", record.id)],
                limit=1,
            )
            if data_record and data_record.custom_filter_data:
                record.custom_field_mapping_id = data_record.custom_filter_data.get(
                    "mapping_id", False
                )
                record.custom_filter_value = data_record.custom_filter_data.get(
                    "filter_value", False
                )
            else:
                record.custom_field_mapping_id = False
                record.custom_filter_value = False

    def _inverse_custom_field_mapping_id(self):
        """Guardar el mapeo seleccionado"""
        data_obj = self.env["account.account.reconcile.data"]
        for record in self:
            data_record = data_obj.search(
                [("user_id", "=", self.env.user.id), ("reconcile_id", "=", record.id)],
                limit=1,
            )
            if not data_record:
                data_record = data_obj.create(
                    {
                        "reconcile_id": record.id,
                        "user_id": self.env.user.id,
                        "data": {"data": [], "counterparts": []},
                        "custom_filter_data": {},
                    }
                )

            custom_data = data_record.custom_filter_data or {}
            custom_data["mapping_id"] = (
                record.custom_field_mapping_id.id
                if record.custom_field_mapping_id
                else False
            )
            data_record.custom_filter_data = custom_data

    def _inverse_custom_filter_value(self):
        """Guardar el valor del filtro"""
        data_obj = self.env["account.account.reconcile.data"]
        for record in self:
            data_record = data_obj.search(
                [("user_id", "=", self.env.user.id), ("reconcile_id", "=", record.id)],
                limit=1,
            )
            if not data_record:
                data_record = data_obj.create(
                    {
                        "reconcile_id": record.id,
                        "user_id": self.env.user.id,
                        "data": {"data": [], "counterparts": []},
                        "custom_filter_data": {},
                    }
                )

            custom_data = data_record.custom_filter_data or {}
            custom_data["filter_value"] = record.custom_filter_value or False
            data_record.custom_filter_data = custom_data

    def _compute_reconcile_data_info(self):
        """
        Extender para agregar sugerencias basadas en mapeos personalizados
        """
        # Primero ejecutar el método original
        super()._compute_reconcile_data_info()

        # Si hay un mapeo y valor de filtro, buscar coincidencias
        for record in self:
            if record.custom_field_mapping_id and record.custom_filter_value:
                matching_lines = record._find_matching_lines_from_custom_filter()
                if matching_lines:
                    # Agregar las líneas encontradas
                    for line in matching_lines:
                        record._add_account_move_line(line, keep_current=True)

    def _find_matching_lines_from_custom_filter(self):
        """
        Buscar líneas de facturas que coincidan usando el mapeo personalizado
        """
        self.ensure_one()

        if not self.custom_field_mapping_id or not self.custom_filter_value:
            return self.env["account.move.line"].browse()

        mapping = self.custom_field_mapping_id

        # Buscar en el modelo origen usando el valor del filtro
        source_records = mapping._get_source_records(self.custom_filter_value)

        if not source_records:
            return self.env["account.move.line"].browse()

        # Obtener facturas relacionadas
        invoices = mapping._get_invoices_from_source(source_records)

        if not invoices:
            return self.env["account.move.line"].browse()

        # Obtener líneas por cobrar/pagar
        matching_lines = mapping._get_receivable_payable_lines(invoices)

        # Filtrar por cuenta y partner si aplica
        if self.account_id:
            matching_lines = matching_lines.filtered(
                lambda l: l.account_id == self.account_id
            )

        if self.partner_id:
            matching_lines = matching_lines.filtered(
                lambda l: l.partner_id == self.partner_id
            )

        return matching_lines

    def button_apply_custom_filter(self):
        """
        Botón para aplicar el filtro personalizado
        """
        self.ensure_one()

        if not self.custom_field_mapping_id or not self.custom_filter_value:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Missing Information",
                    "message": "Please select a custom field mapping and enter a filter value.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        matching_lines = self._find_matching_lines_from_custom_filter()

        if not matching_lines:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Matches Found",
                    "message": f"No matching invoice lines found for '{self.custom_filter_value}'.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Agregar todas las líneas encontradas
        for line in matching_lines:
            self._add_account_move_line(line, keep_current=True)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Matches Found",
                "message": f"Found {len(matching_lines)} matching line(s) and added to reconciliation.",
                "type": "success",
                "sticky": False,
            },
        }

    def button_clear_custom_filter(self):
        """
        Limpiar el filtro personalizado
        """
        self.ensure_one()
        self.custom_field_mapping_id = False
        self.custom_filter_value = False
        self.clean_reconcile()


class AccountAccountReconcileData(models.TransientModel):
    _inherit = "account.account.reconcile.data"

    custom_filter_data = fields.Serialized(
        string="Custom Filter Data",
        help="Store custom field mapping and filter value",
    )


class AccountAccountReconcileCustom(models.Model):
    """
    Modelo específico para conciliación con filtros personalizados
    Hereda de account.account.reconcile pero con vistas personalizadas
    """

    _name = "account.account.reconcile.custom"
    _description = "Account Reconcile with Custom Field Filters"
    _inherit = "account.account.reconcile"
    _auto = False
    _table = "account_account_reconcile"  # Usa la misma tabla/vista SQL

    # Sobrescribir para agregar filtros adicionales en la vista kanban
    def _where(self):
        """
        Extender WHERE para filtrar por mapeos personalizados si están configurados
        """
        where_clause = super()._where()

        # Si hay un contexto con filtro personalizado, agregarlo
        if self.env.context.get("custom_mapping_filter"):
            # Este filtro se aplicará cuando se use desde la vista personalizada
            pass

        return where_clause
