# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MercadolibreBillingCreateInvoiceWizard(models.TransientModel):
    _name = 'mercadolibre.billing.create.invoice.wizard'
    _description = 'Wizard para Crear Factura Agrupada'

    invoice_group_id = fields.Many2one(
        'mercadolibre.billing.invoice',
        string='Documento Legal',
        required=True,
        ondelete='cascade'
    )

    # Indica si es nota de crédito
    is_credit_note = fields.Boolean(
        related='invoice_group_id.is_credit_note',
        string='Es Nota de Crédito'
    )

    # Información calculada
    total_details = fields.Integer(
        string='Total Detalles',
        compute='_compute_summary'
    )
    details_without_po = fields.Integer(
        string='Detalles sin PO',
        compute='_compute_summary'
    )
    pos_to_confirm = fields.Integer(
        string='POs por Confirmar',
        compute='_compute_summary'
    )
    pos_confirmed = fields.Integer(
        string='POs Confirmadas',
        compute='_compute_summary'
    )
    total_amount = fields.Monetary(
        string='Monto Total',
        compute='_compute_summary',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='invoice_group_id.currency_id'
    )

    # Flags de advertencia
    needs_create_pos = fields.Boolean(
        string='Necesita Crear POs',
        compute='_compute_summary'
    )
    needs_confirm_pos = fields.Boolean(
        string='Necesita Confirmar POs',
        compute='_compute_summary'
    )

    warning_message = fields.Text(
        string='Advertencia',
        compute='_compute_summary'
    )

    @api.depends('invoice_group_id')
    def _compute_summary(self):
        for wizard in self:
            if not wizard.invoice_group_id:
                wizard.total_details = 0
                wizard.details_without_po = 0
                wizard.pos_to_confirm = 0
                wizard.pos_confirmed = 0
                wizard.total_amount = 0
                wizard.needs_create_pos = False
                wizard.needs_confirm_pos = False
                wizard.warning_message = ''
                continue

            inv = wizard.invoice_group_id
            details = inv.detail_ids

            # Contar detalles
            wizard.total_details = len(details)
            wizard.total_amount = inv.total_amount

            # Las notas de crédito no requieren POs
            if inv.is_credit_note:
                wizard.details_without_po = 0
                wizard.pos_to_confirm = 0
                wizard.pos_confirmed = 0
                wizard.needs_create_pos = False
                wizard.needs_confirm_pos = False
                wizard.warning_message = _(
                    '✓ Nota de Crédito - Se creará directamente sin orden de compra.'
                )
                continue

            # Solo para facturas normales (no notas de crédito)
            # Detalles sin PO
            without_po = details.filtered(lambda d: not d.purchase_order_id)
            wizard.details_without_po = len(without_po)

            # POs existentes
            pos = details.filtered(lambda d: d.purchase_order_id).mapped('purchase_order_id')
            draft_pos = pos.filtered(lambda po: po.state in ('draft', 'sent', 'to approve'))
            confirmed_pos = pos.filtered(lambda po: po.state not in ('draft', 'sent', 'to approve', 'cancel'))

            wizard.pos_to_confirm = len(draft_pos)
            wizard.pos_confirmed = len(confirmed_pos)

            # Flags
            wizard.needs_create_pos = wizard.details_without_po > 0
            wizard.needs_confirm_pos = wizard.pos_to_confirm > 0

            # Mensaje de advertencia
            warnings = []
            if wizard.needs_create_pos:
                warnings.append(_(
                    '⚠️ Se crearán %d órdenes de compra automáticamente.'
                ) % wizard.details_without_po)
            if wizard.needs_confirm_pos:
                warnings.append(_(
                    '⚠️ Se confirmarán %d órdenes de compra automáticamente.'
                ) % wizard.pos_to_confirm)

            if warnings:
                wizard.warning_message = '\n'.join(warnings)
            else:
                wizard.warning_message = _('✓ Todas las órdenes de compra están listas.')

    def action_create_invoice(self):
        """Crea la factura o nota de crédito, creando y confirmando POs si es necesario"""
        self.ensure_one()

        inv = self.invoice_group_id

        # Verificar si ya existe una factura/nota de crédito
        if inv.vendor_bill_id:
            doc_type = 'nota de crédito' if inv.is_credit_note else 'factura de proveedor'
            raise UserError(_(
                'Ya existe una %s para este documento legal: %s'
            ) % (doc_type, inv.vendor_bill_id.name))

        # Obtener configuración
        config = self.env['mercadolibre.billing.sync.config'].sudo().search([
            ('account_id', '=', inv.account_id.id)
        ], limit=1)

        # Si es nota de crédito, crear directamente sin POs
        if inv.is_credit_note:
            return inv._create_invoice_internal(config)

        # Para facturas normales, crear y confirmar POs primero
        # 1. Crear POs faltantes
        details_without_po = inv.detail_ids.filtered(lambda d: not d.purchase_order_id and d.state == 'draft')
        if details_without_po:
            for detail in details_without_po:
                try:
                    detail.action_create_purchase_order()
                except Exception as e:
                    raise UserError(_(
                        'Error al crear PO para detalle %s: %s'
                    ) % (detail.ml_detail_id, str(e)))

        # 2. Confirmar POs pendientes
        all_pos = inv.detail_ids.mapped('purchase_order_id')
        draft_pos = all_pos.filtered(lambda po: po.state in ('draft', 'sent', 'to approve'))
        if draft_pos:
            for po in draft_pos:
                try:
                    po.button_confirm()
                except Exception as e:
                    raise UserError(_(
                        'Error al confirmar PO %s: %s'
                    ) % (po.name, str(e)))

        # 3. Ahora crear la factura
        return inv._create_invoice_internal(config)
