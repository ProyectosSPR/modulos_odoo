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
        Detecta inconsistencias para un mapeo específico, siguiendo un flujo "referencia por referencia".
        Es resiliente a campos mal configurados en el mapeo.
        """
        _logger.info(f"Procesando mapeo '{mapping.name}' con flujo 'referencia por referencia'")

        source_field = mapping.source_field_name
        target_field = mapping.target_field_name
        source_refs = set()
        target_refs = set()

        # 1. Obtener referencias únicas del ORIGEN, con manejo de errores.
        try:
            if mapping.source_model and source_field:
                source_records = self.env[mapping.source_model].search([(source_field, '!=', False)])
                source_refs = set(source_records.mapped(source_field))
                _logger.info(f"  OK: Encontradas {len(source_refs)} referencias únicas desde '{mapping.source_model}.{source_field}'.")
        except Exception as e:
            _logger.warning(f"  AVISO: No se pudieron obtener referencias desde el origen del '{mapping.source_model}.{source_field}'. Causa: {e}")

        # 2. Obtener referencias únicas del DESTINO (account.move.line), con manejo de errores.
        try:
            if target_field:
                target_lines = self.env['account.move.line'].search([(target_field, '!=', False)])
                target_refs = set(target_lines.mapped(target_field))
                _logger.info(f"  OK: Encontradas {len(target_refs)} referencias únicas desde 'account.move.line.{target_field}'.")
        except Exception as e:
            _logger.warning(f"  AVISO: No se pudieron obtener referencias desde el destino 'account.move.line.{target_field}'. Causa: {e}")
        
        # 3. Combinar todas las referencias encontradas.
        unique_refs = list(source_refs | target_refs)
        _logger.info(f"  Total de {len(unique_refs)} referencias únicas a procesar.")

        if not unique_refs:
            return []

        inconsistencies_vals = []

        # 4. Iterar sobre cada referencia única.
        for ref_value in unique_refs:
            invoice_lines = self.env['account.move.line']
            payment_lines = self.env['account.move.line']
            
            # --- Encontrar apuntes de FACTURA ---
            try:
                source_records = mapping._get_source_records(ref_value)
                invoices = mapping._get_invoices_from_source(source_records)
                invoice_lines = mapping._get_receivable_payable_lines(invoices)
            except Exception as e:
                _logger.error(f"  Error al buscar líneas de factura para la referencia '{ref_value}': {e}")

            # --- Encontrar apuntes de PAGO ---
            payment_lines = self.env['account.move.line'] # Inicializar como recordset vacío
            try:
                # 1. Buscar en el modelo de destino configurado en el mapeo (ej: account.move).
                if mapping.target_model and target_field:
                    target_records = self.env[mapping.target_model].search([(target_field, '=', ref_value)])
                    
                    if target_records:
                        # 2. De los registros encontrados, obtener TODAS sus líneas.
                        #    Asumimos que el modelo destino tiene un campo 'line_ids'.
                        all_lines_from_target = target_records.mapped('line_ids')

                        # 3. Filtrar esas líneas para quedarnos solo con las relevantes.
                        payment_lines = all_lines_from_target.filtered(
                            lambda line: line.parent_state == 'posted' and \
                                         line.account_id.account_type in ('liability_payable', 'asset_receivable')
                        )
            except Exception as e:
                 _logger.error(f"  Error al buscar líneas de pago para la referencia '{ref_value}' (campo: {target_field}): {e}")

            all_lines_for_ref = (invoice_lines | payment_lines)

            if len(all_lines_for_ref) < 2:
                continue

            # 5. Analizar el "expediente".
            partners = all_lines_for_ref.mapped('partner_id')
            if len(partners) > 1:
                _logger.info(f"  [INCONSISTENCIA DETECTADA] Ref: '{ref_value}'")
                _logger.info(f"    Proveedores involucrados: {partners.mapped('name')}")

                anchor_line = all_lines_for_ref[0]
                for other_line in all_lines_for_ref[1:]:
                    if other_line.partner_id != anchor_line.partner_id:
                        vals = {
                            'referencia_comun': str(ref_value),
                            'pago_line_id': other_line.id,
                            'factura_line_id': anchor_line.id,
                            'mapping_id': mapping.id,
                            'tipo_problema': 'Discrepancia de Proveedor',
                        }
                        inconsistencies_vals.append(vals)
        
        return inconsistencies_vals



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
