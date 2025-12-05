# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountAccountReconcile(models.Model):
    _inherit = "account.account.reconcile"

    # Campo para almacenar el mapeo de campos personalizado seleccionado
    custom_field_mapping_id = fields.Many2one(
        "reconcile.field.mapping",
        string="Custom Field Mapping",
        compute="_compute_custom_filter_fields",
        inverse="_inverse_custom_field_mapping_id",
        domain="[('active', '=', True), ('target_model', 'in', ['account.move.line', 'account.payment', 'account.bank.statement.line'])]",
    )

    # Campos de filtro dinámicos
    custom_filter_value = fields.Char(
        string="Filter Value",
        compute="_compute_custom_filter_fields",
        inverse="_inverse_custom_filter_value",
        help="Enter the value to search for in the source model",
    )

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

        # Si no hay líneas directas, buscar desde pagos relacionados
        if not matching_lines and mapping.target_model == 'account.payment':
            # Buscar pagos relacionados con estas facturas
            payments = self.env['account.payment'].search([
                ('reconciled_invoice_ids', 'in', invoices.ids)
            ])
            # Obtener las líneas de movimiento de esos pagos
            for payment in payments:
                matching_lines |= payment.line_ids.filtered(
                    lambda l: l.account_id.account_type in ['asset_receivable', 'liability_payable']
                    and not l.reconciled
                )

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

    def button_find_all_matches(self):
        """
        Buscar TODAS las coincidencias automáticamente usando el mapeo seleccionado
        Sin necesidad de ingresar un valor manualmente
        """
        self.ensure_one()

        if not self.custom_field_mapping_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Missing Mapping",
                    "message": "Please select a custom field mapping first.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        mapping = self.custom_field_mapping_id

        # Limpiar conciliación actual primero
        self.clean_reconcile()

        # Buscar todas las órdenes/facturas con facturas pendientes
        # que coincidan con la cuenta y partner actuales
        matching_lines = self._find_all_automatic_matches(mapping)

        if not matching_lines:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Matches Found",
                    "message": "No automatic matches found using the selected mapping.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        _logger.info(f"Adding {len(matching_lines)} lines to reconciliation widget...")

        # Obtener los datos actuales de conciliación
        data = self.reconcile_data_info
        if not data:
            data = {"data": [], "counterparts": []}

        # Agregar todas las líneas encontradas a counterparts
        for line in matching_lines:
            if line.id not in data["counterparts"]:
                data["counterparts"].append(line.id)
                _logger.info(f"  Added line {line.id} - {line.name}")

        # Recomputar los datos para actualizar el widget
        self.reconcile_data_info = self._recompute_data(data)

        _logger.info(f"Reconcile data updated. Total counterparts: {len(data['counterparts'])}")

        # Retornar una acción que recargue el formulario para refrescar el widget
        return {
            "type": "ir.actions.client",
            "tag": "reload",
            "params": {
                "message": f"Found and added {len(matching_lines)} matching line(s)!",
            },
        }

    def _find_all_automatic_matches(self, mapping):
        """
        Buscar coincidencias automáticas orden por orden

        Lógica CORRECTA:
        1. Por cada ORDEN que tenga valor en el campo origen
        2. Obtener las FACTURAS de esa orden
        3. Buscar PAGOS que coincidan con el valor de la orden
        4. Agregar las líneas de la factura + las líneas del pago
        5. Repetir para todas las órdenes
        """
        self.ensure_one()
        all_matching_lines = self.env["account.move.line"].browse()

        _logger.info(f"========== FIND ALL MATCHES START (ORDER BY ORDER) ==========")
        _logger.info(f"Account: {self.account_id.code} - Partner: {self.partner_id.name if self.partner_id else 'All'}")
        _logger.info(f"Mapping: {mapping.name}")
        _logger.info(f"Source: {mapping.source_model}.{mapping.source_field_name}")
        _logger.info(f"Target: {mapping.target_model}.{mapping.target_field_name}")
        _logger.info(f"Operator: {mapping.operator}")

        # 1. Buscar todas las órdenes que tengan valor en el campo origen
        source_domain = []
        if mapping.source_domain and mapping.source_domain != "[]":
            try:
                source_domain = eval(mapping.source_domain)
            except Exception:
                pass

        all_source_records = self.env[mapping.source_model].search(source_domain)
        _logger.info(f"Found {len(all_source_records)} source records ({mapping.source_model})")

        # 2. Buscar todos los pagos disponibles (para hacer búsquedas eficientes)
        all_target_records = self._search_all_target_records(mapping)
        _logger.info(f"Found {len(all_target_records)} target records ({mapping.target_model})")

        if not all_target_records:
            _logger.warning("No target records found!")
            return all_matching_lines

        # Crear diccionario de pagos por valor para búsqueda rápida
        # {valor: [payment_record, payment_record, ...]}
        payment_by_value = {}
        for target_record in all_target_records:
            target_value = target_record[mapping.target_field_name]
            if not target_value:
                continue

            target_value_str = str(target_value).strip().lower()
            if target_value_str:
                if target_value_str not in payment_by_value:
                    payment_by_value[target_value_str] = []
                payment_by_value[target_value_str].append(target_record)

        _logger.info(f"Indexed {len(payment_by_value)} unique payment values")

        # 3. Procesar cada orden individualmente
        total_matches = 0
        for source_record in all_source_records:
            source_value = source_record[mapping.source_field_name]
            if not source_value:
                continue

            source_value_str = str(source_value).strip()

            # 4. Buscar pagos que coincidan con ESTA orden específica
            matching_payments = self.env[mapping.target_model].browse()

            for payment_value_str, payment_records in payment_by_value.items():
                if self._compare_values(source_value_str, payment_value_str, mapping.operator):
                    matching_payments |= self.env[mapping.target_model].browse([p.id for p in payment_records])
                    _logger.info(f"  MATCH: Order value '{source_value_str}' matches payment value '{payment_value_str}'")

            if not matching_payments:
                continue

            # 5. Obtener facturas de ESTA orden
            order_invoices = mapping._get_invoices_from_source(source_record)

            if not order_invoices:
                _logger.info(f"  Order {source_record.name} (value={source_value_str}): No invoices found")
                continue

            # 6. Obtener líneas por cobrar/pagar de las facturas de ESTA orden
            invoice_lines = mapping._get_receivable_payable_lines(order_invoices)

            # 7. Obtener líneas de los pagos que coincidieron con ESTA orden
            payment_lines = self._get_payment_lines(matching_payments.ids, mapping.target_model)

            # 8. Combinar las líneas de esta orden + sus pagos
            order_lines = invoice_lines | payment_lines

            # 9. Filtrar por cuenta
            order_lines_filtered = order_lines.filtered(
                lambda l: l.account_id == self.account_id
            )

            if order_lines_filtered:
                all_matching_lines |= order_lines_filtered
                total_matches += 1
                _logger.info(f"  Order {source_record.name}: Added {len(invoice_lines.filtered(lambda l: l.account_id == self.account_id))} invoice lines + {len(payment_lines.filtered(lambda l: l.account_id == self.account_id))} payment lines")

        _logger.info(f"Total orders with matches: {total_matches}")
        _logger.info(f"Total lines to add: {len(all_matching_lines)}")
        _logger.info(f"========== FIND ALL MATCHES END ==========")

        return all_matching_lines

    def _get_payment_lines(self, payment_ids, target_model):
        """
        Obtener las líneas de journal items de los pagos que coincidieron
        Incluye líneas NO conciliadas Y líneas parcialmente conciliadas (con saldo pendiente)

        :param payment_ids: IDs de pagos/registros que coincidieron
        :param target_model: modelo destino (account.payment, account.bank.statement.line, account.move.line)
        :return: recordset de account.move.line
        """
        lines = self.env["account.move.line"].browse()

        if not payment_ids:
            return lines

        if target_model == "account.payment":
            # Los pagos tienen move_id que contiene las líneas
            payments = self.env["account.payment"].browse(list(payment_ids))
            _logger.info(f"Processing {len(payments)} payments to extract lines")

            for payment in payments:
                if payment.move_id:
                    # Obtener líneas de cuentas por cobrar/pagar del asiento de pago
                    # que tengan saldo pendiente (amount_residual != 0)
                    payment_lines = payment.move_id.line_ids.filtered(
                        lambda line: line.account_id.account_type in [
                            "asset_receivable",
                            "liability_payable",
                        ]
                        and line.amount_residual != 0  # Incluye NO conciliadas y parcialmente conciliadas
                    )
                    if payment_lines:
                        lines |= payment_lines
                        for line in payment_lines:
                            status = "unreconciled" if not line.reconciled else "partially reconciled"
                            _logger.info(f"  Payment {payment.name}: Line {line.id} - {status}, residual: {line.amount_residual}")

        elif target_model == "account.bank.statement.line":
            # Las líneas bancarias tienen move_id
            bank_lines = self.env["account.bank.statement.line"].browse(list(payment_ids))
            _logger.info(f"Processing {len(bank_lines)} bank statement lines to extract move lines")

            for bank_line in bank_lines:
                if bank_line.move_id:
                    # Obtener líneas de cuentas por cobrar/pagar del asiento
                    # que tengan saldo pendiente (amount_residual != 0)
                    move_lines = bank_line.move_id.line_ids.filtered(
                        lambda line: line.account_id.account_type in [
                            "asset_receivable",
                            "liability_payable",
                        ]
                        and line.amount_residual != 0  # Incluye NO conciliadas y parcialmente conciliadas
                    )
                    if move_lines:
                        lines |= move_lines
                        for line in move_lines:
                            status = "unreconciled" if not line.reconciled else "partially reconciled"
                            _logger.info(f"  Bank Line {bank_line.name}: Line {line.id} - {status}, residual: {line.amount_residual}")

        elif target_model == "account.move.line":
            # Ya son move.line, solo filtrar por tipo de cuenta y saldo pendiente
            all_lines = self.env["account.move.line"].browse(list(payment_ids))
            lines = all_lines.filtered(
                lambda line: line.account_id.account_type in [
                    "asset_receivable",
                    "liability_payable",
                ]
                and line.amount_residual != 0  # Incluye NO conciliadas y parcialmente conciliadas
            )
            _logger.info(f"Processing {len(all_lines)} move lines, {len(lines)} have pending residual (unreconciled or partial)")

        return lines

    def _search_all_target_records(self, mapping):
        """
        Buscar todos los registros en el modelo destino
        Incluye tanto registros NO conciliados como parcialmente conciliados
        """
        domain = [("company_id", "=", self.company_id.id)]

        # Agregar filtros adicionales si existen
        if mapping.target_domain and mapping.target_domain != "[]":
            try:
                additional_domain = eval(mapping.target_domain)
                domain.extend(additional_domain)
            except Exception:
                pass

        # Filtros específicos por tipo de modelo
        if mapping.target_model == "account.payment":
            # Incluir pagos posted Y reconciled (pueden tener saldo pendiente en conciliaciones parciales)
            domain.append(("state", "in", ["posted", "reconciled"]))
        elif mapping.target_model == "account.bank.statement.line":
            domain.append(("state", "=", "posted"))
        elif mapping.target_model == "account.move.line":
            # Para move.line, buscar todas las líneas posted
            # El filtro de amount_residual se aplica después en _get_payment_lines()
            domain.append(("parent_state", "=", "posted"))
            # NO filtrar por reconciled aquí para incluir parcialmente conciliadas

        return self.env[mapping.target_model].search(domain)

    def _compare_values(self, source_value, target_value, operator):
        """Comparar dos valores usando el operador especificado"""
        if not source_value or not target_value:
            return False

        source_value = str(source_value).strip().lower()
        target_value = str(target_value).strip().lower()

        if operator == "=":
            return source_value == target_value
        elif operator == "!=":
            return source_value != target_value
        elif operator == "like":
            return source_value in target_value or target_value in source_value
        elif operator == "ilike":
            return source_value in target_value or target_value in source_value
        elif operator == "in":
            return source_value in target_value.split(",")
        elif operator == "not in":
            return source_value not in target_value.split(",")

        return False

    def button_apply_custom_filter(self):
        """
        Botón para aplicar el filtro personalizado (búsqueda manual)
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
