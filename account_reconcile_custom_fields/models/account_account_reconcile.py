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

    # Nuevos campos para conciliación masiva asistida
    flexible_mode = fields.Boolean(
        string="Modo Flexible",
        default=False,
        compute="_compute_custom_filter_fields",
        inverse="_inverse_flexible_mode",
        help="Activar para ignorar el margen de error y mostrar todos los grupos",
    )

    tolerance_amount = fields.Monetary(
        string="Margen de Error Permitido",
        currency_field="company_currency_id",
        default=0.0,
        compute="_compute_custom_filter_fields",
        inverse="_inverse_tolerance_amount",
        help="Diferencia máxima permitida para considerar un grupo como conciliable automáticamente",
    )

    adjustment_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de Ajuste",
        compute="_compute_custom_filter_fields",
        inverse="_inverse_adjustment_account_id",
        help="Cuenta contable para registrar las diferencias de redondeo",
    )

    processed_groups = fields.Text(
        string="Grupos Procesados",
        compute="_compute_custom_filter_fields",
        inverse="_inverse_processed_groups",
        help="Lista de grupos ya procesados en esta sesión",
    )

    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
        readonly=True,
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
                record.flexible_mode = data_record.custom_filter_data.get(
                    "flexible_mode", False
                )
                record.tolerance_amount = data_record.custom_filter_data.get(
                    "tolerance_amount", 0.0
                )
                record.adjustment_account_id = data_record.custom_filter_data.get(
                    "adjustment_account_id", False
                )
                record.processed_groups = data_record.custom_filter_data.get(
                    "processed_groups", "[]"
                )
            else:
                record.custom_field_mapping_id = False
                record.custom_filter_value = False
                record.flexible_mode = False
                record.tolerance_amount = 0.0
                record.adjustment_account_id = False
                record.processed_groups = "[]"

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

    def _inverse_flexible_mode(self):
        """Guardar el modo flexible"""
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
            custom_data["flexible_mode"] = record.flexible_mode
            data_record.custom_filter_data = custom_data

    def _inverse_tolerance_amount(self):
        """Guardar el margen de error"""
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
            custom_data["tolerance_amount"] = record.tolerance_amount
            data_record.custom_filter_data = custom_data

    def _inverse_adjustment_account_id(self):
        """Guardar la cuenta de ajuste"""
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
            custom_data["adjustment_account_id"] = (
                record.adjustment_account_id.id if record.adjustment_account_id else False
            )
            data_record.custom_filter_data = custom_data

    def _inverse_processed_groups(self):
        """Guardar los grupos procesados"""
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
            custom_data["processed_groups"] = record.processed_groups or "[]"
            data_record.custom_filter_data = custom_data

    def _compute_reconcile_data_info(self):
        """
        Extender para agregar sugerencias basadas en mapeos personalizados
        """
        super()._compute_reconcile_data_info()
        for record in self:
            if record.custom_field_mapping_id and record.custom_filter_value:
                matching_lines = record._find_matching_lines_from_custom_filter()
                if matching_lines:
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
        source_records = mapping._get_source_records(self.custom_filter_value)
        if not source_records:
            return self.env["account.move.line"].browse()
        invoices = mapping._get_invoices_from_source(source_records)
        if not invoices:
            return self.env["account.move.line"].browse()
        matching_lines = mapping._get_receivable_payable_lines(invoices)
        if not matching_lines and mapping.target_model == 'account.payment':
            payments = self.env['account.payment'].search([
                ('reconciled_invoice_ids', 'in', invoices.ids)
            ])
            for payment in payments:
                matching_lines |= payment.line_ids.filtered(
                    lambda l: l.account_id.account_type in ['asset_receivable', 'liability_payable']
                    and not l.reconciled
                )
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
        """
        self.ensure_one()
        if not self.custom_field_mapping_id:
            return self._notify("Mapeo Faltante", "Por favor seleccione un mapeo de campos.", "warning")
        mapping = self.custom_field_mapping_id
        self.clean_reconcile()
        matching_lines = self._find_all_automatic_matches(mapping)
        if not matching_lines:
            return self._notify("Sin Coincidencias", "No se encontraron coincidencias automáticas.", "warning")
        
        _logger.info(f"Adding {len(matching_lines)} lines to reconciliation widget...")
        data = self.reconcile_data_info or {"data": [], "counterparts": []}
        for line in matching_lines:
            if line.id not in data["counterparts"]:
                data["counterparts"].append(line.id)
                _logger.info(f"  Added line {line.id} - {line.name}")
        self.reconcile_data_info = self._recompute_data(data)
        _logger.info(f"Reconcile data updated. Total counterparts: {len(data['counterparts'])}")
        return {
            "type": "ir.actions.client",
            "tag": "reload",
            "params": {"message": f"Se encontraron y añadieron {len(matching_lines)} apunte(s)!"},
        }

    def _find_all_automatic_matches(self, mapping):
        """
        Lógica contextual para encontrar todas las coincidencias para los botones masivos.
        """
        self.ensure_one()
        _logger.info("========== FIND ALL MATCHES START (CONTEXTUAL STRATEGY V3) ==========")
        domain = [
            ("account_id", "=", self.account_id.id),
            ("reconciled", "=", False),
            ("amount_residual", "!=", 0),
        ]
        if self.partner_id:
            domain.append(("partner_id", "=", self.partner_id.id))
        initial_lines = self.env["account.move.line"].search(domain)
        if not initial_lines:
            _logger.info("No unreconciled lines found for the current context.")
            return self.env["account.move.line"].browse()
        _logger.info(f"Found {len(initial_lines)} initial unreconciled lines to process.")
        refs_to_process = self._get_references_from_lines(initial_lines, mapping)
        if not refs_to_process:
            _logger.info("No references found from the initial lines.")
            return self.env["account.move.line"].browse()
        
        valid_lines = self.env["account.move.line"].browse()
        for ref in refs_to_process:
            _logger.info(f"--- Processing Ref for 'find all': '{ref}' ---")
            lines_for_ref = self._get_all_lines_for_refs([ref], mapping)
            if len(lines_for_ref) < 2:
                continue
            partners = lines_for_ref.mapped("partner_id").filtered(lambda p: p)
            if len(partners) > 1:
                continue
            if self.partner_id and partners and partners != self.partner_id:
                continue
            if not (any(line.debit > 0 for line in lines_for_ref) and any(line.credit > 0 for line in lines_for_ref)):
                continue
            valid_lines |= lines_for_ref
        _logger.info(f"Total unique valid lines to add: {len(valid_lines)}")
        _logger.info("========== FIND ALL MATCHES END (CONTEXTUAL STRATEGY V3) ==========")
        return valid_lines

    def _get_references_from_lines(self, lines, mapping):
        refs = set()
        source_field = mapping.source_field_name
        target_field = mapping.target_field_name
        for line in lines:
            move = line.move_id
            if move:
                if mapping.source_model == "account.move" and hasattr(move, source_field):
                    value = move[source_field]
                    if value: refs.add(str(value).strip())
                elif mapping.source_model == "sale.order":
                    for inv_line in move.invoice_line_ids:
                        for sale_line in inv_line.sale_line_ids:
                            if sale_line.order_id and hasattr(sale_line.order_id, source_field):
                                value = sale_line.order_id[source_field]
                                if value: refs.add(str(value).strip())
                elif mapping.source_model == "purchase.order":
                    for inv_line in move.invoice_line_ids:
                        if inv_line.purchase_line_id and inv_line.purchase_line_id.order_id and hasattr(inv_line.purchase_line_id.order_id, source_field):
                            value = inv_line.purchase_line_id.order_id[source_field]
                            if value: refs.add(str(value).strip())
            if mapping.target_model == "account.payment":
                payment = self.env["account.payment"].search([("move_id", "=", line.move_id.id)], limit=1)
                if payment and hasattr(payment, target_field):
                    value = payment[target_field]
                    if value: refs.add(str(value).strip())
            elif mapping.target_model == "account.bank.statement.line":
                st_line = self.env["account.bank.statement.line"].search([("move_id", "=", line.move_id.id)], limit=1)
                if st_line and hasattr(st_line, target_field):
                    value = st_line[target_field]
                    if value: refs.add(str(value).strip())
        _logger.info(f"Found {len(refs)} unique references from initial lines: {refs}")
        return refs

    def _get_payment_lines(self, payment_ids, target_model):
        lines = self.env["account.move.line"].browse()
        if not payment_ids:
            return lines
        if target_model == "account.payment":
            payments = self.env["account.payment"].browse(list(payment_ids))
            _logger.info(f"Processing {len(payments)} payments to extract lines")
            for payment in payments:
                if payment.move_id:
                    payment_lines = payment.move_id.line_ids.filtered(
                        lambda line: line.account_id.account_type in ["asset_receivable", "liability_payable"]
                        and line.amount_residual != 0
                    )
                    if payment_lines:
                        lines |= payment_lines
        elif target_model == "account.bank.statement.line":
            bank_lines = self.env["account.bank.statement.line"].browse(list(payment_ids))
            _logger.info(f"Processing {len(bank_lines)} bank statement lines to extract move lines")
            for bank_line in bank_lines:
                if bank_line.move_id:
                    move_lines = bank_line.move_id.line_ids.filtered(
                        lambda line: line.account_id.account_type in ["asset_receivable", "liability_payable"]
                        and line.amount_residual != 0
                    )
                    if move_lines:
                        lines |= move_lines
        elif target_model == "account.move.line":
            all_lines = self.env["account.move.line"].browse(list(payment_ids))
            lines = all_lines.filtered(
                lambda line: line.account_id.account_type in ["asset_receivable", "liability_payable"]
                and line.amount_residual != 0
            )
        return lines

    def _search_all_target_records(self, mapping):
        domain = [("company_id", "=", self.company_id.id)]
        if mapping.target_domain and mapping.target_domain != "[]":
            try:
                domain.extend(eval(mapping.target_domain))
            except Exception:
                pass
        if mapping.target_model == "account.payment":
            domain.append(("state", "in", ["posted", "reconciled"]))
        elif mapping.target_model == "account.bank.statement.line":
            domain.append(("state", "=", "posted"))
        elif mapping.target_model == "account.move.line":
            domain.append(("parent_state", "=", "posted"))
        return self.env[mapping.target_model].search(domain)

    def _compare_values(self, source_value, target_value, operator):
        if not source_value or not target_value:
            return False
        source_value = str(source_value).strip().lower()
        target_value = str(target_value).strip().lower()
        if operator == "=":
            return source_value == target_value
        elif operator == "!=":
            return source_value != target_value
        elif operator in ("like", "ilike"):
            return source_value in target_value or target_value in source_value
        elif operator == "in":
            return source_value in target_value.split(",")
        elif operator == "not in":
            return source_value not in target_value.split(",")
        return False

    def button_apply_custom_filter(self):
        self.ensure_one()
        if not self.custom_field_mapping_id or not self.custom_filter_value:
            return self._notify("Información Faltante", "Por favor seleccione un mapeo y un valor de filtro.", "warning")
        matching_lines = self._find_matching_lines_from_custom_filter()
        if not matching_lines:
            return self._notify("Sin Coincidencias", f"No se encontraron apuntes para '{self.custom_filter_value}'.", "warning")
        for line in matching_lines:
            self._add_account_move_line(line, keep_current=True)
        return self._notify("Coincidencias Encontradas", f"Se encontraron y añadieron {len(matching_lines)} apunte(s).", "success")

    def find_next_match(self):
        """
        REESCRITO (V4.2): Lógica "uno por uno" centrada en la factura, para manejar facturas globales.
        1. Encuentra la primera factura no procesada en el widget.
        2. Recolecta TODAS las referencias de las órdenes que componen esa factura.
        3. Busca pagos que coincidan con CUALQUIERA de esas referencias.
        4. Forma y valida un único grupo (la factura completa + los pagos encontrados).
        5. Presenta el grupo y marca la FACTURA como procesada.
        """
        self.ensure_one()

        if not self.custom_field_mapping_id:
            return self._notify("Mapeo Faltante", "Por favor seleccione un mapeo de campos.", "warning")

        lines_domain = [
            ("account_id", "=", self.account_id.id),
            ("reconciled", "=", False),
            ("amount_residual", "!=", 0),
            ("debit", ">", 0),
        ]
        if self.partner_id:
            lines_domain.append(("partner_id", "=", self.partner_id.id))
        
        all_candidate_lines = self.env["account.move.line"].search(lines_domain, order="date, id")
        
        import json
        processed_move_ids = json.loads(self.processed_groups or "[]")

        for seed_line in all_candidate_lines:
            invoice_move = seed_line.move_id
            if not invoice_move or invoice_move.id in processed_move_ids:
                continue

            _logger.info(f"--- Intentando construir grupo para la Factura: '{invoice_move.name}' (ID: {invoice_move.id}) ---")
            
            processed_move_ids.append(invoice_move.id)

            all_refs_from_invoice = self._get_all_refs_from_invoice(invoice_move, self.custom_field_mapping_id)
            if not all_refs_from_invoice:
                _logger.info(f"  [DESCARTADO] Factura '{invoice_move.name}': No se encontraron referencias de origen.")
                continue
            
            _logger.info(f"  Referencias encontradas en la factura: {all_refs_from_invoice}")

            group_lines = self._get_all_lines_for_refs(all_refs_from_invoice, self.custom_field_mapping_id)

            if len(group_lines) < 2:
                _logger.info(f"  [DESCARTADO] Grupo para refs {all_refs_from_invoice}: Tiene menos de 2 apuntes.")
                continue

            partners = group_lines.mapped("partner_id").filtered(lambda p: p)
            if len(partners) > 1:
                _logger.warning(f"  [DESCARTADO] Grupo para refs {all_refs_from_invoice}: Partners inconsistentes: {[p.name for p in partners]}.")
                continue
            
            if self.partner_id and partners and partners != self.partner_id:
                _logger.warning(f"  [DESCARTADO] Grupo para refs {all_refs_from_invoice}: Partner del grupo '{partners.name}' no coincide con el del widget '{self.partner_id.name}'.")
                continue

            if not (any(line.debit > 0 for line in group_lines) and any(line.credit > 0 for line in group_lines)):
                _logger.warning(f"  [DESCARTADO] Grupo para refs {all_refs_from_invoice}: No tiene débitos y créditos.")
                continue

            _logger.info(f"  [OK] Grupo para refs {all_refs_from_invoice} es válido con {len(group_lines)} apuntes.")
            self.processed_groups = json.dumps(processed_move_ids)
            self.clean_reconcile()

            balance = sum(group_lines.mapped('amount_residual'))
            
            data = self.reconcile_data_info or {"data": [], "counterparts": []}
            for line in group_lines:
                if line.id not in data["counterparts"]:
                    data["counterparts"].append(line.id)
            
            if not self.flexible_mode and abs(balance) > 0.01 and abs(balance) <= self.tolerance_amount:
                adjustment_line = self._create_adjustment_line(balance)
                if adjustment_line and adjustment_line.id not in data["counterparts"]:
                    data["counterparts"].append(adjustment_line.id)

            self.reconcile_data_info = self._recompute_data(data)
            
            return {
                "type": "ir.actions.client",
                "tag": "reload",
                "params": {"message": f"Grupo para Factura {invoice_move.name} ({len(group_lines)} apuntes), Balance: {balance:.2f}"},
            }

        self.processed_groups = json.dumps(processed_move_ids)
        return self._notify("Sin más coincidencias", "No se encontraron más facturas con grupos válidos para conciliar.", "info")

    def _get_all_refs_from_invoice(self, invoice_move, mapping):
        refs = set()
        source_field = mapping.source_field_name
        for inv_line in invoice_move.invoice_line_ids:
            if mapping.source_model == "sale.order":
                for sale_line in inv_line.sale_line_ids:
                    if sale_line.order_id and hasattr(sale_line.order_id, source_field):
                        value = sale_line.order_id[source_field]
                        if value: refs.add(str(value).strip())
            elif mapping.source_model == "purchase.order":
                if inv_line.purchase_line_id and inv_line.purchase_line_id.order_id and hasattr(inv_line.purchase_line_id.order_id, source_field):
                    value = inv_line.purchase_line_id.order_id[source_field]
                    if value: refs.add(str(value).strip())
            elif mapping.source_model == "account.move" and hasattr(invoice_move, source_field):
                 value = invoice_move[source_field]
                 if value: refs.add(str(value).strip())
        return list(refs)

    def _get_all_lines_for_refs(self, refs, mapping):
        all_lines = self.env["account.move.line"].browse()
        if not refs:
            return all_lines
        line_domain = [('amount_residual', '!=', 0)]
        source_recs = self.env[mapping.source_model].search([(mapping.source_field_name, 'in', refs)])
        if source_recs:
            invoices = mapping._get_invoices_from_source(source_recs)
            invoice_lines = invoices.mapped('line_ids').filtered_domain(line_domain)
            all_lines |= invoice_lines.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
            )
        target_recs = self.env[mapping.target_model].search([(mapping.target_field_name, 'in', refs)])
        if target_recs:
            payment_lines = self._get_payment_lines(target_recs.ids, mapping.target_model)
            all_lines |= payment_lines
        return all_lines

    def _notify(self, title, message, msg_type="info", sticky=False):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": title, "message": message, "type": msg_type, "sticky": sticky},
        }

    def reconcile_all_remaining_matches(self):
        """
        Conciliar automáticamente todos los grupos restantes que estén dentro del margen de tolerancia
        """
        self.ensure_one()
        if not self.custom_field_mapping_id:
            return self._notify("Mapeo Faltante", "Por favor seleccione un mapeo de campos.", "warning")
        if self.flexible_mode:
            return self._notify("Modo Incorrecto", "La conciliación masiva solo está disponible en Modo Preciso.", "warning")
        
        mapping = self.custom_field_mapping_id
        import json
        processed_groups = json.loads(self.processed_groups or "[]")
        all_groups = self._find_all_groups(mapping)
        eligible_groups = [
            group for group in all_groups
            if group['group_key'] not in processed_groups
            and abs(group['balance']) <= self.tolerance_amount
        ]

        if not eligible_groups:
            return self._notify("Sin Grupos", "No se encontraron grupos elegibles para conciliar.", "info")

        _logger.info(f"Batch reconciling {len(eligible_groups)} groups...")
        reconciled_count = 0
        errors = []
        for group in eligible_groups:
            try:
                self.clean_reconcile()
                data = self.reconcile_data_info or {"data": [], "counterparts": []}
                for line in group['lines']:
                    if line.id not in data["counterparts"]:
                        data["counterparts"].append(line.id)
                if abs(group['balance']) > 0.01:
                    adjustment_line = self._create_adjustment_line(group['balance'])
                    if adjustment_line and adjustment_line.id not in data["counterparts"]:
                        data["counterparts"].append(adjustment_line.id)
                self.reconcile_data_info = self._recompute_data(data)
                self.button_reconcile()
                processed_groups.append(group['group_key'])
                reconciled_count += 1
                _logger.info(f"  Reconciled group {group['group_key']}")
            except Exception as e:
                error_msg = f"Group {group['group_key']}: {str(e)}"
                errors.append(error_msg)
                _logger.error(f"  Error reconciling group: {error_msg}")
        
        self.processed_groups = json.dumps(processed_groups)
        self.clean_reconcile()
        message = f"Se conciliaron exitosamente {reconciled_count} grupos."
        if errors:
            message += f" Ocurrieron {len(errors)} errores."
        return self._notify("Conciliación Masiva Completa", message, "success" if reconciled_count > 0 else "warning", sticky=True)

    def button_reset_session(self):
        """
        Reiniciar la sesión de conciliación: limpiar grupos procesados y widget
        """
        self.ensure_one()
        self.processed_groups = "[]"
        self.clean_reconcile()
        return self._notify("Sesión Reiniciada", "Puede procesar todos los grupos de nuevo.", "success")

    def _find_all_groups(self, mapping):
        """
        Encontrar todos los grupos de líneas que coincidan con el mapeo.
        """
        self.ensure_one()
        all_matching_lines = self._find_all_automatic_matches(mapping)
        if not all_matching_lines:
            return []
        
        groups = {}
        for line in all_matching_lines:
            group_key = self._get_group_key_for_line(line, mapping)
            if not group_key:
                continue
            if group_key not in groups:
                groups[group_key] = self.env["account.move.line"].browse()
            groups[group_key] |= line
            
        result = []
        for group_key, lines in groups.items():
            if self.partner_id and any(line.partner_id != self.partner_id for line in lines):
                continue
            balance = sum(lines.mapped('amount_residual'))
            result.append({'group_key': group_key, 'lines': lines, 'balance': balance})
            
        result.sort(key=lambda g: abs(g['balance']))
        _logger.info(f"Found {len(result)} groups from {len(all_matching_lines)} total lines.")
        return result

    def _get_group_key_for_line(self, line, mapping):
        """
        Obtener la clave de grupo para una línea.
        """
        if line.move_id:
            if mapping.source_model == "sale.order":
                for inv_line in line.move_id.invoice_line_ids:
                    for sale_line in inv_line.sale_line_ids:
                        if sale_line.order_id:
                            return str(sale_line.order_id[mapping.source_field_name])
            elif mapping.source_model == "purchase.order":
                for inv_line in line.move_id.invoice_line_ids:
                    if inv_line.purchase_line_id and inv_line.purchase_line_id.order_id:
                        return str(inv_line.purchase_line_id.order_id[mapping.source_field_name])
            elif mapping.source_model == "account.move":
                return str(line.move_id[mapping.source_field_name])
        return line.name or line.ref or f"line_{line.id}"

    def _create_adjustment_line(self, balance):
        """
        Crear una línea de ajuste para la diferencia
        """
        self.ensure_one()
        if not self.adjustment_account_id:
            _logger.warning("No adjustment account configured, cannot create adjustment line")
            return None
        move_vals = {
            'journal_id': self.journal_id.id,
            'date': fields.Date.today(),
            'ref': f"Adjustment for reconciliation - Balance: {balance:.2f}",
            'line_ids': [
                (0, 0, {
                    'account_id': self.adjustment_account_id.id,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'name': "Rounding adjustment",
                    'debit': abs(balance) if balance < 0 else 0.0,
                    'credit': abs(balance) if balance > 0 else 0.0,
                }),
                (0, 0, {
                    'account_id': self.account_id.id,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'name': "Rounding adjustment counterpart",
                    'debit': abs(balance) if balance > 0 else 0.0,
                    'credit': abs(balance) if balance < 0 else 0.0,
                }),
            ],
        }
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        adjustment_line = move.line_ids.filtered(lambda l: l.account_id == self.account_id)
        _logger.info(f"Created adjustment line {adjustment_line.id} for balance {balance:.2f}")
        return adjustment_line

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
    _name = "account.account.reconcile.custom"
    _description = "Account Reconcile with Custom Field Filters"
    _inherit = "account.account.reconcile"
    _auto = False
    _table = "account_account_reconcile"

    def _where(self):
        where_clause = super()._where()
        if self.env.context.get("custom_mapping_filter"):
            pass
        return where_clause