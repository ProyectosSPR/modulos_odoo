# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PartnerInconsistency(models.Model):
    _name = "partner.inconsistency"
    _description = "Partner Inconsistency"
    _order = "create_date desc, referencia_comun, id"

    referencia_comun = fields.Char(string="Referencia Común", readonly=True, index=True)
    tipo_problema = fields.Char(string="Tipo de Problema", readonly=True, default="Discrepancia de Partner")
    pago_line_id = fields.Many2one("account.move.line", string="Apunte 1", readonly=True, ondelete='set null')
    factura_line_id = fields.Many2one("account.move.line", string="Apunte 2", readonly=True, ondelete='set null')
    proveedor_pago_id = fields.Many2one("res.partner", string="Partner en Apunte 1", related="pago_line_id.partner_id", readonly=True, store=True)
    proveedor_factura_id = fields.Many2one("res.partner", string="Partner en Apunte 2", related="factura_line_id.partner_id", readonly=True, store=True)
    monto_pago = fields.Monetary(string="Saldo Apunte 1", related="pago_line_id.amount_residual", readonly=True)
    monto_factura = fields.Monetary(string="Saldo Apunte 2", related="factura_line_id.amount_residual", readonly=True)
    currency_id = fields.Many2one("res.currency", related="pago_line_id.currency_id", readonly=True)
    mapping_id = fields.Many2one("reconcile.field.mapping", string="Mapeo Utilizado", readonly=True, ondelete='cascade')

    # Campos de estado y auditoría
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('corrected', 'Corregido'),
        ('cancelled', 'Cancelado')
    ], string="Estado", default='pending', required=True, index=True, tracking=True)

    corrected_date = fields.Datetime(string="Fecha de Corrección/Cancelación", readonly=True)
    corrected_user_id = fields.Many2one("res.users", string="Usuario que Procesó", readonly=True)
    partner_original_id = fields.Many2one("res.partner", string="Partner Original del Pago", readonly=True)
    partner_corregido_id = fields.Many2one("res.partner", string="Partner Corregido", readonly=True)
    notas = fields.Text(string="Notas/Razón")

    # Nuevos campos para identificar tipo de movimiento (cargo/abono)
    tipo_apunte_1 = fields.Selection([
        ('debit', 'Cargo (Débito)'),
        ('credit', 'Abono (Crédito)')
    ], string="Tipo Apunte 1", compute="_compute_tipos_apuntes", store=True, readonly=True)

    tipo_apunte_2 = fields.Selection([
        ('debit', 'Cargo (Débito)'),
        ('credit', 'Abono (Crédito)')
    ], string="Tipo Apunte 2", compute="_compute_tipos_apuntes", store=True, readonly=True)

    debito_apunte_1 = fields.Monetary(string="Débito Apunte 1", related="pago_line_id.debit", readonly=True)
    credito_apunte_1 = fields.Monetary(string="Crédito Apunte 1", related="pago_line_id.credit", readonly=True)
    debito_apunte_2 = fields.Monetary(string="Débito Apunte 2", related="factura_line_id.debit", readonly=True)
    credito_apunte_2 = fields.Monetary(string="Crédito Apunte 2", related="factura_line_id.credit", readonly=True)

    @api.depends('pago_line_id', 'factura_line_id')
    def _compute_tipos_apuntes(self):
        """Determinar si cada apunte es cargo (débito) o abono (crédito)"""
        for record in self:
            if record.pago_line_id:
                record.tipo_apunte_1 = 'debit' if record.pago_line_id.debit > 0 else 'credit'
            else:
                record.tipo_apunte_1 = False

            if record.factura_line_id:
                record.tipo_apunte_2 = 'debit' if record.factura_line_id.debit > 0 else 'credit'
            else:
                record.tipo_apunte_2 = False

    @api.model
    def find_inconsistencies(self, account_ids, mapping_id, date_from=None, date_to=None, include_reconciled=False):
        _logger.info("========== INICIO DE BÚSQUEDA DE INCONSISTENCIAS ==========")

        mapping = self.env["reconcile.field.mapping"].browse(mapping_id)
        if not mapping:
            raise UserError(_("No se encontró el mapeo de campos seleccionado."))

        # Dominio base para los APUNTES CONTABLES, que se usará DENTRO del bucle.
        line_domain = [
            ('account_id', 'in', account_ids),
            ('parent_state', '=', 'posted'),  # Solo facturas/pagos publicados
        ]

        # Filtros de fecha - MUY IMPORTANTE para rendimiento
        if date_from:
            line_domain.append(('date', '>=', date_from))
        if date_to:
            line_domain.append(('date', '<=', date_to))

        # Filtro de conciliación
        if not include_reconciled:
            # Solo apuntes NO totalmente conciliados (con saldo pendiente)
            line_domain.append(('amount_residual', '!=', 0))
            line_domain.append(('reconciled', '=', False))

        # Filtro adicional: solo cuentas por cobrar/pagar
        line_domain.append(('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']))

        _logger.info(f"Filtros: Cuentas: {account_ids}, Mapeo: {mapping.name}, Fechas: {date_from}-{date_to}, Incluir Conciliados: {include_reconciled}")

        inconsistency_vals = self._find_partner_inconsistencies_for_mapping(mapping, line_domain)

        # Crear solo las inconsistencias nuevas (evitar duplicados)
        nuevas_creadas = 0
        for vals in inconsistency_vals:
            # Verificar si ya existe esta inconsistencia PENDIENTE
            existing = self.search([
                ('referencia_comun', '=', vals['referencia_comun']),
                ('pago_line_id', '=', vals['pago_line_id']),
                ('factura_line_id', '=', vals['factura_line_id']),
                ('mapping_id', '=', vals['mapping_id']),
                ('state', '=', 'pending')  # Solo verificar las pendientes
            ], limit=1)

            if not existing:
                self.create(vals)
                nuevas_creadas += 1
            else:
                _logger.info(f"Inconsistencia duplicada omitida: {vals['referencia_comun']}")

        _logger.info(f"========== FIN DE BÚSQUEDA: {nuevas_creadas} nuevas inconsistencias creadas de {len(inconsistency_vals)} encontradas ==========")

        # Devolver la acción para mostrar SOLO las inconsistencias PENDIENTES
        action = self.env['ir.actions.actions']._for_xml_id('account_reconcile_custom_fields.action_partner_inconsistency_result')
        action['domain'] = [('state', '=', 'pending')]
        action['context'] = {'search_default_pending': 1}
        return action

    def _find_partner_inconsistencies_for_mapping(self, mapping, line_domain):
        _logger.info(f"Iniciando búsqueda de referencias para el mapeo '{mapping.name}'.")

        source_field = mapping.source_field_name
        target_field = mapping.target_field_name

        # OPTIMIZACIÓN: Primero buscar apuntes que cumplan los filtros (fecha, cuenta, etc.)
        # Y de ahí extraer las referencias, en lugar de buscar todas las referencias del sistema
        _logger.info(f"Buscando apuntes contables que cumplan filtros: {line_domain}")

        # Buscar los apuntes que cumplen los criterios (line_domain ya incluye todos los filtros necesarios)
        candidate_lines = self.env['account.move.line'].search(line_domain, limit=10000)  # Límite de seguridad
        _logger.info(f"  -> Encontrados {len(candidate_lines)} apuntes contables candidatos")

        if not candidate_lines:
            _logger.warning("No se encontraron apuntes que cumplan los criterios de búsqueda")
            return []

        # Extraer referencias únicas de estos apuntes USANDO LOS CAMPOS DEL MAPPING
        unique_refs = set()

        # Estrategia: Buscar en los modelos origen y destino del mapping
        _logger.info(f"  Extrayendo referencias usando mapping: {mapping.source_model}.{source_field} vs {mapping.target_model}.{target_field}")

        # 1. Buscar en el modelo TARGET (normalmente account.payment)
        if mapping.target_model == 'account.payment':
            # Obtener payments de los moves de los apuntes candidatos
            payment_ids = []
            for line in candidate_lines:
                # Un payment tiene un move_id, buscar el payment que generó este move
                payments = self.env['account.payment'].search([('move_id', '=', line.move_id.id)])
                payment_ids.extend(payments.ids)

            if payment_ids:
                payments = self.env['account.payment'].browse(payment_ids)
                for payment in payments:
                    if hasattr(payment, target_field):
                        value = getattr(payment, target_field, None)
                        if value:
                            unique_refs.add(str(value).strip())
                            _logger.info(f"    -> Agregada ref de payment.{target_field}: {value}")

        # 2. Buscar en el modelo SOURCE (normalmente sale.order o purchase.order)
        for line in candidate_lines:
            move = line.move_id

            if mapping.source_model == 'account.move':
                if hasattr(move, source_field):
                    value = getattr(move, source_field, None)
                    if value:
                        unique_refs.add(str(value).strip())
                        _logger.info(f"    -> Agregada ref de move.{source_field}: {value}")

            elif mapping.source_model == 'sale.order':
                # Buscar órdenes de venta relacionadas con esta factura
                for inv_line in move.invoice_line_ids:
                    for sale_line in inv_line.sale_line_ids:
                        if sale_line.order_id:
                            value = getattr(sale_line.order_id, source_field, None)
                            if value:
                                unique_refs.add(str(value).strip())
                                _logger.info(f"    -> Agregada ref de sale_order.{source_field}: {value}")

            elif mapping.source_model == 'purchase.order':
                # Buscar órdenes de compra relacionadas
                for inv_line in move.invoice_line_ids:
                    if inv_line.purchase_line_id and inv_line.purchase_line_id.order_id:
                        value = getattr(inv_line.purchase_line_id.order_id, source_field, None)
                        if value:
                            unique_refs.add(str(value).strip())
                            _logger.info(f"    -> Agregada ref de purchase_order.{source_field}: {value}")

        unique_refs = list(unique_refs)
        _logger.info(f"Total de {len(unique_refs)} referencias únicas extraídas de los apuntes filtrados.")
        if not unique_refs:
            return []

        inconsistencies_vals = []
        # 2. Iterar sobre cada referencia
        # IMPORTANTE: Al buscar apuntes para cada referencia, NO aplicamos filtro de fechas
        # porque queremos encontrar TODOS los apuntes con esa referencia, no solo los del rango
        for ref_value in unique_refs:
            _logger.info(f"  Procesando referencia: {ref_value}")

            # Buscar en el modelo SOURCE usando el campo source_field
            source_records = self.env[mapping.source_model].search([
                (source_field, '=', ref_value)
            ])
            _logger.info(f"    -> Encontrados {len(source_records)} registros en {mapping.source_model}")

            # Buscar en el modelo TARGET usando el campo target_field
            target_records = self.env[mapping.target_model].search([
                (target_field, '=', ref_value)
            ])
            _logger.info(f"    -> Encontrados {len(target_records)} registros en {mapping.target_model}")

            # Ahora obtener los apuntes contables de ambos lados
            all_lines_for_ref = self.env['account.move.line'].browse()

            # Obtener líneas de las facturas del SOURCE
            if mapping.source_model in ['sale.order', 'purchase.order']:
                invoices = mapping._get_invoices_from_source(source_records)
                source_lines = mapping._get_receivable_payable_lines(invoices)
                _logger.info(f"    -> {len(source_lines)} líneas de facturas del source")
                all_lines_for_ref |= source_lines
            elif mapping.source_model == 'account.move':
                source_lines = mapping._get_receivable_payable_lines(source_records)
                _logger.info(f"    -> {len(source_lines)} líneas del source")
                all_lines_for_ref |= source_lines

            # Obtener líneas del TARGET (payments)
            if mapping.target_model == 'account.payment':
                for payment in target_records:
                    if payment.move_id:
                        payment_lines = payment.move_id.line_ids.filtered(
                            lambda l: l.account_id.account_type in ['asset_receivable', 'liability_payable']
                        )
                        _logger.info(f"    -> {len(payment_lines)} líneas del payment {payment.id}")
                        all_lines_for_ref |= payment_lines

            # Filtrar por las cuentas seleccionadas en el wizard
            account_ids = []
            for item in line_domain:
                if isinstance(item, tuple) and item[0] == 'account_id' and item[1] == 'in':
                    account_ids = item[2]
                    break

            if account_ids:
                all_lines_for_ref = all_lines_for_ref.filtered(lambda l: l.account_id.id in account_ids)

            lines_for_ref = all_lines_for_ref
            _logger.info(f"    -> Total de {len(lines_for_ref)} líneas para analizar")
            
            if len(lines_for_ref) < 2:
                continue

            # 3. Analizar el grupo de apuntes para esta referencia
            # IMPORTANTE: Solo detectar parejas FACTURA-PAGO, no PAGO-PAGO ni FACTURA-FACTURA

            # Separar FACTURAS de PAGOS por move_type
            invoice_lines = lines_for_ref.filtered(
                lambda l: l.move_id.move_type in ('out_invoice', 'in_invoice')
            )

            # Para los pagos, verificar que vengan de un account.payment real
            payment_lines = self.env['account.move.line'].browse()
            for line in lines_for_ref:
                # Verificar si este move viene de un payment
                payment = self.env['account.payment'].search([('move_id', '=', line.move_id.id)], limit=1)
                if payment:
                    payment_lines |= line

            _logger.info(f"    -> {len(invoice_lines)} líneas de facturas, {len(payment_lines)} líneas de pagos")

            # Solo procesar si hay tanto facturas como pagos
            if not invoice_lines or not payment_lines:
                _logger.info(f"    -> Saltando ref '{ref_value}': no hay parejas factura-pago")
                continue

            # Ahora emparejar facturas con pagos, validando:
            # 1. Que tengan partners diferentes
            # 2. Que el tipo de pago coincida con el tipo de factura
            for invoice_line in invoice_lines:
                invoice_type = invoice_line.move_id.move_type

                for payment_line in payment_lines:
                    # Obtener el payment para verificar el payment_type
                    payment = self.env['account.payment'].search([('move_id', '=', payment_line.move_id.id)], limit=1)
                    if not payment:
                        continue

                    # Validar que el tipo de pago coincida con el tipo de factura
                    # out_invoice (factura de cliente) -> debe emparejar con inbound (pago recibido)
                    # in_invoice (factura de proveedor) -> debe emparejar con outbound (pago enviado)
                    valid_pairing = False
                    if invoice_type == 'out_invoice' and payment.payment_type == 'inbound':
                        valid_pairing = True
                    elif invoice_type == 'in_invoice' and payment.payment_type == 'outbound':
                        valid_pairing = True

                    if not valid_pairing:
                        _logger.info(
                            f"    -> Saltando pareja: factura {invoice_type} no empareja con pago {payment.payment_type}"
                        )
                        continue

                    # Verificar si tienen partners diferentes
                    if invoice_line.partner_id != payment_line.partner_id:
                        _logger.info(
                            f"  [INCONSISTENCIA DETECTADA] Ref: '{ref_value}', "
                            f"Factura ({invoice_type}): {invoice_line.move_id.name} - Partner: {invoice_line.partner_id.name}, "
                            f"Pago ({payment.payment_type}): {payment_line.move_id.name} - Partner: {payment_line.partner_id.name}"
                        )

                        # Determinar cuál va en pago_line_id y cuál en factura_line_id
                        # Siempre ponemos el PAGO en pago_line_id y la FACTURA en factura_line_id
                        inconsistencies_vals.append({
                            'referencia_comun': str(ref_value),
                            'pago_line_id': payment_line.id,
                            'factura_line_id': invoice_line.id,
                            'mapping_id': mapping.id,
                        })
        return inconsistencies_vals

    def action_correct_partner(self):
        """
        Abrir wizard para seleccionar qué partner usar en el PAGO
        IMPORTANTE: SIEMPRE se corrige el PAGO, nunca la factura
        NOTA: Con la nueva lógica, pago_line_id siempre es el PAGO y factura_line_id siempre es la FACTURA
        """
        self.ensure_one()

        if self.state != 'pending':
            raise UserError(_("Solo se pueden corregir inconsistencias en estado 'Pendiente'."))

        if not self.pago_line_id or not self.factura_line_id:
            raise UserError(_("Ambos apuntes deben estar presentes para la corrección."))

        # Con la nueva lógica, pago_line_id siempre contiene el PAGO y factura_line_id la FACTURA
        payment_line = self.pago_line_id
        invoice_line = self.factura_line_id

        # Abrir wizard de corrección
        return {
            'name': _('Corregir Partner del Pago'),
            'type': 'ir.actions.act_window',
            'res_model': 'partner.correction.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_inconsistency_id': self.id,
                'default_payment_line_id': payment_line.id,
                'default_invoice_line_id': invoice_line.id,
                'default_current_partner_id': payment_line.partner_id.id,
                'default_suggested_partner_id': invoice_line.partner_id.id,
            },
        }

    def action_mark_cancelled(self):
        """
        Marcar inconsistencia como cancelada (el contador decide no corregir)
        """
        for record in self:
            if record.state != 'pending':
                raise UserError(_("Solo se pueden cancelar inconsistencias en estado 'Pendiente'."))

        # Abrir wizard para pedir notas
        return {
            'name': _('Cancelar Inconsistencia'),
            'type': 'ir.actions.act_window',
            'res_model': 'partner.inconsistency.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_inconsistency_ids': self.ids,
            },
        }

    def mark_as_cancelled(self, notas=None):
        """
        Marcar como cancelado con notas
        """
        for record in self:
            record.write({
                'state': 'cancelled',
                'corrected_date': fields.Datetime.now(),
                'corrected_user_id': self.env.user.id,
                'notas': notas or '',
            })
        _logger.info(f"Inconsistencias {self.ids} marcadas como canceladas por {self.env.user.name}")

    def mark_as_corrected(self, partner_original_id, partner_corregido_id, notas=None):
        """
        Marcar como corregido después de aplicar la corrección
        """
        self.ensure_one()
        self.write({
            'state': 'corrected',
            'corrected_date': fields.Datetime.now(),
            'corrected_user_id': self.env.user.id,
            'partner_original_id': partner_original_id,
            'partner_corregido_id': partner_corregido_id,
            'notas': notas or '',
        })
        _logger.info(f"Inconsistencia {self.id} marcada como corregida por {self.env.user.name}")
