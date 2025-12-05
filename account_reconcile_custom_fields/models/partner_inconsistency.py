# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PartnerInconsistency(models.TransientModel):
    """
    Modelo transitorio para detectar y corregir inconsistencias de proveedores
    antes de la conciliación.

    Este modelo NO realiza conciliaciones, solo detecta cuando pagos y facturas
    que deberían coincidir tienen diferentes proveedores, y permite corregirlo.
    """
    _name = "partner.inconsistency"
    _description = "Partner Inconsistency Detection and Correction"
    _order = "referencia_comun, id"

    referencia_comun = fields.Char(
        string="Referencia Común",
        help="Valor del campo de referencia que agrupa los apuntes",
        readonly=True,
    )
    tipo_problema = fields.Char(
        string="Tipo de Problema",
        default="Proveedores Diferentes",
        readonly=True,
    )

    # Información del pago
    pago_line_id = fields.Many2one(
        "account.move.line",
        string="Línea de Pago",
        readonly=True,
    )
    pago_move_id = fields.Many2one(
        "account.move",
        string="Asiento de Pago",
        related="pago_line_id.move_id",
        readonly=True,
    )
    proveedor_pago_id = fields.Many2one(
        "res.partner",
        string="Proveedor en Pago",
        related="pago_line_id.partner_id",
        readonly=True,
    )
    proveedor_pago = fields.Char(
        string="Proveedor Pago",
        compute="_compute_proveedor_names",
        store=True,
    )

    # Información de la factura
    factura_line_id = fields.Many2one(
        "account.move.line",
        string="Línea de Factura",
        readonly=True,
    )
    factura_move_id = fields.Many2one(
        "account.move",
        string="Factura",
        related="factura_line_id.move_id",
        readonly=True,
    )
    proveedor_factura_id = fields.Many2one(
        "res.partner",
        string="Proveedor en Factura",
        related="factura_line_id.partner_id",
        readonly=True,
    )
    proveedor_factura = fields.Char(
        string="Proveedor Factura",
        compute="_compute_proveedor_names",
        store=True,
    )

    # Información adicional
    cuenta_id = fields.Many2one(
        "account.account",
        string="Cuenta",
        related="pago_line_id.account_id",
        readonly=True,
    )
    monto_pago = fields.Monetary(
        string="Monto Pago",
        related="pago_line_id.amount_residual",
        readonly=True,
    )
    monto_factura = fields.Monetary(
        string="Monto Factura",
        related="factura_line_id.amount_residual",
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        related="pago_line_id.currency_id",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        related="pago_line_id.company_id",
        readonly=True,
    )

    mapping_id = fields.Many2one(
        "reconcile.field.mapping",
        string="Mapeo Utilizado",
        readonly=True,
    )

    @api.depends("proveedor_pago_id", "proveedor_factura_id")
    def _compute_proveedor_names(self):
        """Computar nombres de proveedores para mostrar en la vista"""
        for record in self:
            record.proveedor_pago = record.proveedor_pago_id.name if record.proveedor_pago_id else ""
            record.proveedor_factura = record.proveedor_factura_id.name if record.proveedor_factura_id else ""

    @api.model
    def find_inconsistencies(self, mapping_id=None):
        """
        Busca y prepara todas las inconsistencias de proveedores para ser mostradas.
        """
        _logger.info("========== BÚSQUEDA DE INCONSISTENCIAS DE PROVEEDORES ==========")
        self.search([]).unlink()

        mappings = self.env["reconcile.field.mapping"].browse(mapping_id) if mapping_id else \
                   self.env["reconcile.field.mapping"].search([("active", "=", True)])

        if not mappings:
            raise UserError(_("No hay mapeos de campos configurados."))

        all_inconsistencies_vals = []
        for mapping in mappings:
            _logger.info(f"Procesando mapeo: {mapping.name}")
            # Este método ahora solo devuelve los diccionarios de valores, no crea nada.
            inconsistency_vals = self._find_partner_inconsistencies_for_mapping(mapping)
            if inconsistency_vals:
                all_inconsistencies_vals.extend(inconsistency_vals)

        if all_inconsistencies_vals:
            self.create(all_inconsistencies_vals)
        
        _logger.info(f"Total de inconsistencias encontradas y creadas: {len(all_inconsistencies_vals)}")

        return {
            "type": "ir.actions.act_window",
            "name": "Inconsistencias de Proveedores",
            "res_model": "partner.inconsistency",
            "view_mode": "tree,form",
            "domain": [],
            "context": {"create": False},
            "target": "current",
        }

    def _find_partner_inconsistencies_for_mapping(self, mapping):
        """
        Detecta inconsistencias para un mapeo específico y devuelve una lista de valores.
        Esta es la lógica central de detección.
        """
        domain = [
            ("reconciled", "=", False),
            ("move_id.state", "=", "posted"),
            ("account_id.account_type", "in", ["liability_payable", "asset_receivable"]),
            ("amount_residual", "!=", 0),
        ]
        _logger.info(f"  Dominio de búsqueda de apuntes: {domain}")
        all_lines = self.env["account.move.line"].search(domain)
        _logger.info(f"  Encontrados {len(all_lines)} apuntes para el mapeo que cumplen el dominio.")

        if not all_lines:
            return []

        groups = self._group_lines_by_reference(all_lines, mapping)
        _logger.info(f"  Agrupados en {len(groups)} grupos por referencia.")

        inconsistencies_vals = []
        for ref_value, lines in groups.items():
            if len(lines) < 2:
                continue

            partners = lines.mapped("partner_id")
            if len(partners) <= 1:
                continue

            # --- LOG MEJORADO ---
            _logger.info(f"  [INCONSISTENCIA DETECTADA] Ref: '{ref_value}'")
            _logger.info(f"    Proveedores involucrados: {partners.mapped('name')}")
            for line in lines:
                _logger.info(f"    -> Apunte: {line.id}, Proveedor: {line.partner_id.name}, Saldo: {line.balance}, Tipo Mov: {line.move_id.move_type}")
            # --- FIN LOG MEJORADO ---

            # --- Lógica v5: Mostrar TODAS las inconsistencias ---
            anchor_line = lines[0]
            anchor_partner = anchor_line.partner_id

            # Iterar sobre todas las demás líneas para encontrar conflictos con el ancla
            for other_line in lines:
                if other_line.id == anchor_line.id:
                    continue

                if other_line.partner_id and other_line.partner_id != anchor_partner:
                    # Se encontró una línea con un proveedor diferente. Se crea un registro.
                    vals = {
                        "referencia_comun": ref_value,
                        "pago_line_id": other_line.id,
                        "factura_line_id": anchor_line.id,
                        "mapping_id": mapping.id,
                        "tipo_problema": "Discrepancia de Proveedor",
                    }
                    inconsistencies_vals.append(vals)
        
        return inconsistencies_vals

    def _group_lines_by_reference(self, lines, mapping):
        """
        Agrupar líneas de apuntes por el valor de referencia del mapeo

        :param lines: recordset de account.move.line
        :param mapping: reconcile.field.mapping
        :return: dict {ref_value: recordset de lines}
        """
        groups = {}

        for line in lines:
            # Obtener el valor de referencia para esta línea
            ref_value = self._get_reference_value_for_line(line, mapping)

            if not ref_value:
                continue

            if ref_value not in groups:
                groups[ref_value] = self.env["account.move.line"].browse()

            groups[ref_value] |= line

        return groups

    def _get_reference_value_for_line(self, line, mapping):
        """
        Obtiene dinámicamente el valor de referencia para una línea, basándose
        estrictamente en los campos definidos en el mapeo.
        """
        _logger.info(f"    [Extracción Dinámica] Procesando línea {line.id} con mapeo '{mapping.name}'...")

        # Lista de posibles ubicaciones para encontrar el valor, usando los campos del mapeo.
        # Se verifica la existencia del atributo antes de intentar acceder.

        # 1. Directamente en la línea (común para 'target_field_name')
        if hasattr(line, mapping.target_field_name):
            value = line[mapping.target_field_name]
            if value:
                value = getattr(value, 'name', value) # Obtiene .name si es un m2o, si no, el valor mismo
                _logger.info(f"      -> Valor encontrado en 'line.{mapping.target_field_name}': {value}")
                return str(value)

        # 2. Directamente en el asiento contable de la línea (común para campos en 'account.move')
        if hasattr(line.move_id, mapping.source_field_name):
            value = line.move_id[mapping.source_field_name]
            if value:
                value = getattr(value, 'name', value)
                _logger.info(f"      -> Valor encontrado en 'move_id.{mapping.source_field_name}': {value}")
                return str(value)

        # 3. A través de la relación a Órdenes de Venta (si el mapeo lo especifica)
        if mapping.source_model == "sale.order" and line.move_id.invoice_line_ids:
            for inv_line in line.move_id.invoice_line_ids.filtered(lambda l: not l.display_type):
                for sale_line in inv_line.sale_line_ids:
                    if sale_line.order_id and hasattr(sale_line.order_id, mapping.source_field_name):
                        value = sale_line.order_id[mapping.source_field_name]
                        if value:
                            value = getattr(value, 'name', value)
                            _logger.info(f"      -> Valor encontrado vía SO en '{mapping.source_field_name}': {value}")
                            return str(value)

        # 4. A través de la relación a Órdenes de Compra (si el mapeo lo especifica)
        if mapping.source_model == "purchase.order" and line.move_id.invoice_line_ids:
            for inv_line in line.move_id.invoice_line_ids.filtered(lambda l: not l.display_type):
                if inv_line.purchase_line_id and hasattr(inv_line.purchase_line_id.order_id, mapping.source_field_name):
                    value = inv_line.purchase_line_id.order_id[mapping.source_field_name]
                    if value:
                        value = getattr(value, 'name', value)
                        _logger.info(f"      -> Valor encontrado vía PO en '{mapping.source_field_name}': {value}")
                        return str(value)
        
        _logger.debug(f"      -> No se encontró valor para la línea {line.id} usando el mapeo '{mapping.name}'. La línea será ignorada en este agrupamiento.")
        return False # No hay fallback. Si el mapeo no arroja un valor, no se puede agrupar.

    def action_correct_partner_on_payments(self):
        """
        Corregir el proveedor del pago para que coincida con el de la factura

        Esta acción se ejecuta desde el menú "Acción" en la vista de árbol
        """
        if not self:
            raise UserError(_("No hay registros seleccionados."))

        corrected_count = 0
        errors = []

        _logger.info(f"Corrigiendo proveedores en {len(self)} registros...")

        for record in self:
            try:
                # Validar que tengamos los datos necesarios
                if not record.pago_line_id or not record.factura_line_id:
                    errors.append(f"Ref {record.referencia_comun}: Datos incompletos")
                    continue

                if not record.proveedor_factura_id:
                    errors.append(f"Ref {record.referencia_comun}: No hay proveedor en factura")
                    continue

                # Actualizar el proveedor del pago
                old_partner = record.proveedor_pago_id.name
                new_partner = record.proveedor_factura_id.name

                # Actualizar el apunte del pago
                record.pago_line_id.write({
                    "partner_id": record.proveedor_factura_id.id,
                })

                # Si el pago tiene un asiento completo, actualizar todas las líneas
                if record.pago_move_id:
                    record.pago_move_id.line_ids.write({
                        "partner_id": record.proveedor_factura_id.id,
                    })

                corrected_count += 1
                _logger.info(f"  ✓ Ref {record.referencia_comun}: {old_partner} → {new_partner}")

            except Exception as e:
                error_msg = f"Ref {record.referencia_comun}: {str(e)}"
                errors.append(error_msg)
                _logger.error(f"  ✗ {error_msg}")

        # Mensaje de resultado
        message = f"Se corrigieron {corrected_count} proveedores."
        if errors:
            message += f"\n\nErrores ({len(errors)}):\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                message += f"\n... y {len(errors) - 5} errores más."

        # Eliminar los registros corregidos de la vista
        self.unlink()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Corrección Completada",
                "message": message,
                "type": "success" if corrected_count > 0 else "warning",
                "sticky": True,
            },
        }
