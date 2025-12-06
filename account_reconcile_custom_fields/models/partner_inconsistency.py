# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PartnerInconsistency(models.TransientModel):
    _name = "partner.inconsistency"
    _description = "Partner Inconsistency Detection"
    _order = "referencia_comun, id"

    referencia_comun = fields.Char(string="Referencia Común", readonly=True)
    tipo_problema = fields.Char(string="Tipo de Problema", readonly=True)
    pago_line_id = fields.Many2one("account.move.line", string="Apunte 1", readonly=True)
    factura_line_id = fields.Many2one("account.move.line", string="Apunte 2", readonly=True)
    proveedor_pago_id = fields.Many2one("res.partner", string="Partner en Apunte 1", related="pago_line_id.partner_id", readonly=True)
    proveedor_factura_id = fields.Many2one("res.partner", string="Partner en Apunte 2", related="factura_line_id.partner_id", readonly=True)
    monto_pago = fields.Monetary(string="Saldo Apunte 1", related="pago_line_id.amount_residual", readonly=True)
    monto_factura = fields.Monetary(string="Saldo Apunte 2", related="factura_line_id.amount_residual", readonly=True)
    currency_id = fields.Many2one("res.currency", related="pago_line_id.currency_id", readonly=True)
    company_id = fields.Many2one("res.company", related="pago_line_id.company_id", readonly=True)
    mapping_id = fields.Many2one("reconcile.field.mapping", string="Mapeo Utilizado", readonly=True)

    @api.model
    def find_inconsistencies(self, account_ids, mapping_id, date_from=None, date_to=None, include_reconciled=False):
        _logger.info("========== INICIO DE BÚSQUEDA DE INCONSISTENCIAS ==========")
        self.search([]).unlink()

        mapping = self.env["reconcile.field.mapping"].browse(mapping_id)
        if not mapping:
            raise UserError(_("No se encontró el mapeo de campos seleccionado."))

        # Construir el dominio base con los filtros del wizard
        domain = [('account_id', 'in', account_ids)]
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        if not include_reconciled:
            domain.append(('amount_residual', '!=', 0))
        
        _logger.info(f"Filtros aplicados: Cuentas: {account_ids}, Mapeo: {mapping.name}, Rango Fechas: {date_from}-{date_to}, Incluir Conciliados: {include_reconciled}")

        inconsistency_vals = self._find_partner_inconsistencies_for_mapping(mapping, domain)

        if inconsistency_vals:
            self.create(inconsistency_vals)
        
        _logger.info(f"Total de inconsistencias encontradas y creadas: {len(inconsistency_vals)}")

        return {
            "type": "ir.actions.act_window",
            "name": "Inconsistencias de Proveedores",
            "res_model": "partner.inconsistency",
            "view_mode": "tree,form",
            "domain": [],
            "context": {"create": False},
        }

    def _find_partner_inconsistencies_for_mapping(self, mapping, base_domain):
        _logger.info(f"Procesando mapeo '{mapping.name}' con dominio base: {base_domain}")

        source_field = mapping.source_field_name
        target_field = mapping.target_field_name
        
        # 1. Obtener referencias únicas del ORIGEN y DESTINO, ya pre-filtradas por el dominio base
        source_refs, target_refs = set(), set()
        
        try:
            source_domain = base_domain + [(source_field, '!=', False)]
            source_records = self.env[mapping.source_model].search(source_domain)
            source_refs = set(source_records.mapped(source_field))
            _logger.info(f"  OK: Encontradas {len(source_refs)} refs desde Origen '{mapping.source_model}.{source_field}'.")
        except Exception: # Si el source_field no está en el modelo, etc.
            pass

        try:
            target_domain = base_domain + [(target_field, '!=', False)]
            target_lines = self.env['account.move.line'].search(target_domain)
            target_refs = set(target_lines.mapped(target_field))
            _logger.info(f"  OK: Encontradas {len(target_refs)} refs desde Destino 'account.move.line.{target_field}'.")
        except Exception: # Si el target_field no está en account.move.line
            pass
        
        unique_refs = list(source_refs | target_refs)
        _logger.info(f"  Total de {len(unique_refs)} referencias únicas a procesar.")
        if not unique_refs:
            return []

        inconsistencies_vals = []
        # 2. Iterar sobre cada referencia
        for ref_value in unique_refs:
            domain_ref = [('account_id', 'in', base_domain[0][2])] # Re-añadir filtro de cuenta
            
            # Buscar todos los apuntes (facturas, pagos, etc.) para esta referencia y que pertenezcan a las cuentas seleccionadas
            ref_lines = self.env['account.move.line'].search(domain_ref + [
                '|', (source_field, '=', ref_value), (target_field, '=', ref_value)
            ])
            
            # Si en este pequeño grupo hay más de un proveedor, es una inconsistencia
            partners = ref_lines.mapped('partner_id')
            if len(partners) > 1:
                _logger.info(f"  [INCONSISTENCIA DETECTADA] Ref: '{ref_value}', Proveedores: {partners.mapped('name')}")
                anchor_line = ref_lines[0]
                for other_line in ref_lines[1:]:
                    if other_line.partner_id != anchor_line.partner_id:
                        inconsistencies_vals.append({
                            'referencia_comun': str(ref_value),
                            'pago_line_id': other_line.id,
                            'factura_line_id': anchor_line.id,
                            'mapping_id': mapping.id,
                            'tipo_problema': 'Discrepancia de Proveedor',
                        })
        return inconsistencies_vals

    def action_correct_partner(self):
        # Esta acción es un ejemplo y puede necesitar ajustes
        if not self.pago_line_id or not self.factura_line_id:
            raise UserError(_("Ambos apuntes deben estar presentes para la corrección."))

        correct_partner_id = self.factura_line_id.partner_id.id
        line_to_correct = self.pago_line_id
        
        _logger.info(f"Corrigiendo Apunte ID {line_to_correct.id}. Cambiando partner a {self.factura_line_id.partner_id.name}")

        # Corregir la línea y todo su asiento
        move_to_correct = line_to_correct.move_id
        if move_to_correct.state == 'posted':
            move_to_correct.button_draft()
            move_to_correct.line_ids.with_context(check_move_validity=False).partner_id = correct_partner_id
            move_to_correct.action_post()
        else:
            move_to_correct.line_ids.with_context(check_move_validity=False).partner_id = correct_partner_id

        # Eliminar la inconsistencia de la lista
        self.unlink()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Corrección Exitosa',
                'message': f'El asiento {move_to_correct.name} ha sido actualizado.',
                'type': 'success',
                'sticky': False,
            },
        }
