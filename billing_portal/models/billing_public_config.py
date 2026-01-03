# -*- coding: utf-8 -*-
"""
Configuración para facturación a Público en General.
"""

import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BillingPublicConfig(models.Model):
    _name = 'billing.public.config'
    _description = 'Configuración Factura Público en General'
    _rec_name = 'public_partner_id'

    active = fields.Boolean(default=True)

    public_partner_id = fields.Many2one(
        'res.partner',
        string='Cliente Público en General',
        required=True,
        help='Partner que se usará como cliente para las facturas a Público en General'
    )

    # Datos fiscales por defecto
    uso_cfdi_id = fields.Many2one(
        'catalogo.uso.cfdi',
        string='Uso CFDI por Defecto',
        help='Uso de CFDI para facturas a Público en General (típicamente S01)'
    )

    forma_pago_id = fields.Many2one(
        'catalogo.forma.pago',
        string='Forma de Pago por Defecto',
        help='Forma de pago para facturas a Público en General'
    )

    regimen_fiscal_id = fields.Many2one(
        'catalogo.regimen.fiscal',
        string='Régimen Fiscal por Defecto',
        help='Régimen fiscal del cliente Público en General'
    )

    metodo_pago = fields.Selection([
        ('PUE', 'PUE - Pago en una sola exhibición'),
        ('PPD', 'PPD - Pago en parcialidades o diferido'),
    ], string='Método de Pago por Defecto',
        help='Método de pago para facturas (PUE o PPD)'
    )

    # Configuración de tolerancia para conciliación
    allow_partial_reconciliation = fields.Boolean(
        string='Permitir Conciliación Parcial',
        default=True,
        help='Permite conciliar pagos aunque el monto no coincida exactamente'
    )

    tolerance_type = fields.Selection([
        ('none', 'Sin Tolerancia'),
        ('fixed', 'Monto Fijo'),
        ('percent', 'Porcentaje'),
    ], string='Tipo de Tolerancia', default='none')

    tolerance_amount = fields.Float(
        string='Tolerancia (Monto)',
        default=0.0,
        help='Diferencia máxima permitida en monto fijo'
    )

    tolerance_percent = fields.Float(
        string='Tolerancia (%)',
        default=0.0,
        help='Diferencia máxima permitida en porcentaje'
    )

    # Configuración de facturación
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario de Facturación',
        domain=[('type', '=', 'sale')],
        help='Diario a usar para crear las facturas'
    )

    auto_post_invoice = fields.Boolean(
        string='Publicar Factura Automáticamente',
        default=False,
        help='Si está marcado, la factura se publicará automáticamente al crearla'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )

    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre esta configuración'
    )

    # ========== Filtros de Estado de Envío ML ==========
    ml_include_delivered = fields.Boolean(
        string='Incluir Entregados (delivered)',
        default=True,
        help='Incluir órdenes con estado de envío "delivered"'
    )
    ml_include_shipped = fields.Boolean(
        string='Incluir Enviados (shipped)',
        default=False,
        help='Incluir órdenes con estado de envío "shipped"'
    )
    ml_include_pending = fields.Boolean(
        string='Incluir Pendientes (pending)',
        default=False,
        help='Incluir órdenes con estado de envío "pending"'
    )
    ml_include_ready_to_ship = fields.Boolean(
        string='Incluir Listos para enviar (ready_to_ship)',
        default=False,
        help='Incluir órdenes con estado de envío "ready_to_ship"'
    )
    ml_include_no_status = fields.Boolean(
        string='Incluir Sin estado ML',
        default=True,
        help='Incluir órdenes que no tienen estado de envío ML (órdenes no ML)'
    )

    # ========== Configuración de Automatización - FACTURACIÓN ==========
    auto_invoice_enabled = fields.Boolean(
        string='Facturación Automática',
        default=False,
        help='Habilitar creación automática de facturas Público en General'
    )

    invoice_day_of_month = fields.Integer(
        string='Día del Mes',
        default=1,
        help='Día del mes para ejecutar la facturación (1-28)'
    )

    invoice_hour = fields.Integer(
        string='Hora',
        default=6,
        help='Hora del día para ejecutar la facturación (0-23)'
    )

    invoice_minute = fields.Integer(
        string='Minuto',
        default=0,
        help='Minuto para ejecutar la facturación (0-59)'
    )

    # ========== Configuración de Automatización - CONCILIACIÓN ==========
    auto_reconciliation_enabled = fields.Boolean(
        string='Conciliación Automática',
        default=False,
        help='Habilitar conciliación automática de pagos'
    )

    reconciliation_frequency_type = fields.Selection([
        ('minutes', 'Minutos'),
        ('hours', 'Horas'),
        ('days', 'Días'),
        ('weeks', 'Semanas'),
    ], string='Tipo de Frecuencia', default='hours',
        help='Tipo de intervalo para conciliación automática')

    reconciliation_frequency_number = fields.Integer(
        string='Cada',
        default=4,
        help='Número de intervalos entre ejecuciones (ej: 5 minutos, 2 horas)'
    )

    # Campos de última ejecución para cada tipo
    last_invoice_execution = fields.Datetime(
        string='Última Ejecución Facturación',
        readonly=True,
        help='Fecha/hora de la última ejecución automática de facturación'
    )

    last_reconciliation_execution = fields.Datetime(
        string='Última Ejecución Conciliación',
        readonly=True,
        help='Fecha/hora de la última ejecución automática de conciliación'
    )

    # Campos legacy para compatibilidad
    auto_frequency = fields.Selection([
        ('daily', 'Diaria'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
    ], string='Frecuencia (Legacy)', default='weekly')

    auto_day_of_week = fields.Selection([
        ('0', 'Lunes'),
        ('1', 'Martes'),
        ('2', 'Miércoles'),
        ('3', 'Jueves'),
        ('4', 'Viernes'),
        ('5', 'Sábado'),
        ('6', 'Domingo'),
    ], string='Día de la Semana', default='0')

    auto_day_of_month = fields.Integer(
        string='Día del Mes',
        default=1
    )

    auto_hour = fields.Integer(
        string='Hora de Ejecución',
        default=6
    )

    auto_invoice_period_type = fields.Selection([
        ('days', 'Últimos X días'),
        ('dates', 'Rango de fechas específico'),
    ], string='Tipo de Período', default='days',
        help='Cómo definir el período de facturación')

    auto_invoice_period_days = fields.Integer(
        string='Días hacia atrás',
        default=7,
        help='Número de días hacia atrás para buscar órdenes a facturar'
    )

    auto_invoice_date_from = fields.Date(
        string='Fecha Desde',
        help='Fecha de inicio del período a facturar'
    )

    auto_invoice_date_to = fields.Date(
        string='Fecha Hasta',
        help='Fecha de fin del período a facturar'
    )

    auto_notify_email = fields.Char(
        string='Email de Notificación',
        help='Email para recibir notificaciones de ejecuciones automáticas'
    )

    last_auto_execution = fields.Datetime(
        string='Última Ejecución Automática',
        readonly=True
    )

    last_auto_execution_result = fields.Text(
        string='Resultado Última Ejecución',
        readonly=True
    )

    execution_ids = fields.One2many(
        'billing.auto.execution',
        'config_id',
        string='Historial de Ejecuciones'
    )

    @api.constrains('auto_day_of_month', 'invoice_day_of_month')
    def _check_day_of_month(self):
        for record in self:
            if record.auto_day_of_month and (record.auto_day_of_month < 1 or record.auto_day_of_month > 28):
                raise ValidationError('El día del mes debe estar entre 1 y 28')
            if record.invoice_day_of_month and (record.invoice_day_of_month < 1 or record.invoice_day_of_month > 28):
                raise ValidationError('El día del mes para facturación debe estar entre 1 y 28')

    @api.constrains('auto_hour', 'invoice_hour')
    def _check_hour(self):
        for record in self:
            if record.auto_hour and (record.auto_hour < 0 or record.auto_hour > 23):
                raise ValidationError('La hora debe estar entre 0 y 23')
            if record.invoice_hour and (record.invoice_hour < 0 or record.invoice_hour > 23):
                raise ValidationError('La hora de facturación debe estar entre 0 y 23')

    @api.constrains('invoice_minute')
    def _check_minute(self):
        for record in self:
            if record.invoice_minute and (record.invoice_minute < 0 or record.invoice_minute > 59):
                raise ValidationError('El minuto debe estar entre 0 y 59')

    @api.constrains('reconciliation_frequency_number')
    def _check_frequency_number(self):
        for record in self:
            if record.reconciliation_frequency_number and record.reconciliation_frequency_number < 1:
                raise ValidationError('El número de frecuencia debe ser al menos 1')

    @api.constrains('auto_invoice_period_type', 'auto_invoice_date_from', 'auto_invoice_date_to')
    def _check_dates(self):
        for record in self:
            if record.auto_invoice_period_type == 'dates':
                if record.auto_invoice_date_from and record.auto_invoice_date_to:
                    if record.auto_invoice_date_from > record.auto_invoice_date_to:
                        raise ValidationError('La fecha "Desde" debe ser anterior o igual a la fecha "Hasta"')

    @api.constrains('tolerance_type', 'tolerance_amount', 'tolerance_percent')
    def _check_tolerance(self):
        for record in self:
            if record.tolerance_type == 'fixed' and record.tolerance_amount < 0:
                raise ValidationError('La tolerancia de monto no puede ser negativa')
            if record.tolerance_type == 'percent':
                if record.tolerance_percent < 0 or record.tolerance_percent > 100:
                    raise ValidationError('La tolerancia porcentual debe estar entre 0 y 100')

    @api.model
    def get_config(self, company_id=None):
        """
        Obtiene la configuración activa para la compañía.
        """
        if not company_id:
            company_id = self.env.company.id
        config = self.search([
            ('company_id', '=', company_id),
            ('active', '=', True)
        ], limit=1)
        return config

    def is_within_tolerance(self, expected_amount, actual_amount):
        """
        Verifica si la diferencia entre montos está dentro de la tolerancia.
        """
        self.ensure_one()
        difference = abs(expected_amount - actual_amount)

        if self.tolerance_type == 'none':
            return difference == 0
        elif self.tolerance_type == 'fixed':
            return difference <= self.tolerance_amount
        elif self.tolerance_type == 'percent':
            if expected_amount == 0:
                return actual_amount == 0
            percent_diff = (difference / expected_amount) * 100
            return percent_diff <= self.tolerance_percent

        return False

    def is_ml_status_allowed(self, ml_status):
        """
        Verifica si un estado de envío ML está permitido para facturación.

        Args:
            ml_status: Estado de envío ML de la orden (puede ser None/False)

        Returns:
            bool: True si el estado está permitido según la configuración
        """
        self.ensure_one()

        # Si no tiene estado ML
        if not ml_status:
            return self.ml_include_no_status

        # Mapeo de estados a campos de configuración
        status_mapping = {
            'delivered': self.ml_include_delivered,
            'shipped': self.ml_include_shipped,
            'pending': self.ml_include_pending,
            'ready_to_ship': self.ml_include_ready_to_ship,
        }

        # Si el estado está en el mapeo, usar la configuración
        if ml_status in status_mapping:
            return status_mapping[ml_status]

        # Para estados no mapeados, no incluir por defecto
        _logger.warning(f"Estado ML no reconocido: {ml_status}")
        return False

    def action_preview_invoice(self):
        """Abre el wizard de vista previa de facturación."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vista Previa - Facturación Público en General',
            'res_model': 'billing.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
                'default_preview_type': 'invoice',
            }
        }

    def action_preview_reconciliation(self):
        """Abre el wizard de vista previa de conciliación."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vista Previa - Conciliación',
            'res_model': 'billing.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
                'default_preview_type': 'reconciliation',
            }
        }

    def action_execute_invoice_now(self):
        """Ejecuta la facturación manualmente."""
        self.ensure_one()
        return self._execute_auto_invoice(manual=True)

    def action_execute_reconciliation_now(self):
        """Ejecuta la conciliación manualmente."""
        self.ensure_one()
        return self._execute_auto_reconciliation(manual=True)

    def _execute_auto_invoice(self, manual=False):
        """
        Ejecuta la creación automática de facturas Público en General.
        """
        self.ensure_one()
        from datetime import timedelta

        execution = self.env['billing.auto.execution'].create({
            'config_id': self.id,
            'execution_type': 'invoice',
            'manual': manual,
            'state': 'running',
        })

        try:
            # Calcular fechas del período según el tipo seleccionado
            if self.auto_invoice_period_type == 'dates':
                # Usar fechas específicas configuradas
                date_from = self.auto_invoice_date_from
                date_to = self.auto_invoice_date_to
                if not date_from or not date_to:
                    raise ValueError('Las fechas de inicio y fin son requeridas cuando se usa rango de fechas específico')
            else:
                # Usar últimos X días (comportamiento por defecto)
                date_to = fields.Date.today()
                date_from = date_to - timedelta(days=self.auto_invoice_period_days)

            # NOTA: Los productos excluidos solo aplican para el portal del cliente,
            # NO para la factura Público en General.

            # Buscar órdenes elegibles
            domain = [
                ('company_id', '=', self.company_id.id),
                ('date_order', '>=', date_from),
                ('date_order', '<=', date_to),
                ('state', 'in', ('sale', 'done')),
                ('invoice_status', '!=', 'invoiced'),
            ]

            orders = self.env['sale.order'].search(domain)

            # Filtrar órdenes
            eligible_orders = self.env['sale.order']
            for order in orders:
                # Excluir si tiene billing_request completado (ya se facturó por portal)
                completed_requests = order.billing_request_ids.filtered(
                    lambda r: r.state == 'done'
                )
                if completed_requests:
                    continue

                # Verificar estado de envío ML según configuración
                if not self.is_ml_status_allowed(order.ml_shipment_status):
                    continue

                eligible_orders |= order

            if not eligible_orders:
                execution.write({
                    'state': 'done',
                    'result_message': 'No se encontraron órdenes elegibles para facturar.',
                    'orders_found': 0,
                })
                self.write({
                    'last_auto_execution': fields.Datetime.now(),
                    'last_auto_execution_result': 'Sin órdenes elegibles',
                })
                return execution

            # Crear el registro de factura pública
            public_invoice = self.env['billing.public.invoice'].create({
                'date_from': date_from,
                'date_to': date_to,
                'order_ids': [(6, 0, eligible_orders.ids)],
                'company_id': self.company_id.id,
            })

            # Crear la factura consolidada
            invoice = self._create_consolidated_invoice(eligible_orders)

            # Asociar factura al registro
            public_invoice.write({
                'invoice_id': invoice.id,
                'state': 'invoiced',
            })

            # Publicar factura automáticamente si está configurado
            if self.auto_post_invoice and invoice.state == 'draft':
                invoice.action_post()

            execution.write({
                'state': 'done',
                'result_message': f'Factura {invoice.name} creada exitosamente con {len(eligible_orders)} órdenes.',
                'orders_found': len(eligible_orders),
                'orders_processed': len(eligible_orders),
                'invoice_id': invoice.id,
                'public_invoice_id': public_invoice.id,
            })

            self.write({
                'last_auto_execution': fields.Datetime.now(),
                'last_auto_execution_result': f'Factura {invoice.name} creada',
            })

            # Enviar notificación
            self._send_execution_notification(execution)

            return execution

        except Exception as e:
            _logger.exception("Error en ejecución automática de facturación")
            execution.write({
                'state': 'error',
                'result_message': str(e),
            })
            self.write({
                'last_auto_execution': fields.Datetime.now(),
                'last_auto_execution_result': f'Error: {str(e)[:100]}',
            })
            return execution

    def _create_consolidated_invoice(self, orders):
        """
        Crea una factura consolidada con todas las líneas de las órdenes.
        """
        self.ensure_one()

        partner = self.public_partner_id

        # Preparar valores de la factura
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'journal_id': self.journal_id.id if self.journal_id else False,
            'company_id': self.company_id.id,
            'invoice_line_ids': [],
        }

        # Agregar datos fiscales si están configurados
        if self.uso_cfdi_id:
            invoice_vals['uso_cfdi_id'] = self.uso_cfdi_id.id
        if self.forma_pago_id:
            invoice_vals['forma_pago_id'] = self.forma_pago_id.id
        if self.metodo_pago:
            invoice_vals['methodo_pago'] = self.metodo_pago

        # Agregar líneas de factura desde las órdenes
        line_vals = []
        for order in orders:
            for line in order.order_line:
                # Saltar líneas sin producto o con cantidad 0
                if not line.product_id or line.product_uom_qty <= 0:
                    continue

                # Calcular cantidad pendiente de facturar
                qty_to_invoice = line.product_uom_qty - line.qty_invoiced
                if qty_to_invoice <= 0:
                    continue

                line_vals.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': f"[{order.name}] {line.name}",
                    'quantity': qty_to_invoice,
                    'product_uom_id': line.product_uom.id,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'tax_ids': [(6, 0, line.tax_id.ids)],
                    'sale_line_ids': [(6, 0, [line.id])],
                }))

        invoice_vals['invoice_line_ids'] = line_vals

        # Crear la factura
        invoice = self.env['account.move'].create(invoice_vals)

        return invoice

    def _execute_auto_reconciliation(self, manual=False):
        """
        Ejecuta la conciliación automática de pagos.
        """
        self.ensure_one()

        execution = self.env['billing.auto.execution'].create({
            'config_id': self.id,
            'execution_type': 'reconciliation',
            'manual': manual,
            'state': 'running',
        })

        try:
            # Buscar facturas públicas pendientes de conciliación
            public_invoices = self.env['billing.public.invoice'].search([
                ('company_id', '=', self.company_id.id),
                ('state', 'in', ['invoiced', 'partial']),
            ])

            if not public_invoices:
                execution.write({
                    'state': 'done',
                    'result_message': 'No hay facturas Público en General pendientes de conciliación.',
                })
                return execution

            total_reconciled = 0
            total_amount = 0

            # Obtener campos de búsqueda activos
            search_fields = self.env['billing.reconciliation.field'].get_active_fields(self.company_id.id)

            for public_invoice in public_invoices:
                reconciled_count, reconciled_amount = self._reconcile_public_invoice(
                    public_invoice, search_fields
                )
                total_reconciled += reconciled_count
                total_amount += reconciled_amount

            execution.write({
                'state': 'done',
                'result_message': f'Se conciliaron {total_reconciled} pagos por un total de ${total_amount:,.2f}',
                'orders_processed': total_reconciled,
            })

            self.write({
                'last_auto_execution': fields.Datetime.now(),
                'last_auto_execution_result': f'{total_reconciled} pagos conciliados',
            })

            # Enviar notificación
            self._send_execution_notification(execution)

            return execution

        except Exception as e:
            _logger.exception("Error en ejecución automática de conciliación")
            execution.write({
                'state': 'error',
                'result_message': str(e),
            })
            return execution

    def _reconcile_public_invoice(self, public_invoice, search_fields):
        """
        Concilia pagos para una factura pública específica.
        - Permite que un pago se use para múltiples órdenes (1 pago → N órdenes)
        - Permite que una orden tenga múltiples pagos (N pagos → 1 orden)
        """
        partner_id = self.public_partner_id.id
        reconciled_count = 0
        reconciled_amount = 0

        # Cache de saldos usados en esta sesión
        payment_used_amounts = {}  # {payment_id: monto_usado}
        order_used_amounts = {}    # {order_id: monto_conciliado}

        # Cargar montos ya conciliados desde BD
        existing_reconciliations = self.env['billing.public.reconciliation'].search([
            ('public_invoice_id', '=', public_invoice.id)
        ])
        for rec in existing_reconciliations:
            if rec.order_id.id not in order_used_amounts:
                order_used_amounts[rec.order_id.id] = 0
            order_used_amounts[rec.order_id.id] += rec.amount

        for order in public_invoice.order_ids:
            # Calcular saldo pendiente de la orden
            order_reconciled = order_used_amounts.get(order.id, 0)
            order_remaining = order.amount_total - order_reconciled

            if order_remaining <= 0:
                _logger.debug(f"Orden {order.name} ya está completamente conciliada")
                continue

            _logger.info(f"Procesando orden {order.name}: Total=${order.amount_total}, Conciliado=${order_reconciled}, Pendiente=${order_remaining}")

            # Buscar pagos usando los campos configurados
            for field_config in search_fields.sorted('sequence'):
                search_value = getattr(order, field_config.field_name, None)
                if not search_value:
                    continue

                # Construir dominio de búsqueda
                domain = field_config.get_search_domain(search_value, partner_id)
                payments = self.env['account.payment'].search(domain)

                for payment in payments:
                    # Si la orden ya está completa, salir
                    if order_remaining <= 0:
                        break

                    # Calcular saldo disponible del pago
                    payment_remaining = self._get_payment_remaining_balance(payment, payment_used_amounts)

                    if payment_remaining <= 0:
                        _logger.debug(f"Pago {payment.id} sin saldo disponible, saltando...")
                        continue

                    # Calcular monto a conciliar: el mínimo entre lo pendiente de la orden y lo disponible del pago
                    amount_to_reconcile = min(order_remaining, payment_remaining)

                    # Crear conciliación
                    try:
                        self.env['billing.public.reconciliation'].create_with_reconciliation({
                            'public_invoice_id': public_invoice.id,
                            'order_id': order.id,
                            'order_amount': order.amount_total,
                            'payment_id': payment.id,
                            'matched_field': field_config.name,
                            'matched_value': str(search_value),
                            'amount': amount_to_reconcile,
                        })
                        reconciled_count += 1
                        reconciled_amount += amount_to_reconcile

                        # Actualizar caches
                        if payment.id not in payment_used_amounts:
                            payment_used_amounts[payment.id] = 0
                        payment_used_amounts[payment.id] += amount_to_reconcile

                        if order.id not in order_used_amounts:
                            order_used_amounts[order.id] = 0
                        order_used_amounts[order.id] += amount_to_reconcile

                        # Actualizar saldo pendiente de la orden
                        order_remaining -= amount_to_reconcile

                        _logger.info(f"Conciliado: Orden {order.name} ↔ Pago {payment.id} = ${amount_to_reconcile} (Orden pendiente: ${order_remaining})")

                    except Exception as e:
                        _logger.warning(f"Error al conciliar orden {order.name} con pago {payment.id}: {e}")

                # Si la orden ya está completa, no buscar en más campos
                if order_remaining <= 0:
                    _logger.info(f"Orden {order.name} completamente conciliada")
                    break

        # Actualizar estado de la factura pública
        public_invoice._update_state()

        return reconciled_count, reconciled_amount

    def _get_payment_remaining_balance(self, payment, session_used_amounts):
        """
        Calcula el saldo disponible de un pago.
        Considera: monto original - conciliaciones existentes - usado en esta sesión.
        """
        # Obtener total ya conciliado en BD para este pago
        existing_reconciliations = self.env['billing.public.reconciliation'].search([
            ('payment_id', '=', payment.id)
        ])
        total_reconciled = sum(existing_reconciliations.mapped('amount'))

        # Agregar lo usado en esta sesión (aún no guardado en BD)
        session_used = session_used_amounts.get(payment.id, 0)

        # Calcular saldo disponible
        remaining = payment.amount - total_reconciled - session_used

        _logger.debug(f"Pago {payment.id}: Total={payment.amount}, Conciliado={total_reconciled}, Sesión={session_used}, Disponible={remaining}")

        return remaining

    def _send_execution_notification(self, execution):
        """
        Envía notificación por email del resultado de la ejecución.
        """
        if not self.auto_notify_email:
            return

        try:
            template_vals = {
                'subject': f'Ejecución Automática - {execution.execution_type.upper()} - {execution.state}',
                'body_html': f'''
                    <p>Se ha completado una ejecución automática:</p>
                    <ul>
                        <li><strong>Tipo:</strong> {dict(execution._fields['execution_type'].selection).get(execution.execution_type)}</li>
                        <li><strong>Estado:</strong> {dict(execution._fields['state'].selection).get(execution.state)}</li>
                        <li><strong>Resultado:</strong> {execution.result_message}</li>
                        <li><strong>Fecha:</strong> {execution.execution_date}</li>
                    </ul>
                ''',
                'email_to': self.auto_notify_email,
            }
            self.env['mail.mail'].create(template_vals).send()
        except Exception:
            pass  # No fallar si no se puede enviar el email

    @api.model
    def _cron_execute_auto_invoice(self):
        """
        Cron para ejecutar facturación automática.
        Se ejecuta según la frecuencia configurada (día específico del mes).
        """
        from datetime import datetime
        now = datetime.now()

        _logger.info("=" * 80)
        _logger.info("[CRON FACTURACION] ========== INICIO CRON ==========")
        _logger.info(f"[CRON FACTURACION] Fecha/Hora actual: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        _logger.info(f"[CRON FACTURACION] Día: {now.day}, Hora: {now.hour}, Minuto: {now.minute}")
        _logger.info("=" * 80)

        configs = self.search([
            ('active', '=', True),
            ('auto_invoice_enabled', '=', True)
        ])

        _logger.info(f"[CRON FACTURACION] Configuraciones activas encontradas: {len(configs)}")

        if not configs:
            _logger.warning("[CRON FACTURACION] No hay configuraciones con facturación automática habilitada")
            return

        for config in configs:
            _logger.info(f"[CRON FACTURACION] --- Procesando config ID={config.id}, Compañía={config.company_id.name} ---")
            _logger.info(f"[CRON FACTURACION] Configurado para: Día {config.invoice_day_of_month} a las {config.invoice_hour}:{config.invoice_minute or 0:02d}")
            _logger.info(f"[CRON FACTURACION] Última ejecución: {config.last_invoice_execution or 'NUNCA'}")

            try:
                should_execute = config._should_execute_invoice_now()
                _logger.info(f"[CRON FACTURACION] ¿Debe ejecutar ahora? {should_execute}")

                if should_execute:
                    _logger.info(f"[CRON FACTURACION] >>> EJECUTANDO FACTURACIÓN para {config.company_id.name}")
                    config._execute_auto_invoice(manual=False)
                    config.write({'last_invoice_execution': fields.Datetime.now()})
                    _logger.info(f"[CRON FACTURACION] >>> FACTURACIÓN COMPLETADA")
                else:
                    _logger.info(f"[CRON FACTURACION] Saltando - No es el momento configurado")

            except Exception as e:
                _logger.exception(f"[CRON FACTURACION] ERROR: {e}")

        _logger.info("[CRON FACTURACION] ========== FIN CRON ==========")

    @api.model
    def _cron_execute_auto_reconciliation(self):
        """
        Cron para ejecutar conciliación automática.
        Se ejecuta según el intervalo configurado.
        Procesa TODAS las facturas públicas pendientes de conciliación.
        """
        from datetime import datetime
        now = datetime.now()

        _logger.info("=" * 80)
        _logger.info("[CRON CONCILIACION] ========== INICIO CRON ==========")
        _logger.info(f"[CRON CONCILIACION] Fecha/Hora actual: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        _logger.info("=" * 80)

        configs = self.search([
            ('active', '=', True),
            ('auto_reconciliation_enabled', '=', True)
        ])

        _logger.info(f"[CRON CONCILIACION] Configuraciones activas encontradas: {len(configs)}")

        if not configs:
            _logger.warning("[CRON CONCILIACION] No hay configuraciones con conciliación automática habilitada")
            return

        for config in configs:
            _logger.info(f"[CRON CONCILIACION] --- Procesando config ID={config.id}, Compañía={config.company_id.name} ---")
            _logger.info(f"[CRON CONCILIACION] Configurado para: cada {config.reconciliation_frequency_number} {config.reconciliation_frequency_type}")
            _logger.info(f"[CRON CONCILIACION] Última ejecución: {config.last_reconciliation_execution or 'NUNCA'}")

            try:
                should_execute = config._should_execute_reconciliation_now()
                _logger.info(f"[CRON CONCILIACION] ¿Debe ejecutar ahora? {should_execute}")

                if should_execute:
                    _logger.info(f"[CRON CONCILIACION] >>> EJECUTANDO CONCILIACIÓN para {config.company_id.name}")
                    config._execute_auto_reconciliation_all(manual=False)
                    config.write({'last_reconciliation_execution': fields.Datetime.now()})
                    _logger.info(f"[CRON CONCILIACION] >>> CONCILIACIÓN COMPLETADA")
                else:
                    _logger.info(f"[CRON CONCILIACION] Saltando - No ha pasado suficiente tiempo desde última ejecución")

            except Exception as e:
                _logger.exception(f"[CRON CONCILIACION] ERROR: {e}")

        _logger.info("[CRON CONCILIACION] ========== FIN CRON ==========")

    def _should_execute_invoice_now(self):
        """
        Determina si debe ejecutarse la facturación ahora.
        La facturación se ejecuta en un día y hora específicos del mes.
        """
        self.ensure_one()
        from datetime import datetime

        if not self.auto_invoice_enabled:
            _logger.debug(f"[SHOULD_EXEC_INV] Config {self.id}: Facturación automática NO habilitada")
            return False

        now = datetime.now()

        # Verificar si es el día y hora configurados
        is_correct_day = now.day == self.invoice_day_of_month
        is_correct_hour = now.hour == self.invoice_hour
        is_correct_minute = now.minute == (self.invoice_minute or 0)

        _logger.debug(f"[SHOULD_EXEC_INV] Config {self.id}: Ahora={now.day}/{now.hour}:{now.minute} vs Config={self.invoice_day_of_month}/{self.invoice_hour}:{self.invoice_minute or 0}")
        _logger.debug(f"[SHOULD_EXEC_INV] Config {self.id}: día_correcto={is_correct_day}, hora_correcta={is_correct_hour}, minuto_correcto={is_correct_minute}")

        if not (is_correct_day and is_correct_hour and is_correct_minute):
            _logger.debug(f"[SHOULD_EXEC_INV] Config {self.id}: NO es el momento configurado")
            return False

        # Verificar que no se haya ejecutado ya este mes
        last_exec = self.last_invoice_execution
        if last_exec:
            # Si ya se ejecutó este mes, no ejecutar de nuevo
            if last_exec.month == now.month and last_exec.year == now.year:
                _logger.debug(f"[SHOULD_EXEC_INV] Config {self.id}: Ya se ejecutó este mes ({last_exec})")
                return False

        _logger.info(f"[SHOULD_EXEC_INV] Config {self.id}: ¡SÍ debe ejecutar! Es el día {self.invoice_day_of_month} a las {self.invoice_hour}:{self.invoice_minute or 0:02d}")
        return True

    def _should_execute_reconciliation_now(self):
        """
        Determina si debe ejecutarse la conciliación ahora.
        Compara con la última ejecución para respetar el intervalo configurado.
        """
        self.ensure_one()
        from datetime import datetime, timedelta

        if not self.auto_reconciliation_enabled:
            _logger.debug(f"[SHOULD_EXEC_REC] Config {self.id}: Conciliación automática NO habilitada")
            return False

        now = datetime.now()
        last_exec = self.last_reconciliation_execution

        # Si nunca se ha ejecutado, ejecutar ahora
        if not last_exec:
            _logger.info(f"[SHOULD_EXEC_REC] Config {self.id}: Primera ejecución - NUNCA se ha ejecutado")
            return True

        # Calcular el intervalo en minutos
        interval_minutes = self._get_interval_minutes(
            self.reconciliation_frequency_type,
            self.reconciliation_frequency_number
        )

        # Verificar si ha pasado suficiente tiempo
        next_execution = last_exec + timedelta(minutes=interval_minutes)
        time_remaining = (next_execution - now).total_seconds() / 60

        _logger.debug(f"[SHOULD_EXEC_REC] Config {self.id}: Intervalo={interval_minutes} min")
        _logger.debug(f"[SHOULD_EXEC_REC] Config {self.id}: Última ejecución={last_exec}")
        _logger.debug(f"[SHOULD_EXEC_REC] Config {self.id}: Próxima ejecución={next_execution}")
        _logger.debug(f"[SHOULD_EXEC_REC] Config {self.id}: Tiempo restante={time_remaining:.1f} min")

        if now >= next_execution:
            _logger.info(f"[SHOULD_EXEC_REC] Config {self.id}: ¡SÍ debe ejecutar! Han pasado los {interval_minutes} minutos configurados")
            return True
        else:
            _logger.debug(f"[SHOULD_EXEC_REC] Config {self.id}: NO ejecutar - faltan {time_remaining:.1f} minutos")
            return False

    def _get_interval_minutes(self, frequency_type, frequency_number):
        """
        Convierte el tipo y número de frecuencia a minutos.
        """
        multipliers = {
            'minutes': 1,
            'hours': 60,
            'days': 60 * 24,
            'weeks': 60 * 24 * 7,
            'months': 60 * 24 * 30,  # Aproximado
        }
        return multipliers.get(frequency_type, 60) * (frequency_number or 1)

    def _execute_auto_reconciliation_all(self, manual=False):
        """
        Ejecuta la conciliación automática para TODAS las facturas públicas pendientes.
        Procesa una factura a la vez, buscando pagos nuevos.
        """
        self.ensure_one()

        _logger.info("[RECONCILIATION ALL] Iniciando conciliación de todas las facturas pendientes")

        execution = self.env['billing.auto.execution'].create({
            'config_id': self.id,
            'execution_type': 'reconciliation',
            'manual': manual,
            'state': 'running',
        })

        try:
            # Buscar TODAS las facturas públicas pendientes de conciliación
            public_invoices = self.env['billing.public.invoice'].search([
                ('company_id', '=', self.company_id.id),
                ('state', 'in', ['invoiced', 'partial']),  # No incluir las ya reconciliadas
            ], order='create_date asc')  # Procesar las más antiguas primero

            if not public_invoices:
                execution.write({
                    'state': 'done',
                    'result_message': 'No hay facturas Público en General pendientes de conciliación.',
                })
                _logger.info("[RECONCILIATION ALL] No hay facturas pendientes")
                return execution

            _logger.info(f"[RECONCILIATION ALL] Encontradas {len(public_invoices)} facturas pendientes")

            total_reconciled = 0
            total_amount = 0
            invoices_processed = 0
            errors = []

            # Obtener campos de búsqueda activos
            search_fields = self.env['billing.reconciliation.field'].get_active_fields(self.company_id.id)

            # Procesar cada factura
            for public_invoice in public_invoices:
                _logger.info(f"[RECONCILIATION ALL] Procesando factura {public_invoice.name}")
                try:
                    reconciled_count, reconciled_amount = self._reconcile_public_invoice(
                        public_invoice, search_fields
                    )
                    total_reconciled += reconciled_count
                    total_amount += reconciled_amount
                    invoices_processed += 1

                    if reconciled_count > 0:
                        _logger.info(f"[RECONCILIATION ALL] {public_invoice.name}: {reconciled_count} conciliaciones, ${reconciled_amount:,.2f}")
                except Exception as e:
                    error_msg = f"{public_invoice.name}: {str(e)}"
                    errors.append(error_msg)
                    _logger.error(f"[RECONCILIATION ALL] Error en {public_invoice.name}: {e}")

            # Resultado
            result_msg = f'Procesadas {invoices_processed} facturas. Se conciliaron {total_reconciled} pagos por ${total_amount:,.2f}'
            if errors:
                result_msg += f'. Errores: {len(errors)}'

            execution.write({
                'state': 'done' if not errors else 'error',
                'result_message': result_msg,
                'orders_processed': total_reconciled,
            })

            self.write({
                'last_auto_execution': fields.Datetime.now(),
                'last_auto_execution_result': f'{total_reconciled} pagos conciliados en {invoices_processed} facturas',
            })

            # Enviar notificación si hubo conciliaciones
            if total_reconciled > 0:
                self._send_execution_notification(execution)

            _logger.info(f"[RECONCILIATION ALL] Completado: {result_msg}")
            return execution

        except Exception as e:
            _logger.exception("[RECONCILIATION ALL] Error general")
            execution.write({
                'state': 'error',
                'result_message': str(e),
            })
            return execution

    # Legacy method for compatibility
    def _should_execute_today(self):
        """Método legacy - usar _should_execute_invoice_now o _should_execute_reconciliation_now"""
        return self._should_execute_invoice_now()
