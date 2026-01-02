# -*- coding: utf-8 -*-
"""
Modelo para registro de conciliaciones de facturas Público en General.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BillingPublicReconciliation(models.Model):
    _name = 'billing.public.reconciliation'
    _description = 'Conciliación de Factura Público en General'
    _order = 'reconcile_date desc'

    public_invoice_id = fields.Many2one(
        'billing.public.invoice',
        string='Factura Público en General',
        required=True,
        ondelete='cascade',
        index=True
    )

    order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=True,
        ondelete='restrict',
        index=True
    )

    order_name = fields.Char(
        related='order_id.name',
        string='Número Orden',
        store=True
    )

    order_amount = fields.Monetary(
        string='Monto Orden',
        currency_field='currency_id'
    )

    payment_id = fields.Many2one(
        'account.payment',
        string='Pago',
        required=True,
        ondelete='restrict',
        index=True
    )

    payment_name = fields.Char(
        related='payment_id.name',
        string='Número Pago',
        store=True
    )

    payment_amount = fields.Monetary(
        related='payment_id.amount',
        string='Monto Pago',
        store=True,
        currency_field='currency_id'
    )

    matched_field = fields.Char(
        string='Campo de Match',
        help='Nombre del campo que hizo la coincidencia'
    )

    matched_value = fields.Char(
        string='Valor de Match',
        help='Valor que coincidió entre la orden y el pago'
    )

    amount = fields.Monetary(
        string='Monto Conciliado',
        required=True,
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        related='public_invoice_id.currency_id',
        string='Moneda',
        store=True
    )

    difference = fields.Monetary(
        compute='_compute_difference',
        string='Diferencia',
        store=True,
        currency_field='currency_id',
        help='Diferencia entre monto de pago y monto de orden'
    )

    reconcile_date = fields.Datetime(
        string='Fecha Conciliación',
        default=fields.Datetime.now,
        required=True
    )

    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        required=True
    )

    notes = fields.Text(string='Notas')

    company_id = fields.Many2one(
        related='public_invoice_id.company_id',
        string='Compañía',
        store=True
    )

    is_reconciled = fields.Boolean(
        string='Conciliación Contable Realizada',
        default=False,
        help='Indica si la conciliación contable real se realizó en Odoo'
    )

    reconciliation_error = fields.Text(
        string='Error de Conciliación',
        readonly=True,
        help='Mensaje de error si la conciliación contable falló'
    )

    @api.depends('order_amount', 'payment_amount')
    def _compute_difference(self):
        for record in self:
            record.difference = (record.payment_amount or 0) - (record.order_amount or 0)

    def _perform_accounting_reconciliation(self):
        """
        Realiza la conciliación contable real entre el pago y la factura.
        Retorna True si fue exitosa, False si falló.
        """
        self.ensure_one()

        _logger.info("=" * 60)
        _logger.info(f"[ACCOUNTING RECONCILIATION] Iniciando conciliación contable")
        _logger.info(f"[ACCOUNTING RECONCILIATION] Pago: {self.payment_id.id}")
        _logger.info(f"[ACCOUNTING RECONCILIATION] Factura Pública: {self.public_invoice_id.name}")
        _logger.info("=" * 60)

        try:
            # Obtener la factura contable
            invoice = self.public_invoice_id.invoice_id
            if not invoice:
                raise UserError(_('La factura pública no tiene una factura contable asociada.'))

            _logger.info(f"[ACCOUNTING RECONCILIATION] Factura contable: {invoice.name} (ID: {invoice.id})")
            _logger.info(f"[ACCOUNTING RECONCILIATION] Estado factura: {invoice.state}")
            _logger.info(f"[ACCOUNTING RECONCILIATION] Estado pago factura: {invoice.payment_state}")
            _logger.info(f"[ACCOUNTING RECONCILIATION] Monto residual: {invoice.amount_residual}")

            # Verificar que la factura esté publicada
            if invoice.state != 'posted':
                raise UserError(_('La factura debe estar publicada para poder conciliar.'))

            # Obtener el pago
            payment = self.payment_id
            _logger.info(f"[ACCOUNTING RECONCILIATION] Monto pago: {payment.amount}")

            # Verificar que el pago esté publicado
            if payment.move_id.state != 'posted':
                raise UserError(_('El pago debe estar publicado para poder conciliar.'))

            # Obtener las líneas de cuenta por cobrar de la factura
            invoice_receivable_lines = invoice.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
                and not l.reconciled
            )

            _logger.info(f"[ACCOUNTING RECONCILIATION] Líneas por cobrar de factura: {len(invoice_receivable_lines)}")
            for line in invoice_receivable_lines:
                _logger.info(f"  - Línea {line.id}: Cuenta {line.account_id.code}, Débito: {line.debit}, Crédito: {line.credit}, Residual: {line.amount_residual}")

            if not invoice_receivable_lines:
                raise UserError(_('No hay líneas pendientes de conciliar en la factura.'))

            # Obtener las líneas de cuenta por cobrar del pago
            payment_receivable_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
                and not l.reconciled
            )

            _logger.info(f"[ACCOUNTING RECONCILIATION] Líneas por cobrar del pago: {len(payment_receivable_lines)}")
            for line in payment_receivable_lines:
                _logger.info(f"  - Línea {line.id}: Cuenta {line.account_id.code}, Débito: {line.debit}, Crédito: {line.credit}, Residual: {line.amount_residual}")

            if not payment_receivable_lines:
                raise UserError(_('No hay líneas pendientes de conciliar en el pago.'))

            # Verificar que las cuentas coincidan
            invoice_account = invoice_receivable_lines[0].account_id
            payment_account = payment_receivable_lines[0].account_id

            if invoice_account != payment_account:
                _logger.warning(
                    f"[ACCOUNTING RECONCILIATION] Cuentas diferentes: "
                    f"Factura={invoice_account.code}, Pago={payment_account.code}"
                )
                # En algunos casos pueden ser diferentes, intentamos de todos modos

            # Realizar la conciliación
            lines_to_reconcile = invoice_receivable_lines + payment_receivable_lines
            _logger.info(f"[ACCOUNTING RECONCILIATION] Intentando conciliar {len(lines_to_reconcile)} líneas...")

            # Usar el método de conciliación de Odoo
            lines_to_reconcile.reconcile()

            _logger.info("[ACCOUNTING RECONCILIATION] ¡Conciliación exitosa!")

            # Verificar el resultado
            invoice.invalidate_recordset(['payment_state', 'amount_residual'])
            _logger.info(f"[ACCOUNTING RECONCILIATION] Nuevo estado pago factura: {invoice.payment_state}")
            _logger.info(f"[ACCOUNTING RECONCILIATION] Nuevo monto residual: {invoice.amount_residual}")

            self.write({
                'is_reconciled': True,
                'reconciliation_error': False,
            })

            return True

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"[ACCOUNTING RECONCILIATION] Error: {error_msg}")
            self.write({
                'is_reconciled': False,
                'reconciliation_error': error_msg,
            })
            return False

    @api.model
    def create_with_reconciliation(self, vals):
        """
        Crea el registro de conciliación SOLO si la conciliación contable es exitosa.
        """
        _logger.info(f"[RECONCILIATION] Intentando crear conciliación con vals: {vals}")

        # Crear el registro temporalmente
        record = self.create(vals)

        # Intentar la conciliación contable
        success = record._perform_accounting_reconciliation()

        if not success:
            # Si falló, eliminar el registro y lanzar error
            error_msg = record.reconciliation_error or _('Error desconocido en conciliación contable')
            record.unlink()
            _logger.error(f"[RECONCILIATION] Conciliación fallida, registro eliminado: {error_msg}")
            raise UserError(_(
                'No se pudo realizar la conciliación contable:\n\n%s\n\n'
                'El registro NO fue creado.'
            ) % error_msg)

        _logger.info(f"[RECONCILIATION] Conciliación exitosa, registro creado: {record.id}")
        return record

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Actualizar estado de la factura pública
        for record in records:
            record.public_invoice_id._update_state()
        return records

    def unlink(self):
        public_invoices = self.mapped('public_invoice_id')
        result = super().unlink()
        # Actualizar estado de las facturas públicas
        for invoice in public_invoices:
            invoice._update_state()
        return result

    def action_view_order(self):
        """Ver la orden de venta"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Orden de Venta'),
            'res_model': 'sale.order',
            'res_id': self.order_id.id,
            'view_mode': 'form',
        }

    def action_view_payment(self):
        """Ver el pago"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pago'),
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
        }
