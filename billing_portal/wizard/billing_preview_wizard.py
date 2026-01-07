# -*- coding: utf-8 -*-
"""
Wizard para vista previa de ejecuciones automáticas.
Permite ver qué se ejecutará antes de habilitar la automatización.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class BillingPreviewWizard(models.TransientModel):
    _name = 'billing.preview.wizard'
    _description = 'Vista Previa de Ejecución Automática'

    config_id = fields.Many2one(
        'billing.public.config',
        string='Configuración',
        required=True
    )

    preview_type = fields.Selection([
        ('invoice', 'Facturación'),
        ('reconciliation', 'Conciliación'),
    ], string='Tipo de Vista Previa', required=True, default='invoice')

    # Campos para facturación
    date_from = fields.Date(
        string='Desde',
    )

    date_to = fields.Date(
        string='Hasta',
    )

    # Tipo de período (heredado de config)
    period_type = fields.Selection([
        ('days', 'Últimos X días'),
        ('dates', 'Rango de fechas específico'),
    ], string='Tipo de Período', default='days')

    # Órdenes a facturar
    order_ids = fields.Many2many(
        'sale.order',
        'billing_preview_wizard_order_rel',
        'wizard_id',
        'order_id',
        string='Órdenes a Facturar'
    )

    order_count = fields.Integer(
        string='# Órdenes',
        compute='_compute_order_stats'
    )

    total_amount = fields.Monetary(
        string='Monto Total',
        compute='_compute_order_stats',
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # Campos para conciliación
    public_invoice_ids = fields.Many2many(
        'billing.public.invoice',
        'billing_preview_wizard_invoice_rel',
        'wizard_id',
        'invoice_id',
        string='Facturas Público en General'
    )

    reconciliation_line_ids = fields.One2many(
        'billing.preview.wizard.reconciliation.line',
        'wizard_id',
        string='Conciliaciones Potenciales'
    )

    reconciliation_count = fields.Integer(
        string='# Conciliaciones',
        compute='_compute_reconciliation_stats'
    )

    reconciliation_amount = fields.Monetary(
        string='Monto a Conciliar',
        compute='_compute_reconciliation_stats',
        currency_field='currency_id'
    )

    # Estado
    preview_done = fields.Boolean(
        string='Vista Previa Realizada',
        default=False
    )

    state = fields.Selection([
        ('setup', 'Configuración'),
        ('preview', 'Vista Previa'),
        ('executed', 'Ejecutado'),
    ], string='Estado', default='setup')

    @api.model
    def default_get(self, fields_list):
        """Calcula las fechas por defecto basándose en la configuración."""
        res = super().default_get(fields_list)

        # Si viene config_id del contexto, calcular las fechas
        config_id = res.get('config_id') or self._context.get('default_config_id')
        if config_id:
            config = self.env['billing.public.config'].browse(config_id)
            if config.exists():
                res['period_type'] = config.auto_invoice_period_type or 'days'
                if config.auto_invoice_period_type == 'dates':
                    res['date_from'] = config.auto_invoice_date_from
                    res['date_to'] = config.auto_invoice_date_to
                else:
                    res['date_to'] = date.today()
                    res['date_from'] = date.today() - timedelta(
                        days=config.auto_invoice_period_days or 7
                    )
        else:
            res['date_from'] = date.today().replace(day=1)
            res['date_to'] = date.today()

        return res

    @api.onchange('config_id')
    def _onchange_config_id(self):
        """Carga el tipo de período según la configuración."""
        if self.config_id:
            self.period_type = self.config_id.auto_invoice_period_type or 'days'
            # Si es modo fechas, cargar las fechas de la configuración
            if self.period_type == 'dates':
                self.date_from = self.config_id.auto_invoice_date_from
                self.date_to = self.config_id.auto_invoice_date_to

    @api.onchange('period_type')
    def _onchange_period_type(self):
        """Carga las fechas de la configuración cuando cambia a modo fechas."""
        if self.config_id and self.period_type == 'dates':
            # Cargar fechas de la configuración si existen
            if self.config_id.auto_invoice_date_from:
                self.date_from = self.config_id.auto_invoice_date_from
            if self.config_id.auto_invoice_date_to:
                self.date_to = self.config_id.auto_invoice_date_to

    @api.depends('order_ids')
    def _compute_order_stats(self):
        for wizard in self:
            wizard.order_count = len(wizard.order_ids)
            wizard.total_amount = sum(wizard.order_ids.mapped('amount_total'))

    @api.depends('reconciliation_line_ids')
    def _compute_reconciliation_stats(self):
        for wizard in self:
            wizard.reconciliation_count = len(wizard.reconciliation_line_ids.filtered('payment_id'))
            wizard.reconciliation_amount = sum(
                wizard.reconciliation_line_ids.filtered('payment_id').mapped('amount_to_reconcile')
            )

    def action_generate_preview(self):
        """Genera la vista previa según el tipo seleccionado."""
        self.ensure_one()

        if self.preview_type == 'invoice':
            return self._generate_invoice_preview()
        else:
            return self._generate_reconciliation_preview()

    def _generate_invoice_preview(self):
        """Genera vista previa de facturación.

        NOTA: Los productos excluidos solo aplican para el portal del cliente,
        NO para la factura Público en General.
        """
        self.ensure_one()

        if not self.config_id:
            raise UserError(_('Debe seleccionar una configuración.'))

        if not self.config_id.public_partner_id:
            raise UserError(_('La configuración no tiene un cliente Público en General asignado.'))

        # Calcular fechas según el tipo de período
        if self.period_type == 'days':
            # Últimos X días - calcular automáticamente
            date_to = date.today()
            date_from = date.today() - timedelta(
                days=self.config_id.auto_invoice_period_days or 7
            )
            _logger.info(f"[PREVIEW] Modo 'days': calculando últimos {self.config_id.auto_invoice_period_days} días")
        else:
            # Rango de fechas específico - usar las fechas del wizard
            date_from = self.date_from
            date_to = self.date_to
            _logger.info(f"[PREVIEW] Modo 'dates': usando fechas del wizard")

        _logger.info(f"[PREVIEW] date_from={date_from}, date_to={date_to}")

        # Validar fechas
        if not date_from or not date_to:
            raise UserError(_('Debe especificar las fechas del período a facturar.'))

        if date_from > date_to:
            raise UserError(_('La fecha "Desde" debe ser anterior o igual a la fecha "Hasta".'))

        # Guardar las fechas calculadas en el wizard para mostrarlas en la vista previa
        self.date_from = date_from
        self.date_to = date_to

        # Buscar órdenes elegibles
        domain = [
            ('company_id', '=', self.config_id.company_id.id),
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to),
            ('state', 'in', ('sale', 'done')),
            ('invoice_status', '!=', 'invoiced'),
        ]

        _logger.info(f"[PREVIEW] Dominio de búsqueda: {domain}")

        orders = self.env['sale.order'].search(domain)
        _logger.info(f"[PREVIEW] Órdenes encontradas: {len(orders)}")

        # Filtrar órdenes
        eligible_orders = self.env['sale.order']
        for order in orders:
            # Excluir si tiene billing_request completado (ya se facturó por portal)
            if hasattr(order, 'billing_request_ids'):
                completed_requests = order.billing_request_ids.filtered(
                    lambda r: r.state == 'done'
                )
                if completed_requests:
                    continue

            # Verificar estado de envío ML según configuración
            if hasattr(order, 'ml_shipment_status') and not self.config_id.is_ml_status_allowed(order.ml_shipment_status):
                continue

            eligible_orders |= order

        self.write({
            'order_ids': [(6, 0, eligible_orders.ids)],
            'preview_done': True,
            'state': 'preview',
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _generate_reconciliation_preview(self):
        """Genera vista previa de conciliación.

        Muestra múltiples pagos por orden si es necesario (N pagos → 1 orden)
        y permite que un pago se use para múltiples órdenes (1 pago → N órdenes)
        """
        self.ensure_one()

        if not self.config_id:
            raise UserError(_('Debe seleccionar una configuración.'))

        if not self.config_id.public_partner_id:
            raise UserError(_('La configuración no tiene un cliente Público en General asignado.'))

        # Buscar facturas públicas pendientes
        public_invoices = self.env['billing.public.invoice'].search([
            ('company_id', '=', self.config_id.company_id.id),
            ('state', 'in', ['invoiced', 'partial']),
        ])

        if not public_invoices:
            raise UserError(_('No hay facturas Público en General pendientes de conciliación.'))

        self.public_invoice_ids = [(6, 0, public_invoices.ids)]

        # Limpiar líneas anteriores
        self.reconciliation_line_ids.unlink()

        partner_id = self.config_id.public_partner_id.id
        lines_to_create = []

        # Obtener campos de búsqueda activos
        search_fields = self.env['billing.reconciliation.field'].get_active_fields(
            self.config_id.company_id.id
        )

        # Cache global de saldos usados (para preview)
        payment_used_amounts = {}  # {payment_id: monto_usado_en_preview}

        for public_invoice in public_invoices:
            # Obtener conciliaciones ya existentes
            existing_reconciliations = self.env['billing.public.reconciliation'].search([
                ('public_invoice_id', '=', public_invoice.id)
            ])

            # Calcular montos ya conciliados por orden
            order_reconciled_amounts = {}
            for rec in existing_reconciliations:
                if rec.order_id.id not in order_reconciled_amounts:
                    order_reconciled_amounts[rec.order_id.id] = 0
                order_reconciled_amounts[rec.order_id.id] += rec.amount

            for order in public_invoice.order_ids:
                # Calcular saldo pendiente de la orden
                order_reconciled = order_reconciled_amounts.get(order.id, 0)
                order_remaining = order.amount_total - order_reconciled

                if order_remaining <= 0:
                    continue  # Orden completamente conciliada

                # Buscar TODOS los pagos que coincidan
                for field_config in search_fields.sorted('sequence'):
                    search_value = getattr(order, field_config.field_name, None)
                    if not search_value:
                        continue

                    # Construir dominio de búsqueda (NO excluir pagos usados)
                    domain = field_config.get_search_domain(search_value, partner_id)
                    payments = self.env['account.payment'].search(domain)

                    for payment in payments:
                        if order_remaining <= 0:
                            break  # Orden ya cubierta

                        # Calcular saldo disponible del pago
                        payment_total_used = self._get_payment_total_reconciled(payment)
                        payment_preview_used = payment_used_amounts.get(payment.id, 0)
                        payment_remaining = payment.amount - payment_total_used - payment_preview_used

                        if payment_remaining <= 0:
                            continue  # Pago sin saldo

                        # Calcular monto a conciliar
                        amount_to_reconcile = min(order_remaining, payment_remaining)

                        # Crear línea de preview
                        lines_to_create.append({
                            'wizard_id': self.id,
                            'public_invoice_id': public_invoice.id,
                            'order_id': order.id,
                            'order_amount': order.amount_total,
                            'order_pending': order_remaining,
                            'payment_id': payment.id,
                            'payment_available': payment_remaining,
                            'matched_field': field_config.name,
                            'matched_value': str(search_value),
                            'preview_amount': amount_to_reconcile,
                        })

                        # Actualizar caches
                        if payment.id not in payment_used_amounts:
                            payment_used_amounts[payment.id] = 0
                        payment_used_amounts[payment.id] += amount_to_reconcile
                        order_remaining -= amount_to_reconcile

                    # Si orden cubierta, no buscar en más campos
                    if order_remaining <= 0:
                        break

                # Si no encontró pagos, crear línea sin pago (para mostrar que falta)
                if order_remaining > 0 and not any(
                    l['order_id'] == order.id for l in lines_to_create
                    if l.get('public_invoice_id') == public_invoice.id
                ):
                    lines_to_create.append({
                        'wizard_id': self.id,
                        'public_invoice_id': public_invoice.id,
                        'order_id': order.id,
                        'order_amount': order.amount_total,
                        'order_pending': order_remaining,
                    })

        if lines_to_create:
            self.env['billing.preview.wizard.reconciliation.line'].create(lines_to_create)

        self.write({
            'preview_done': True,
            'state': 'preview',
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_payment_total_reconciled(self, payment):
        """Obtiene el total ya conciliado de un pago."""
        existing = self.env['billing.public.reconciliation'].search([
            ('payment_id', '=', payment.id)
        ])
        return sum(existing.mapped('amount'))

    def action_execute(self):
        """Ejecuta la operación según la vista previa."""
        self.ensure_one()

        if self.preview_type == 'invoice':
            return self._execute_invoice()
        else:
            return self._execute_reconciliation()

    def _execute_invoice(self):
        """Ejecuta la creación de factura usando las órdenes del wizard."""
        self.ensure_one()

        if not self.order_ids:
            raise UserError(_('No hay órdenes para facturar.'))

        # Crear registro de ejecución
        execution = self.env['billing.auto.execution'].create({
            'config_id': self.config_id.id,
            'execution_type': 'invoice',
            'manual': True,
            'state': 'running',
        })

        try:
            # Crear el registro de factura pública usando las fechas del wizard
            public_invoice = self.env['billing.public.invoice'].create({
                'date_from': self.date_from,
                'date_to': self.date_to,
                'order_ids': [(6, 0, self.order_ids.ids)],
                'company_id': self.config_id.company_id.id,
            })

            # Crear la factura consolidada
            invoice = self.config_id._create_consolidated_invoice(self.order_ids)

            # Asociar factura al registro
            public_invoice.write({
                'invoice_id': invoice.id,
                'state': 'invoiced',
            })

            # Publicar factura automáticamente si está configurado
            if self.config_id.auto_post_invoice and invoice.state == 'draft':
                invoice.action_post()

            execution.write({
                'state': 'done',
                'result_message': f'Factura {invoice.name} creada exitosamente con {len(self.order_ids)} órdenes.',
                'orders_found': len(self.order_ids),
                'orders_processed': len(self.order_ids),
                'invoice_id': invoice.id,
                'public_invoice_id': public_invoice.id,
            })

            self.state = 'executed'

            return {
                'type': 'ir.actions.act_window',
                'name': _('Factura Público en General'),
                'res_model': 'billing.public.invoice',
                'res_id': public_invoice.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            execution.write({
                'state': 'error',
                'result_message': str(e),
            })
            raise UserError(_('Error al crear la factura: %s') % str(e))

    def _execute_reconciliation(self):
        """Ejecuta la conciliación con conciliación contable real."""
        self.ensure_one()

        lines_to_reconcile = self.reconciliation_line_ids.filtered('payment_id')

        if not lines_to_reconcile:
            raise UserError(_('No hay conciliaciones para ejecutar.'))

        reconciliations_created = []
        errors = []

        for line in lines_to_reconcile:
            # Verificar que no exista ya
            existing = self.env['billing.public.reconciliation'].search([
                ('public_invoice_id', '=', line.public_invoice_id.id),
                ('order_id', '=', line.order_id.id),
                ('payment_id', '=', line.payment_id.id),
            ], limit=1)

            if existing:
                continue

            # Usar create_with_reconciliation para hacer la conciliación contable real
            try:
                reconciliation = self.env['billing.public.reconciliation'].create_with_reconciliation({
                    'public_invoice_id': line.public_invoice_id.id,
                    'order_id': line.order_id.id,
                    'order_amount': line.order_amount,
                    'payment_id': line.payment_id.id,
                    'matched_field': line.matched_field,
                    'matched_value': line.matched_value,
                    'amount': line.amount_to_reconcile,
                })
                reconciliations_created.append(reconciliation.id)
            except Exception as e:
                errors.append(f"Orden {line.order_id.name}: {str(e)}")

        self.state = 'executed'

        # Si hubo errores, mostrarlos
        if errors and not reconciliations_created:
            raise UserError(_('No se pudo realizar ninguna conciliación:\n\n%s') % '\n'.join(errors))
        elif errors:
            raise UserError(_(
                'Se crearon %d conciliaciones, pero hubo %d errores:\n\n%s'
            ) % (len(reconciliations_created), len(errors), '\n'.join(errors)))

        # Cerrar wizard y refrescar vista
        return {'type': 'ir.actions.act_window_close'}

    def action_back(self):
        """Volver a la configuración."""
        self.ensure_one()
        self.state = 'setup'
        self.preview_done = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class BillingPreviewWizardReconciliationLine(models.TransientModel):
    _name = 'billing.preview.wizard.reconciliation.line'
    _description = 'Línea de Vista Previa de Conciliación'

    wizard_id = fields.Many2one(
        'billing.preview.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    public_invoice_id = fields.Many2one(
        'billing.public.invoice',
        string='Factura Pública',
        required=True
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

    order_amount = fields.Monetary(
        string='Monto Orden',
        currency_field='currency_id'
    )

    order_pending = fields.Monetary(
        string='Pendiente Orden',
        currency_field='currency_id',
        help='Monto pendiente de conciliar de la orden'
    )

    payment_id = fields.Many2one(
        'account.payment',
        string='Pago'
    )

    payment_name = fields.Char(
        related='payment_id.name',
        string='# Pago'
    )

    payment_amount = fields.Monetary(
        related='payment_id.amount',
        string='Monto Pago Total',
        currency_field='currency_id'
    )

    payment_available = fields.Monetary(
        string='Disponible Pago',
        currency_field='currency_id',
        help='Monto disponible del pago para conciliar'
    )

    matched_field = fields.Char(
        string='Campo Match'
    )

    matched_value = fields.Char(
        string='Valor Match'
    )

    preview_amount = fields.Monetary(
        string='Monto a Conciliar',
        currency_field='currency_id',
        help='Monto que se conciliará (calculado en preview)'
    )

    amount_to_reconcile = fields.Monetary(
        compute='_compute_amount_to_reconcile',
        string='Monto Conciliación',
        currency_field='currency_id'
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

    @api.depends('preview_amount', 'order_amount', 'payment_amount')
    def _compute_amount_to_reconcile(self):
        for line in self:
            if line.preview_amount:
                line.amount_to_reconcile = line.preview_amount
            else:
                line.amount_to_reconcile = min(
                    line.order_amount or 0,
                    line.payment_amount or 0
                )

    @api.depends('payment_id', 'order_pending', 'preview_amount')
    def _compute_match_status(self):
        for line in self:
            if not line.payment_id:
                line.match_status = 'no_match'
            elif line.preview_amount and line.order_pending:
                # Si el monto a conciliar cubre todo el pendiente
                if abs(line.preview_amount - line.order_pending) < 0.01:
                    line.match_status = 'matched'
                else:
                    line.match_status = 'partial'
            elif abs((line.payment_amount or 0) - (line.order_amount or 0)) < 0.01:
                line.match_status = 'matched'
            else:
                line.match_status = 'partial'
