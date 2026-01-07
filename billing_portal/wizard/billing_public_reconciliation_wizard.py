# -*- coding: utf-8 -*-
"""
Wizard para conciliación masiva de facturas a Público en General.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class BillingPublicReconciliationWizard(models.TransientModel):
    _name = 'billing.public.reconciliation.wizard'
    _description = 'Conciliación Masiva de Factura Público en General'

    public_invoice_id = fields.Many2one(
        'billing.public.invoice',
        string='Factura Público en General',
        required=True,
        ondelete='cascade'
    )

    public_invoice_name = fields.Char(
        related='public_invoice_id.name',
        string='Referencia'
    )

    search_field_ids = fields.Many2many(
        'billing.reconciliation.field',
        'reconciliation_wizard_field_rel',
        'wizard_id',
        'field_id',
        string='Campos de Búsqueda',
        help='Campos de la orden a usar para buscar pagos coincidentes'
    )

    config_id = fields.Many2one(
        'billing.public.config',
        string='Configuración'
    )

    config_missing = fields.Boolean(
        string='Falta Configuración',
        default=True
    )

    # Líneas de preview/match
    line_ids = fields.One2many(
        'billing.public.reconciliation.wizard.line',
        'wizard_id',
        string='Coincidencias Encontradas'
    )

    # Totales
    total_orders = fields.Integer(
        compute='_compute_totals',
        string='Total Órdenes'
    )

    total_matched = fields.Integer(
        compute='_compute_totals',
        string='Órdenes con Pago'
    )

    total_unmatched = fields.Integer(
        compute='_compute_totals',
        string='Órdenes sin Pago'
    )

    amount_matched = fields.Monetary(
        compute='_compute_totals',
        string='Monto Coincidente',
        currency_field='currency_id'
    )

    amount_to_reconcile = fields.Monetary(
        compute='_compute_totals',
        string='Monto a Conciliar',
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        related='public_invoice_id.currency_id',
        string='Moneda'
    )

    search_done = fields.Boolean(
        string='Búsqueda Realizada',
        default=False
    )

    state = fields.Selection([
        ('search', 'Configurar Búsqueda'),
        ('preview', 'Vista Previa'),
        ('done', 'Completado'),
    ], string='Estado', default='search')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Obtener company_id del contexto si hay public_invoice_id
        public_invoice_id = res.get('public_invoice_id') or self._context.get('default_public_invoice_id')
        company_id = None
        if public_invoice_id:
            invoice = self.env['billing.public.invoice'].browse(public_invoice_id)
            if invoice.exists():
                company_id = invoice.company_id.id

        # Configuración
        config = self.env['billing.public.config'].get_config(company_id)
        if config:
            res['config_id'] = config.id
            res['config_missing'] = False
        else:
            res['config_missing'] = True

        # Campos de búsqueda por defecto
        search_fields = self.env['billing.reconciliation.field'].get_active_fields(company_id)
        if search_fields:
            res['search_field_ids'] = [(6, 0, search_fields.ids)]

        return res

    @api.depends('line_ids', 'line_ids.to_reconcile', 'line_ids.payment_id')
    def _compute_totals(self):
        for wizard in self:
            lines = wizard.line_ids
            wizard.total_orders = len(lines)
            wizard.total_matched = len(lines.filtered(lambda l: l.payment_id))
            wizard.total_unmatched = len(lines.filtered(lambda l: not l.payment_id))
            wizard.amount_matched = sum(lines.filtered(lambda l: l.payment_id).mapped('payment_amount'))
            wizard.amount_to_reconcile = sum(
                lines.filtered(lambda l: l.to_reconcile and l.payment_id).mapped('amount_to_reconcile')
            )

    def action_search_payments(self):
        """Busca pagos coincidentes para cada orden."""
        self.ensure_one()

        _logger.info("=" * 80)
        _logger.info("[RECONCILIATION] ========== INICIO BÚSQUEDA DE PAGOS ==========")
        _logger.info(f"[RECONCILIATION] Factura Pública: {self.public_invoice_id.name}")
        _logger.info("=" * 80)

        if not self.config_id:
            _logger.error("[RECONCILIATION] ERROR: No hay configuración de Público en General")
            raise UserError(_(
                'No hay configuración de Público en General.\n\n'
                'Vaya a: Portal Facturación → Configuración → Público en General\n'
                'y cree una configuración antes de continuar.'
            ))

        if not self.config_id.public_partner_id:
            _logger.error("[RECONCILIATION] ERROR: No hay cliente Público en General configurado")
            raise UserError(_(
                'La configuración no tiene un cliente Público en General asignado.\n\n'
                'Vaya a: Portal Facturación → Configuración → Público en General\n'
                'y seleccione el cliente.'
            ))

        if not self.search_field_ids:
            _logger.error("[RECONCILIATION] ERROR: No hay campos de búsqueda seleccionados")
            raise UserError(_('Debe seleccionar al menos un campo de búsqueda.'))

        if not self.public_invoice_id.order_ids:
            _logger.error("[RECONCILIATION] ERROR: La factura no tiene órdenes asociadas")
            raise UserError(_('La factura no tiene órdenes asociadas.'))

        _logger.info(f"[RECONCILIATION] Configuración: {self.config_id.id}")
        _logger.info(f"[RECONCILIATION] Partner Público en General: {self.config_id.public_partner_id.name} (ID: {self.config_id.public_partner_id.id})")
        _logger.info(f"[RECONCILIATION] Campos de búsqueda seleccionados: {self.search_field_ids.mapped('name')}")
        _logger.info(f"[RECONCILIATION] Total órdenes en factura: {len(self.public_invoice_id.order_ids)}")

        # Limpiar líneas anteriores
        self.line_ids.unlink()

        partner_id = self.config_id.public_partner_id.id
        lines_to_create = []

        # Obtener conciliaciones ya existentes para esta factura
        existing_reconciliations = self.env['billing.public.reconciliation'].search([
            ('public_invoice_id', '=', self.public_invoice_id.id)
        ])
        already_reconciled_orders = existing_reconciliations.mapped('order_id').ids
        already_reconciled_payments = existing_reconciliations.mapped('payment_id').ids

        _logger.info(f"[RECONCILIATION] Conciliaciones existentes: {len(existing_reconciliations)}")
        _logger.info(f"[RECONCILIATION] Órdenes ya conciliadas: {already_reconciled_orders}")
        _logger.info(f"[RECONCILIATION] Pagos ya usados: {already_reconciled_payments}")

        # Contar pagos disponibles del partner
        available_payments = self.env['account.payment'].search([
            ('partner_id', '=', partner_id),
            ('state', '=', 'posted'),
            ('payment_type', '=', 'inbound'),
            ('id', 'not in', already_reconciled_payments),
        ])
        _logger.info(f"[RECONCILIATION] Pagos disponibles del partner: {len(available_payments)}")
        for payment in available_payments[:10]:  # Mostrar los primeros 10
            _logger.info(f"  - Pago: {payment.name}, Ref: {payment.ref}, Monto: {payment.amount}")

        orders_processed = 0
        orders_matched = 0
        orders_unmatched = 0

        _logger.info("-" * 80)
        _logger.info("[RECONCILIATION] Procesando órdenes...")
        _logger.info("-" * 80)

        for order in self.public_invoice_id.order_ids:
            orders_processed += 1
            _logger.info(f"\n[RECONCILIATION] --- Orden #{orders_processed}: {order.name} ---")
            _logger.info(f"[RECONCILIATION]   Monto: {order.amount_total}")
            _logger.info(f"[RECONCILIATION]   Client Ref: {order.client_order_ref}")

            # Mostrar valores de campos ML si existen
            if hasattr(order, 'ml_order_id'):
                _logger.info(f"[RECONCILIATION]   ML Order ID: {order.ml_order_id}")
            if hasattr(order, 'ml_pack_id'):
                _logger.info(f"[RECONCILIATION]   ML Pack ID: {order.ml_pack_id}")

            # Saltar órdenes ya conciliadas
            if order.id in already_reconciled_orders:
                _logger.info(f"[RECONCILIATION]   >> SALTADA: Ya tiene conciliación existente")
                continue

            line_data = {
                'wizard_id': self.id,
                'order_id': order.id,
                'order_amount': order.amount_total,
            }

            # Buscar pagos usando los campos configurados
            matched_payments = self.env['account.payment']
            matched_field = None
            matched_value = None

            for field_config in self.search_field_ids.sorted('sequence'):
                _logger.info(f"[RECONCILIATION]   Buscando con campo: {field_config.name} ({field_config.field_name} -> {field_config.payment_field})")

                search_value = getattr(order, field_config.field_name, None)
                _logger.info(f"[RECONCILIATION]   Valor en orden: '{search_value}'")

                if not search_value:
                    _logger.info(f"[RECONCILIATION]   >> Campo vacío, saltando...")
                    continue

                # Construir dominio de búsqueda
                domain = field_config.get_search_domain(search_value, partner_id)
                # Excluir pagos ya conciliados
                domain.append(('id', 'not in', already_reconciled_payments))

                _logger.info(f"[RECONCILIATION]   Dominio de búsqueda: {domain}")

                payments = self.env['account.payment'].search(domain)
                _logger.info(f"[RECONCILIATION]   Pagos encontrados: {len(payments)}")

                if payments:
                    for p in payments:
                        _logger.info(f"[RECONCILIATION]     - Pago: {p.name}, Ref: {p.ref}, Monto: {p.amount}")

                    matched_payments = payments
                    matched_field = field_config.name
                    matched_value = str(search_value)
                    _logger.info(f"[RECONCILIATION]   >> MATCH ENCONTRADO con campo '{matched_field}'")
                    break  # Usar el primer campo que encuentre coincidencias
                else:
                    _logger.info(f"[RECONCILIATION]   >> Sin coincidencias con este campo")

            if matched_payments:
                orders_matched += 1
                # Si hay múltiples pagos, crear una línea por cada pago
                for payment in matched_payments:
                    if payment.id in already_reconciled_payments:
                        _logger.info(f"[RECONCILIATION]   >> Pago {payment.name} ya usado, saltando")
                        continue
                    line_data_copy = line_data.copy()
                    line_data_copy.update({
                        'payment_id': payment.id,
                        'matched_field': matched_field,
                        'matched_value': matched_value,
                        'to_reconcile': True,
                    })
                    lines_to_create.append(line_data_copy)
                    _logger.info(f"[RECONCILIATION]   >> Línea creada: Orden {order.name} <-> Pago {payment.name}")
                    # Agregar a lista de ya usados para no duplicar
                    already_reconciled_payments.append(payment.id)
            else:
                orders_unmatched += 1
                _logger.info(f"[RECONCILIATION]   >> SIN MATCH - No se encontró pago coincidente")
                # Orden sin pago coincidente
                lines_to_create.append(line_data)

        _logger.info("=" * 80)
        _logger.info("[RECONCILIATION] ========== RESUMEN DE BÚSQUEDA ==========")
        _logger.info(f"[RECONCILIATION] Órdenes procesadas: {orders_processed}")
        _logger.info(f"[RECONCILIATION] Órdenes con pago encontrado: {orders_matched}")
        _logger.info(f"[RECONCILIATION] Órdenes sin pago: {orders_unmatched}")
        _logger.info(f"[RECONCILIATION] Líneas a crear: {len(lines_to_create)}")
        _logger.info("=" * 80)

        if lines_to_create:
            self.env['billing.public.reconciliation.wizard.line'].create(lines_to_create)
            _logger.info(f"[RECONCILIATION] Líneas creadas exitosamente")

        self.search_done = True
        self.state = 'preview'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_reconcile(self):
        """Ejecuta la conciliación de las líneas seleccionadas."""
        self.ensure_one()

        _logger.info("=" * 80)
        _logger.info("[RECONCILIATION] ========== EJECUTANDO CONCILIACIÓN ==========")
        _logger.info(f"[RECONCILIATION] Factura Pública: {self.public_invoice_id.name}")
        _logger.info("=" * 80)

        lines_to_reconcile = self.line_ids.filtered(lambda l: l.to_reconcile and l.payment_id)

        _logger.info(f"[RECONCILIATION] Total líneas en wizard: {len(self.line_ids)}")
        _logger.info(f"[RECONCILIATION] Líneas marcadas para conciliar: {len(lines_to_reconcile)}")

        if not lines_to_reconcile:
            _logger.warning("[RECONCILIATION] No hay líneas seleccionadas para conciliar")
            raise UserError(_('No hay líneas seleccionadas para conciliar.'))

        reconciliations_created = []

        errors = []
        for line in lines_to_reconcile:
            _logger.info(f"[RECONCILIATION] Procesando: Orden {line.order_id.name} <-> Pago {line.payment_id.name}")
            _logger.info(f"[RECONCILIATION]   Monto orden: {line.order_amount}")
            _logger.info(f"[RECONCILIATION]   Monto pago: {line.payment_amount}")
            _logger.info(f"[RECONCILIATION]   Monto a conciliar: {line.amount_to_reconcile}")

            # Verificar que no exista ya una conciliación para este par orden-pago
            existing = self.env['billing.public.reconciliation'].search([
                ('public_invoice_id', '=', self.public_invoice_id.id),
                ('order_id', '=', line.order_id.id),
                ('payment_id', '=', line.payment_id.id),
            ], limit=1)

            if existing:
                _logger.warning(
                    f"[RECONCILIATION] >> SALTADA: Conciliación ya existe para orden {line.order_id.name} y pago {line.payment_id.name}"
                )
                continue

            # Usar el nuevo método que hace la conciliación contable real
            try:
                reconciliation = self.env['billing.public.reconciliation'].create_with_reconciliation({
                    'public_invoice_id': self.public_invoice_id.id,
                    'order_id': line.order_id.id,
                    'order_amount': line.order_amount,
                    'payment_id': line.payment_id.id,
                    'matched_field': line.matched_field,
                    'matched_value': line.matched_value,
                    'amount': line.amount_to_reconcile,
                })
                reconciliations_created.append(reconciliation.id)
                _logger.info(f"[RECONCILIATION] >> CREADA: Conciliación ID {reconciliation.id} (contable realizada)")
            except Exception as e:
                error_msg = f"Orden {line.order_id.name}: {str(e)}"
                _logger.error(f"[RECONCILIATION] >> ERROR: {error_msg}")
                errors.append(error_msg)

        self.state = 'done'

        _logger.info("=" * 80)
        _logger.info(f"[RECONCILIATION] RESUMEN: Se crearon {len(reconciliations_created)} conciliaciones")
        if errors:
            _logger.info(f"[RECONCILIATION] ERRORES: {len(errors)}")
            for err in errors:
                _logger.info(f"  - {err}")
        _logger.info("=" * 80)

        # Si hubo errores, mostrarlos al usuario
        if errors and not reconciliations_created:
            raise UserError(_(
                'No se pudo realizar ninguna conciliación contable:\n\n%s'
            ) % '\n'.join(errors))
        elif errors:
            # Algunos exitosos, algunos con error
            raise UserError(_(
                'Se crearon %d conciliaciones, pero hubo %d errores:\n\n%s'
            ) % (len(reconciliations_created), len(errors), '\n'.join(errors)))

        # Regresar a la factura pública
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura Público en General'),
            'res_model': 'billing.public.invoice',
            'res_id': self.public_invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_back_to_search(self):
        """Volver a la pantalla de búsqueda."""
        self.ensure_one()
        self.state = 'search'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class BillingPublicReconciliationWizardLine(models.TransientModel):
    _name = 'billing.public.reconciliation.wizard.line'
    _description = 'Línea de Conciliación (Wizard)'

    wizard_id = fields.Many2one(
        'billing.public.reconciliation.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    order_id = fields.Many2one(
        'sale.order',
        string='Orden',
        required=True
    )

    order_name = fields.Char(
        related='order_id.name',
        string='# Orden'
    )

    order_reference = fields.Char(
        related='order_id.client_order_ref',
        string='Referencia Cliente'
    )

    order_amount = fields.Monetary(
        string='Monto Orden',
        currency_field='currency_id'
    )

    payment_id = fields.Many2one(
        'account.payment',
        string='Pago'
    )

    payment_name = fields.Char(
        related='payment_id.name',
        string='# Pago'
    )

    payment_ref = fields.Char(
        related='payment_id.ref',
        string='Referencia Pago'
    )

    payment_amount = fields.Monetary(
        related='payment_id.amount',
        string='Monto Pago',
        currency_field='currency_id'
    )

    matched_field = fields.Char(
        string='Campo Match'
    )

    matched_value = fields.Char(
        string='Valor Match'
    )

    difference = fields.Monetary(
        compute='_compute_difference',
        string='Diferencia',
        currency_field='currency_id'
    )

    amount_to_reconcile = fields.Monetary(
        compute='_compute_amount_to_reconcile',
        string='Monto a Conciliar',
        currency_field='currency_id'
    )

    to_reconcile = fields.Boolean(
        string='Conciliar',
        default=False
    )

    currency_id = fields.Many2one(
        related='wizard_id.currency_id',
        string='Moneda'
    )

    match_status = fields.Selection([
        ('matched', 'Coincide'),
        ('partial', 'Parcial'),
        ('no_match', 'Sin Pago'),
    ], compute='_compute_match_status', string='Estado')

    @api.depends('order_amount', 'payment_amount')
    def _compute_difference(self):
        for line in self:
            line.difference = (line.payment_amount or 0) - (line.order_amount or 0)

    @api.depends('order_amount', 'payment_amount')
    def _compute_amount_to_reconcile(self):
        for line in self:
            # Usar el menor de los dos montos
            line.amount_to_reconcile = min(
                line.order_amount or 0,
                line.payment_amount or 0
            )

    @api.depends('payment_id', 'difference')
    def _compute_match_status(self):
        for line in self:
            if not line.payment_id:
                line.match_status = 'no_match'
            elif abs(line.difference) < 0.01:
                line.match_status = 'matched'
            else:
                line.match_status = 'partial'
