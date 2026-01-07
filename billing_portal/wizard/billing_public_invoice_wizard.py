# -*- coding: utf-8 -*-
"""
Wizard para crear facturas a Público en General.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date


class BillingPublicInvoiceWizard(models.TransientModel):
    _name = 'billing.public.invoice.wizard'
    _description = 'Crear Factura Público en General'

    date_from = fields.Date(
        string='Desde',
        required=True,
        default=lambda self: date.today().replace(day=1),
        help='Fecha de inicio del período a facturar'
    )

    date_to = fields.Date(
        string='Hasta',
        required=True,
        default=fields.Date.today,
        help='Fecha de fin del período a facturar'
    )

    config_id = fields.Many2one(
        'billing.public.config',
        string='Configuración',
        required=False,
        help='Configuración de Público en General a usar'
    )

    config_missing = fields.Boolean(
        string='Falta Configuración',
        default=True
    )

    # Preview de órdenes
    order_ids = fields.Many2many(
        'sale.order',
        'billing_public_wizard_order_rel',
        'wizard_id',
        'order_id',
        string='Órdenes a Facturar'
    )

    order_count = fields.Integer(
        string='# Órdenes'
    )

    total_amount = fields.Monetary(
        string='Monto Total',
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda'
    )

    preview_done = fields.Boolean(
        string='Vista Previa Realizada',
        default=False
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Configuración
        config = self.env['billing.public.config'].get_config()
        if config:
            res['config_id'] = config.id
            res['config_missing'] = False
        else:
            res['config_missing'] = True
        # Moneda
        res['currency_id'] = self.env.company.currency_id.id
        return res

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError(_('La fecha "Desde" debe ser anterior o igual a la fecha "Hasta".'))

    def _search_eligible_orders(self):
        """
        Busca órdenes elegibles para facturación a Público en General.

        NOTA: Los productos excluidos solo aplican para el portal del cliente,
        NO para la factura Público en General. Aquí se incluyen TODAS las órdenes
        pendientes de facturar.
        """
        self.ensure_one()

        if not self.date_from or not self.date_to:
            return self.env['sale.order']

        # Buscar órdenes elegibles
        domain = [
            ('company_id', '=', self.company_id.id),
            ('date_order', '>=', self.date_from),
            ('date_order', '<=', self.date_to),
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
            if not self.config_id.is_ml_status_allowed(order.ml_shipment_status):
                continue

            eligible_orders |= order

        return eligible_orders

    def action_preview(self):
        """Genera la vista previa de órdenes a facturar."""
        self.ensure_one()

        # Validar que exista configuración
        if not self.config_id:
            raise UserError(_(
                'No hay configuración de Público en General.\n\n'
                'Vaya a: Portal Facturación → Configuración → Público en General\n'
                'y cree una configuración antes de continuar.'
            ))

        if not self.config_id.public_partner_id:
            raise UserError(_(
                'La configuración no tiene un cliente Público en General asignado.\n\n'
                'Vaya a: Portal Facturación → Configuración → Público en General\n'
                'y seleccione el cliente.'
            ))

        # Buscar órdenes elegibles
        eligible_orders = self._search_eligible_orders()

        if not eligible_orders:
            raise UserError(_(
                'No se encontraron órdenes elegibles para facturación en el período seleccionado.\n\n'
                'Verifique que:\n'
                '- Las órdenes estén confirmadas\n'
                '- No estén completamente facturadas\n'
                '- No contengan productos excluidos\n'
                '- No tengan una solicitud de facturación completada\n'
                '- Si tienen envío ML, esté entregado'
            ))

        # Actualizar el wizard con los resultados
        self.write({
            'order_ids': [(6, 0, eligible_orders.ids)],
            'order_count': len(eligible_orders),
            'total_amount': sum(eligible_orders.mapped('amount_total')),
            'preview_done': True,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_create_invoice(self):
        """Crea la factura unificada a Público en General."""
        self.ensure_one()

        if not self.order_ids:
            raise UserError(_('No hay órdenes para facturar.'))

        if not self.config_id:
            raise UserError(_('Debe configurar los datos de Público en General.'))

        if not self.config_id.public_partner_id:
            raise UserError(_('Debe configurar el cliente Público en General.'))

        # Crear el registro de factura pública
        public_invoice = self.env['billing.public.invoice'].create({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'order_ids': [(6, 0, self.order_ids.ids)],
            'company_id': self.company_id.id,
        })

        # Crear la factura usando el método estándar de Odoo
        invoice = self._create_consolidated_invoice()

        # Asociar factura al registro
        public_invoice.write({
            'invoice_id': invoice.id,
            'state': 'invoiced',
        })

        # Publicar factura automáticamente si está configurado
        if self.config_id.auto_post_invoice and invoice.state == 'draft':
            invoice.action_post()

        # Mostrar la factura creada
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura Público en General'),
            'res_model': 'billing.public.invoice',
            'res_id': public_invoice.id,
            'view_mode': 'form',
        }

    def _create_consolidated_invoice(self):
        """
        Crea una factura consolidada con todas las líneas de las órdenes.
        """
        self.ensure_one()

        partner = self.config_id.public_partner_id

        # Preparar valores de la factura
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'journal_id': self.config_id.journal_id.id if self.config_id.journal_id else False,
            'company_id': self.company_id.id,
            'invoice_line_ids': [],
            'narration': self._get_invoice_narration(),
        }

        # Agregar datos fiscales si están configurados
        if self.config_id.uso_cfdi_id:
            invoice_vals['uso_cfdi_id'] = self.config_id.uso_cfdi_id.id
        if self.config_id.forma_pago_id:
            invoice_vals['forma_pago_id'] = self.config_id.forma_pago_id.id
        if self.config_id.metodo_pago:
            invoice_vals['methodo_pago'] = self.config_id.metodo_pago

        # Agregar líneas de factura desde las órdenes
        line_vals = []
        for order in self.order_ids:
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

        if not line_vals:
            raise UserError(_('No hay líneas para facturar en las órdenes seleccionadas.'))

        invoice_vals['invoice_line_ids'] = line_vals

        # Crear la factura
        invoice = self.env['account.move'].create(invoice_vals)

        return invoice

    def _get_invoice_narration(self):
        """Genera las notas de la factura con referencias de las órdenes."""
        lines = [_('Factura Público en General')]
        lines.append(f"Período: {self.date_from} a {self.date_to}")
        lines.append('')
        lines.append(_('Órdenes incluidas:'))
        for order in self.order_ids[:50]:  # Limitar a 50 para no hacer muy larga la nota
            ref_parts = [order.name]
            if order.client_order_ref:
                ref_parts.append(f"Ref: {order.client_order_ref}")
            if order.ml_order_id:
                ref_parts.append(f"ML: {order.ml_order_id}")
            lines.append(' | '.join(ref_parts))

        if len(self.order_ids) > 50:
            lines.append(f"... y {len(self.order_ids) - 50} órdenes más")

        return '\n'.join(lines)
