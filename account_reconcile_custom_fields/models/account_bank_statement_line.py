# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    # Campo para filtrar mapeos disponibles
    available_field_mappings_count = fields.Integer(
        string="Available Custom Mappings",
        compute="_compute_available_field_mappings",
    )

    @api.depends("payment_ref", "partner_id", "amount")
    def _compute_available_field_mappings(self):
        """Contar cuántos mapeos están disponibles para esta línea"""
        for record in self:
            mappings = self.env["reconcile.field.mapping"].search(
                [
                    ("active", "=", True),
                    ("company_id", "in", [False, record.company_id.id]),
                    ("target_model", "=", "account.bank.statement.line"),
                ]
            )
            record.available_field_mappings_count = len(mappings)

    def _default_reconcile_data(self, from_unreconcile=False):
        """
        Sobrescribir para agregar sugerencias basadas en mapeos de campos personalizados
        """
        # Llamar al método original
        result = super()._default_reconcile_data(from_unreconcile=from_unreconcile)

        # Si ya hay auto-reconciliación o estamos des-conciliando, no agregar más
        if from_unreconcile:
            return result

        # Buscar mapeos activos para líneas bancarias
        mappings = self.env["reconcile.field.mapping"].search(
            [
                ("active", "=", True),
                ("company_id", "in", [False, self.company_id.id]),
                ("target_model", "=", "account.bank.statement.line"),
            ]
        )

        if not mappings:
            return result

        # Buscar líneas coincidentes usando los mapeos
        matching_lines = self._find_matching_lines_from_mappings(mappings)

        if not matching_lines:
            return result

        # Agregar las líneas encontradas a los datos de conciliación
        result = self._add_matching_lines_to_reconcile_data(result, matching_lines)

        return result

    def _find_matching_lines_from_mappings(self, mappings):
        """
        Encontrar líneas de facturas que coincidan usando los mapeos configurados

        :param mappings: recordset de reconcile.field.mapping
        :return: recordset de account.move.line
        """
        self.ensure_one()

        matching_lines = self.env["account.move.line"].browse()

        for mapping in mappings:
            try:
                # Usar el método del mapeo para encontrar líneas
                lines = mapping.find_matching_lines(self)
                matching_lines |= lines
            except Exception:
                # Si hay algún error, continuar con el siguiente mapeo
                continue

        # Eliminar duplicados y líneas ya reconciliadas
        matching_lines = matching_lines.filtered(lambda l: not l.reconciled)

        return matching_lines

    def _add_matching_lines_to_reconcile_data(self, reconcile_data, matching_lines):
        """
        Agregar líneas coincidentes a los datos de conciliación

        :param reconcile_data: dict con datos de conciliación
        :param matching_lines: recordset de account.move.line a agregar
        :return: dict actualizado con los datos de conciliación
        """
        self.ensure_one()

        if not matching_lines:
            return reconcile_data

        data = reconcile_data.get("data", [])
        reconcile_auxiliary_id = reconcile_data.get("reconcile_auxiliary_id", 1)

        # Calcular el monto pendiente
        currency = self._get_reconcile_currency()
        pending_amount = 0.0
        for line_data in data:
            if line_data.get("kind") != "suspense":
                pending_amount += self._get_amount_currency(line_data, currency)

        # Agregar líneas coincidentes hasta completar el monto
        amount_to_reconcile = abs(pending_amount)

        for move_line in matching_lines:
            if currency.is_zero(amount_to_reconcile):
                break

            # Calcular el monto máximo a usar de esta línea
            max_amount = min(
                abs(move_line.amount_residual),
                amount_to_reconcile,
            )

            # Ajustar signo según si es débito o crédito
            if pending_amount > 0:
                max_amount = -max_amount

            # Obtener datos de la línea para conciliación
            reconcile_auxiliary_id, lines = self._get_reconcile_line(
                move_line,
                "other",
                is_counterpart=True,
                max_amount=max_amount,
                reconcile_auxiliary_id=reconcile_auxiliary_id,
                move=True,
            )

            data.extend(lines)

            # Actualizar monto pendiente
            for line in lines:
                amount_to_reconcile -= abs(line.get("amount", 0))

        # Recalcular línea de suspense
        return self._recompute_suspense_line(
            data,
            reconcile_auxiliary_id,
            reconcile_data.get("manual_reference"),
        )

    def action_show_custom_field_mappings(self):
        """Abrir ventana con los mapeos de campos disponibles"""
        self.ensure_one()

        return {
            "name": "Custom Field Mappings",
            "type": "ir.actions.act_window",
            "res_model": "reconcile.field.mapping",
            "view_mode": "tree,form",
            "domain": [
                ("active", "=", True),
                ("company_id", "in", [False, self.company_id.id]),
                ("target_model", "=", "account.bank.statement.line"),
            ],
            "context": {"default_target_model_id": self.env.ref("account.model_account_bank_statement_line").id},
        }

    def button_find_custom_matches(self):
        """
        Botón para buscar manualmente coincidencias usando mapeos personalizados
        """
        self.ensure_one()

        # Buscar mapeos activos
        mappings = self.env["reconcile.field.mapping"].search(
            [
                ("active", "=", True),
                ("company_id", "in", [False, self.company_id.id]),
                ("target_model", "=", "account.bank.statement.line"),
            ]
        )

        if not mappings:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Mappings Found",
                    "message": "Please configure custom field mappings first.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Buscar líneas coincidentes
        matching_lines = self._find_matching_lines_from_mappings(mappings)

        if not matching_lines:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Matches Found",
                    "message": "No matching invoice lines found using custom field mappings.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Agregar todas las líneas encontradas
        for move_line in matching_lines:
            self._add_account_move_line(move_line, keep_current=True)

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
