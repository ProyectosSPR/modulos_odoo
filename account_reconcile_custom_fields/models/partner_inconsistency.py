# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PartnerInconsistency(models.TransientModel):
    _name = "partner.inconsistency"
    _description = "Partner Inconsistency"
    _order = "referencia_comun, id"

    referencia_comun = fields.Char(string="Referencia Común", readonly=True)
    tipo_problema = fields.Char(string="Tipo de Problema", readonly=True, default="Discrepancia de Partner")
    pago_line_id = fields.Many2one("account.move.line", string="Apunte 1", readonly=True)
    factura_line_id = fields.Many2one("account.move.line", string="Apunte 2", readonly=True)
    proveedor_pago_id = fields.Many2one("res.partner", string="Partner en Apunte 1", related="pago_line_id.partner_id", readonly=True)
    proveedor_factura_id = fields.Many2one("res.partner", string="Partner en Apunte 2", related="factura_line_id.partner_id", readonly=True)
    monto_pago = fields.Monetary(string="Saldo Apunte 1", related="pago_line_id.amount_residual", readonly=True)
    monto_factura = fields.Monetary(string="Saldo Apunte 2", related="factura_line_id.amount_residual", readonly=True)
    currency_id = fields.Many2one("res.currency", related="pago_line_id.currency_id", readonly=True)
    mapping_id = fields.Many2one("reconcile.field.mapping", string="Mapeo Utilizado", readonly=True)

    @api.model
    def find_inconsistencies(self, account_ids, mapping_id, date_from=None, date_to=None, include_reconciled=False):
        _logger.info("========== INICIO DE BÚSQUEDA DE INCONSISTENCIAS ==========")
        self.search([]).unlink()

        mapping = self.env["reconcile.field.mapping"].browse(mapping_id)
        if not mapping:
            raise UserError(_("No se encontró el mapeo de campos seleccionado."))

        # Dominio base para los A PUNTES CONTABLES, que se usará DENTRO del bucle.
        line_domain = [('account_id', 'in', account_ids)]
        if date_from:
            line_domain.append(('date', '>=', date_from))
        if date_to:
            line_domain.append(('date', '<=', date_to))
        if not include_reconciled:
            line_domain.append(('amount_residual', '!=', 0))
        else:
            line_domain.append(('parent_state', '=', 'posted'))
        
        _logger.info(f"Filtros: Cuentas: {account_ids}, Mapeo: {mapping.name}, Fechas: {date_from}-{date_to}, Incluir Conciliados: {include_reconciled}")

        inconsistency_vals = self._find_partner_inconsistencies_for_mapping(mapping, line_domain)

        if inconsistency_vals:
            self.create(inconsistency_vals)
        
        _logger.info(f"========== FIN DE BÚSQUEDA: {len(inconsistency_vals)} inconsistencias encontradas ==========")
        
        # Devolver la acción para mostrar los resultados en la vista de este modelo
        action = self.env['ir.actions.actions']._for_xml_id('account_reconcile_custom_fields.action_partner_inconsistency_result')
        return action

    def _find_partner_inconsistencies_for_mapping(self, mapping, line_domain):
        _logger.info(f"Iniciando búsqueda de referencias para el mapeo '{mapping.name}'.")

        source_field = mapping.source_field_name
        target_field = mapping.target_field_name
        source_refs, target_refs = set(), set()

        # 1. Obtener TODAS las referencias únicas, sin filtros de dominio.
        try:
            _logger.info(f"Buscando referencias en Origen: {mapping.source_model}.{source_field}")
            source_records = self.env[mapping.source_model].search([(source_field, '!=', False)])
            source_refs = set(source_records.mapped(source_field))
            _logger.info(f"  -> OK: Encontradas {len(source_refs)} referencias.")
        except Exception as e:
            _logger.warning(f"  -> AVISO al buscar en Origen: {e}")

        try:
            _logger.info(f"Buscando referencias en Destino: {mapping.target_model}.{target_field}")
            target_records = self.env[mapping.target_model].search([(target_field, '!=', False)])
            target_refs = set(target_records.mapped(target_field))
            _logger.info(f"  -> OK: Encontradas {len(target_refs)} referencias.")
        except Exception as e:
            _logger.warning(f"  -> AVISO al buscar en Destino: {e}")
        
        unique_refs = list(source_refs | target_refs)
        _logger.info(f"Total de {len(unique_refs)} referencias únicas a procesar.")
        if not unique_refs:
            return []

        inconsistencies_vals = []
        # 2. Iterar sobre cada referencia y APLICAR FILTROS de línea
        for ref_value in unique_refs:
            # Construir un dominio para encontrar todos los apuntes relacionados con esta referencia
            # Este dominio se aplicará al modelo account.move.line
            
            domain_for_ref = []
            # Lógica para construir el dominio de referencia cruzada
            # Usamos un OR para buscar la referencia en cualquiera de los campos mapeados
            # Esto es más flexible si los datos no son consistentes.
            if source_field and hasattr(self.env['account.move.line'], f'move_id.{source_field}'):
                 domain_for_ref.append((f'move_id.{source_field}', '=', ref_value))
            if target_field:
                 if hasattr(self.env['account.move.line'], target_field):
                     domain_for_ref.append((target_field, '=', ref_value))
                 elif hasattr(self.env['account.move.line'], f'move_id.{target_field}'):
                     domain_for_ref.append((f'move_id.{target_field}', '=', ref_value))
            
            if len(domain_for_ref) > 1:
                domain_for_ref.insert(0, '|')

            # El dominio final combina los filtros del wizard y el filtro de la referencia actual
            final_line_domain = line_domain + domain_for_ref
            
            _logger.debug(f"Buscando apuntes para Ref '{ref_value}' con dominio: {final_line_domain}")
            lines_for_ref = self.env['account.move.line'].search(final_line_domain)
            
            if len(lines_for_ref) < 2:
                continue

            # 3. Analizar el grupo de apuntes para esta referencia
            partners = lines_for_ref.mapped('partner_id')
            if len(partners) > 1:
                _logger.info(f"  [INCONSISTENCIA DETECTADA] Ref: '{ref_value}', Partners: {partners.mapped('name')}")
                anchor_line = lines_for_ref[0]
                for other_line in lines_for_ref[1:]:
                    if other_line.partner_id != anchor_line.partner_id:
                        inconsistencies_vals.append({
                            'referencia_comun': str(ref_value),
                            'pago_line_id': other_line.id,
                            'factura_line_id': anchor_line.id,
                            'mapping_id': mapping.id,
                        })
        return inconsistencies_vals

    def action_correct_partner(self):
        # Esta acción es un ejemplo y puede necesitar ajustes
        if not self.pago_line_id or not self.factura_line_id:
            raise UserError(_("Ambos apuntes deben estar presentes para la corrección."))

        correct_partner_id = self.factura_line_id.partner_id.id
        line_to_correct = self.pago_line_id
        
        _logger.info(f"Corrigiendo Apunte ID {line_to_correct.id}. Cambiando partner a {self.factura_line_id.partner_id.name}")

        move_to_correct = line_to_correct.move_id
        if move_to_correct.state == 'posted':
            move_to_correct.button_draft()
            move_to_correct.line_ids.with_context(check_move_validity=False).partner_id = correct_partner_id
            move_to_correct.action_post()
        else:
            move_to_correct.line_ids.with_context(check_move_validity=False).partner_id = correct_partner_id

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
