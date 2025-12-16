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
        MODIFICADO: Buscar coincidencias automáticas, agruparlas por una clave de referencia
        y luego filtrar para asegurar que todos los apuntes de un grupo pertenezcan al MISMO partner.
        """
        self.ensure_one()
        _logger.info("========== FIND ALL MATCHES START (STRICT PARTNER LOGIC) ==========")
        _logger.info(f"Account: {self.account_id.code} - Partner: {self.partner_id.name if self.partner_id else 'All'}")
        _logger.info(f"Mapping: {mapping.name}")

        # 1. Obtener todos los apuntes coincidentes por referencia, sin filtrar por partner aún.
        # El resultado es un diccionario: {'ref_value': {line1, line2, ...}}
        lines_by_ref = self._get_all_lines_grouped_by_reference(mapping)

        # 2. Filtrar los grupos para asegurar la consistencia del partner.
        # El resultado es el mismo, pero eliminando referencias con partners mezclados.
        consistent_lines_by_ref = self._filter_groups_for_partner_consistency(lines_by_ref)

        # 3. Aplanar el diccionario a una lista de todos los apuntes válidos.
        all_matching_lines = self.env["account.move.line"].browse()
        for lines in consistent_lines_by_ref.values():
            all_matching_lines |= lines
        
        # 4. (Opcional pero recomendado) Filtrar por el partner del widget si está definido
        if self.partner_id:
            all_matching_lines = all_matching_lines.filtered(
                lambda l: l.partner_id == self.partner_id
            )
        
        _logger.info(f"Total unique lines to add after partner consistency check: {len(all_matching_lines)}")
        _logger.info("========== FIND ALL MATCHES END ==========")

        return all_matching_lines

    def _get_all_lines_grouped_by_reference(self, mapping):
        """
        NUEVO: Busca todas las líneas de origen y destino y las agrupa en un diccionario
        por el valor de su referencia.
        Retorna: {'ref_value_1': {lineA, lineB}, 'ref_value_2': {lineC}}
        """
        lines_by_ref = {}

        # Obtener todos los registros origen y destino
        source_records = self.env[mapping.source_model].search(
            mapping.source_domain and eval(mapping.source_domain) or []
        )
        target_records = self._search_all_target_records(mapping)

        # Procesar registros de ORIGEN (órdenes/facturas)
        for rec in source_records:
            ref_value = rec[mapping.source_field_name]
            if not ref_value:
                continue
            
            ref_str = str(ref_value).strip()
            invoices = mapping._get_invoices_from_source(rec)
            lines = mapping._get_receivable_payable_lines(invoices)
            
            if ref_str not in lines_by_ref:
                lines_by_ref[ref_str] = self.env["account.move.line"].browse()
            lines_by_ref[ref_str] |= lines

        # Procesar registros de DESTINO (pagos)
        for rec in target_records:
            ref_value = rec[mapping.target_field_name]
            if not ref_value:
                continue

            ref_str = str(ref_value).strip()
            lines = self._get_payment_lines([rec.id], mapping.target_model)
            
            # Buscar la orden/factura correspondiente para usar la misma clave de referencia
            source_recs_for_target = mapping._get_source_records(ref_str)
            if not source_recs_for_target:
                # Si no hay orden, usamos la referencia del pago como clave
                key = ref_str
                if key not in lines_by_ref:
                    lines_by_ref[key] = self.env["account.move.line"].browse()
                lines_by_ref[key] |= lines
            else:
                # Usar la referencia de la orden para agrupar
                for src in source_recs_for_target:
                    key = src[mapping.source_field_name]
                    if not key:
                        continue
                    key_str = str(key).strip()
                    if key_str not in lines_by_ref:
                        lines_by_ref[key_str] = self.env["account.move.line"].browse()
                    lines_by_ref[key_str] |= lines
        
        return lines_by_ref

    def _filter_groups_for_partner_consistency(self, lines_by_ref):
        """
        NUEVO: Toma un diccionario de apuntes agrupados por referencia y descarta
        los grupos que contengan más de un partner.
        """
        consistent_groups = {}
        _logger.info("--- Filtering for Partner Consistency ---")
        for ref, lines in lines_by_ref.items():
            if not lines:
                continue

            # Obtener todos los partners de este grupo (ignorando partners vacíos)
            partners = lines.mapped('partner_id').filtered(lambda p: p) # Filter out False partners
            
            # Un grupo es consistente si solo tiene un partner (o cero si todas las líneas no tienen partner, aunque esto es raro para receivable/payable)
            if len(partners) <= 1:
                consistent_groups[ref] = lines
                partner_name = partners.name if partners else "No Partner"
                _logger.info(f"  [OK] Ref '{ref}': Consistent partner '{partner_name}' ({len(lines)} lines)")
            else:
                partner_names = [p.name for p in partners]
                _logger.warning(
                    f"  [DISCARDED] Ref '{ref}': Inconsistent partners found: {partner_names}. "
                    f"This group will be ignored for automatic reconciliation."
                )
        return consistent_groups

    def _match_orders_to_payments(self, mapping):
        """
        DIRECCIÓN 1: Buscar desde órdenes hacia pagos
        Orden → Pago → Agregar ambos
        """
        # Esta función ya no añade líneas directamente a all_matching_lines.
        # Su lógica ahora está subsumida en _get_all_lines_grouped_by_reference.
        # Retorna un recordset vacío para mantener la compatibilidad con el método original
        # si alguna llamada externa aún lo espera, aunque _find_all_automatic_matches ya no lo usa.
        return self.env["account.move.line"].browse()

    def _match_payments_to_orders(self, mapping):
        """
        DIRECCIÓN 2: Buscar desde pagos hacia órdenes
        Pago → Orden → Factura → Agregar ambos
        """
        # Esta función ya no añade líneas directamente a all_matching_lines.
        # Su lógica ahora está subsumida en _get_all_lines_grouped_by_reference.
        # Retorna un recordset vacío para mantener la compatibilidad con el método original
        # si alguna llamada externa aún lo espera, aunque _find_all_automatic_matches ya no lo usa.
        return self.env["account.move.line"].browse()

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

    def find_next_match(self):
        """
        Buscar el siguiente grupo de conciliación y presentarlo en el widget

        Lógica:
        - Buscar todos los grupos de líneas que coincidan con el mapeo
        - Filtrar los grupos ya procesados
        - Si flexible_mode = False: Filtrar por abs(balance) <= tolerance_amount
        - Si flexible_mode = True: Mostrar cualquier grupo
        - Presentar el primer grupo elegible
        - Crear línea de ajuste si es necesario (solo en modo preciso)
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

        # Limpiar conciliación actual
        self.clean_reconcile()

        # Obtener grupos procesados
        import json
        processed_groups = json.loads(self.processed_groups or "[]")

        # Buscar todos los grupos
        all_groups = self._find_all_groups(mapping)

        if not all_groups:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Matches Found",
                    "message": "No matching groups found.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Filtrar grupos ya procesados
        eligible_groups = [
            group for group in all_groups
            if group['group_key'] not in processed_groups
        ]

        if not eligible_groups:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "All Groups Processed",
                    "message": "All matching groups have been processed. Click 'Reiniciar Sesión' to start over.",
                    "type": "info",
                    "sticky": False,
                },
            }

        # Aplicar filtro de tolerancia si modo preciso
        if not self.flexible_mode:
            eligible_groups = [
                group for group in eligible_groups
                if abs(group['balance']) <= self.tolerance_amount
            ]

        if not eligible_groups:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Groups Within Tolerance",
                    "message": f"No groups found with balance <= {self.tolerance_amount}. {len([g for g in all_groups if g['group_key'] not in processed_groups])} groups exceed tolerance.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Tomar el primer grupo
        next_group = eligible_groups[0]

        _logger.info(f"Presenting group {next_group['group_key']}: {len(next_group['lines'])} lines, balance: {next_group['balance']}")

        # Obtener los datos actuales de conciliación
        data = self.reconcile_data_info
        if not data:
            data = {"data": [], "counterparts": []}

        # Agregar líneas del grupo
        for line in next_group['lines']:
            if line.id not in data["counterparts"]:
                data["counterparts"].append(line.id)

        # Si está en modo preciso y hay diferencia, crear línea de ajuste
        if not self.flexible_mode and abs(next_group['balance']) > 0.01:
            adjustment_line = self._create_adjustment_line(next_group['balance'])
            if adjustment_line and adjustment_line.id not in data["counterparts"]:
                data["counterparts"].append(adjustment_line.id)

        # Recomputar los datos para actualizar el widget
        self.reconcile_data_info = self._recompute_data(data)

        # Marcar grupo como procesado
        processed_groups.append(next_group['group_key'])
        self.processed_groups = json.dumps(processed_groups)

        # Retornar acción de recarga
        return {
            "type": "ir.actions.client",
            "tag": "reload",
            "params": {
                "message": f"Group {next_group['group_key']}: {len(next_group['lines'])} lines, balance: {next_group['balance']:.2f}",
            },
        }

    def reconcile_all_remaining_matches(self):
        """
        Conciliar automáticamente todos los grupos restantes que estén dentro del margen de tolerancia

        Solo funciona en modo preciso (flexible_mode = False)
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

        if self.flexible_mode:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Not Available in Flexible Mode",
                    "message": "Batch reconciliation is only available in Precise Mode (flexible_mode = False).",
                    "type": "warning",
                    "sticky": False,
                },
            }

        mapping = self.custom_field_mapping_id

        # Obtener grupos procesados
        import json
        processed_groups = json.loads(self.processed_groups or "[]")

        # Buscar todos los grupos
        all_groups = self._find_all_groups(mapping)

        # Filtrar grupos ya procesados y dentro de tolerancia
        eligible_groups = [
            group for group in all_groups
            if group['group_key'] not in processed_groups
            and abs(group['balance']) <= self.tolerance_amount
        ]

        if not eligible_groups:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Groups to Reconcile",
                    "message": "No eligible groups found within tolerance.",
                    "type": "info",
                    "sticky": False,
                },
            }

        _logger.info(f"Batch reconciling {len(eligible_groups)} groups...")

        reconciled_count = 0
        errors = []

        for group in eligible_groups:
            try:
                # Limpiar widget
                self.clean_reconcile()

                # Obtener los datos actuales de conciliación
                data = self.reconcile_data_info
                if not data:
                    data = {"data": [], "counterparts": []}

                # Agregar líneas del grupo
                for line in group['lines']:
                    if line.id not in data["counterparts"]:
                        data["counterparts"].append(line.id)

                # Crear línea de ajuste si es necesario
                if abs(group['balance']) > 0.01:
                    adjustment_line = self._create_adjustment_line(group['balance'])
                    if adjustment_line and adjustment_line.id not in data["counterparts"]:
                        data["counterparts"].append(adjustment_line.id)

                # Recomputar los datos
                self.reconcile_data_info = self._recompute_data(data)

                # Intentar conciliar
                self.button_reconcile()

                # Marcar como procesado
                processed_groups.append(group['group_key'])
                reconciled_count += 1

                _logger.info(f"  Reconciled group {group['group_key']}: {len(group['lines'])} lines, balance: {group['balance']}")

            except Exception as e:
                error_msg = f"Group {group['group_key']}: {str(e)}"
                errors.append(error_msg)
                _logger.error(f"  Error reconciling group: {error_msg}")

        # Actualizar grupos procesados
        self.processed_groups = json.dumps(processed_groups)

        # Limpiar widget final
        self.clean_reconcile()

        # Mensaje de resultado
        message = f"Successfully reconciled {reconciled_count} groups."
        if errors:
            message += f" {len(errors)} errors occurred."

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Batch Reconciliation Complete",
                "message": message,
                "type": "success" if reconciled_count > 0 else "warning",
                "sticky": True,
            },
        }

    def button_reset_session(self):
        """
        Reiniciar la sesión de conciliación: limpiar grupos procesados y widget
        """
        self.ensure_one()

        import json
        self.processed_groups = json.dumps([])
        self.clean_reconcile()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Session Reset",
                "message": "The reconciliation session has been reset. You can now process all groups again.",
                "type": "success",
                "sticky": False,
            },
        }

    def _find_all_groups(self, mapping):
        """
        MODIFICADO: Encontrar todos los grupos de líneas que coincidan con el mapeo,
        utilizando la lógica de busqueda ya validada para la consistencia del partner.

        Retorna lista de diccionarios:
        [
            {
                'group_key': 'SO001',  # Valor de referencia
                'lines': recordset de account.move.line,
                'balance': 123.45,  # Balance total del grupo
            },
            ...
        ]
        """
        self.ensure_one()

        # Buscar todas las líneas coincidentes utilizando la nueva lógica de _find_all_automatic_matches
        # que ya incluye la validación de consistencia del partner.
        all_matching_lines = self._find_all_automatic_matches(mapping)

        if not all_matching_lines:
            return []

        # Agrupar las líneas ya filtradas por la clave de referencia/orden
        groups = {}

        for line in all_matching_lines:
            group_key = self._get_group_key_for_line(line, mapping)

            if not group_key:
                continue

            if group_key not in groups:
                groups[group_key] = self.env["account.move.line"].browse()

            groups[group_key] |= line

        # Convertir a lista con balance
        result = []
        for group_key, lines in groups.items():
            # Filtramos líneas sin partner para el cálculo del balance si fuera el caso,
            # aunque la lógica anterior ya debería haberlos excluido si eran inconsistentes.
            partners = lines.mapped('partner_id').filtered(lambda p: p)
            if not partners and self.partner_id: # Si no hay partner en las líneas, pero el widget tiene uno, descartar
                _logger.info(f"  [SKIPPING GROUP] Group '{group_key}' has no partners, but widget has partner {self.partner_id.name}")
                continue
            
            # Si el widget tiene un partner definido, aseguramos que todas las líneas del grupo coincidan con ese partner.
            # Esto es un filtro adicional por si _find_all_automatic_matches trajo algo más amplio.
            if self.partner_id and any(line.partner_id != self.partner_id for line in lines):
                _logger.info(f"  [SKIPPING GROUP] Group '{group_key}' contains lines for a different partner than the widget partner {self.partner_id.name}")
                continue

            balance = sum(lines.mapped('amount_residual'))
            result.append({
                'group_key': group_key,
                'lines': lines,
                'balance': balance,
            })

        # Ordenar por balance absoluto (los más balanceados primero)
        result.sort(key=lambda g: abs(g['balance']))

        _logger.info(f"Found {len(result)} groups from {len(all_matching_lines)} total lines after re-grouping and final checks.")

        return result

    def _get_group_key_for_line(self, line, mapping):
        """
        Obtener la clave de grupo para una línea

        Busca en la factura/pago el valor del campo de mapeo para agrupar
        """
        # Intentar desde la factura
        if line.move_id:
            # Buscar orden relacionada
            if mapping.source_model == "sale.order":
                # Buscar en invoice_line_ids -> sale_line_ids -> order_id
                for inv_line in line.move_id.invoice_line_ids:
                    for sale_line in inv_line.sale_line_ids:
                        if sale_line.order_id:
                            value = sale_line.order_id[mapping.source_field_name]
                            if value:
                                return str(value)

            elif mapping.source_model == "purchase.order":
                # Buscar en invoice_line_ids -> purchase_line_id -> order_id
                for inv_line in line.move_id.invoice_line_ids:
                    if inv_line.purchase_line_id and inv_line.purchase_line_id.order_id:
                        value = inv_line.purchase_line_id.order_id[mapping.source_field_name]
                        if value:
                            return str(value)

            elif mapping.source_model == "account.move":
                # Usar directamente el campo de la factura
                value = line.move_id[mapping.source_field_name]
                if value:
                    return str(value)

        # Si no encontramos desde la orden, usar el name o ref de la línea
        return line.name or line.ref or f"line_{line.id}"

    def _create_adjustment_line(self, balance):
        """
        Crear una línea de ajuste para la diferencia

        :param balance: diferencia a ajustar (positivo o negativo)
        :return: account.move.line de ajuste
        """
        self.ensure_one()

        if not self.adjustment_account_id:
            _logger.warning("No adjustment account configured, cannot create adjustment line")
            return None

        # Crear un asiento de ajuste
        move_vals = {
            'journal_id': self.journal_id.id,
            'date': fields.Date.today(),
            'ref': f"Adjustment for reconciliation - Balance: {balance:.2f}",
            'line_ids': [
                (0, 0, {
                    'account_id': self.adjustment_account_id.id,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'name': f"Rounding adjustment",
                    'debit': abs(balance) if balance < 0 else 0.0,
                    'credit': abs(balance) if balance > 0 else 0.0,
                }),
                (0, 0, {
                    'account_id': self.account_id.id,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'name': f"Rounding adjustment counterpart",
                    'debit': abs(balance) if balance > 0 else 0.0,
                    'credit': abs(balance) if balance < 0 else 0.0,
                }),
            ],
        }

        move = self.env['account.move'].create(move_vals)
        move.action_post()

        # Retornar la línea de la cuenta de ajuste
        adjustment_line = move.line_ids.filtered(
            lambda l: l.account_id == self.account_id
        )

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
