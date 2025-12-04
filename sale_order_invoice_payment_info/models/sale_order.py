from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Campos computados para información de facturas y pagos
    invoice_payment_info_ids = fields.One2many(
        'sale.order.invoice.payment.info',
        'order_id',
        string='Información de Facturas y Pagos',
        compute='_compute_invoice_payment_info',
        store=False
    )

    invoice_payment_count = fields.Integer(
        string='Número de Registros',
        compute='_compute_invoice_payment_info'
    )

    # Campos para el sistema de comisiones
    commission_paid = fields.Boolean(
        string='Comisión Pagada',
        default=False,
        help='Indica si la comisión de esta venta ya fue pagada al vendedor'
    )
    commission_paid_date = fields.Date(
        string='Fecha de Comisión Pagada',
        help='Fecha en que se marcó la comisión como pagada'
    )
    commission_invalid = fields.Boolean(
        string='Comisión No Válida',
        default=False,
        help='Indica si esta venta fue marcada como comisión no válida'
    )

    # Campos para mostrar facturas y pagos en vista tree
    invoice_names = fields.Char(
        string='Facturas',
        compute='_compute_invoice_payment_names',
        store=False
    )
    payment_names = fields.Char(
        string='Pagos',
        compute='_compute_invoice_payment_names',
        store=False
    )

    # Campo computado para fecha de pago válida (la más reciente de las facturas pagadas)
    payment_valid_date = fields.Date(
        string='Fecha de Pago Válida',
        compute='_compute_payment_valid_date',
        store=True,
        help='Fecha de pago más reciente de las facturas relacionadas a esta orden'
    )

    @api.depends('invoice_ids', 'invoice_ids.payment_state')
    def _compute_invoice_payment_info(self):
        """
        Calcula la información de facturas y pagos relacionados a la orden de venta
        """
        InvoicePaymentInfo = self.env['sale.order.invoice.payment.info']

        for order in self:
            # Limpiar registros anteriores para este pedido
            existing_records = InvoicePaymentInfo.search([('order_id', '=', order.id)])
            existing_records.unlink()

            invoice_payment_data = []

            # Obtener todas las facturas relacionadas
            invoices = order.invoice_ids.filtered(lambda inv: inv.move_type in ('out_invoice', 'out_refund'))

            for invoice in invoices:
                # Para cada factura, obtener los pagos relacionados
                payments = self._get_payments_for_invoice(invoice)

                if payments:
                    for payment in payments:
                        # Crear un registro por cada pago
                        vals = {
                            'order_id': order.id,
                            'invoice_id': invoice.id,
                            'invoice_name': invoice.name,
                            'invoice_date': invoice.invoice_date,
                            'invoice_amount_total': invoice.amount_total,
                            'invoice_amount_residual': invoice.amount_residual,
                            'invoice_partner_id': invoice.partner_id.id,
                            'invoice_state': invoice.state,
                            'invoice_payment_state': invoice.payment_state,
                            'payment_id': payment['payment_id'],
                            'payment_name': payment['payment_name'],
                            'payment_ref': payment['payment_ref'],
                            'payment_date': payment['payment_date'],
                            'payment_amount': payment['payment_amount'],
                            'payment_create_date': payment['payment_create_date'],
                            'reconcile_date': payment['reconcile_date'],
                        }
                        invoice_payment_data.append((0, 0, vals))
                else:
                    # Si no hay pagos, crear un registro solo con la información de la factura
                    vals = {
                        'order_id': order.id,
                        'invoice_id': invoice.id,
                        'invoice_name': invoice.name,
                        'invoice_date': invoice.invoice_date,
                        'invoice_amount_total': invoice.amount_total,
                        'invoice_amount_residual': invoice.amount_residual,
                        'invoice_partner_id': invoice.partner_id.id,
                        'invoice_state': invoice.state,
                        'invoice_payment_state': invoice.payment_state,
                    }
                    invoice_payment_data.append((0, 0, vals))

            order.invoice_payment_info_ids = invoice_payment_data
            order.invoice_payment_count = len(invoice_payment_data)

    def _get_payments_for_invoice(self, invoice):
        """
        Obtiene todos los pagos relacionados a una factura a través de las conciliaciones
        """
        payments_data = []

        # Obtener las líneas de movimiento de la factura que son de tipo receivable/payable
        invoice_lines = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
        )

        for line in invoice_lines:
            # Obtener las conciliaciones parciales donde esta línea está involucrada
            partial_reconciles = line.matched_debit_ids | line.matched_credit_ids

            for reconcile in partial_reconciles:
                # Determinar cuál es la línea del pago (la que no es de la factura)
                payment_line = False
                if reconcile.debit_move_id.id != line.id:
                    payment_line = reconcile.debit_move_id
                elif reconcile.credit_move_id.id != line.id:
                    payment_line = reconcile.credit_move_id

                if payment_line and payment_line.payment_id:
                    payment = payment_line.payment_id

                    # Evitar duplicados
                    if not any(p['payment_id'] == payment.id for p in payments_data):
                        payments_data.append({
                            'payment_id': payment.id,
                            'payment_name': payment.name or '',
                            'payment_ref': payment.ref or '',
                            'payment_date': payment.date,
                            'payment_amount': payment.amount,
                            'payment_create_date': payment.create_date,
                            'reconcile_date': reconcile.max_date or reconcile.create_date.date() if reconcile.create_date else False,
                        })

        return payments_data

    @api.depends('invoice_ids', 'invoice_ids.name')
    def _compute_invoice_payment_names(self):
        """
        Calcula los nombres de facturas y pagos para mostrar en la vista tree
        """
        for order in self:
            # Obtener facturas
            invoices = order.invoice_ids.filtered(lambda inv: inv.move_type in ('out_invoice', 'out_refund'))
            invoice_list = [inv.name for inv in invoices if inv.name]
            order.invoice_names = ', '.join(invoice_list) if invoice_list else ''

            # Obtener pagos
            payment_list = []
            for invoice in invoices:
                payments = self._get_payments_for_invoice(invoice)
                for payment in payments:
                    if payment['payment_name'] and payment['payment_name'] not in payment_list:
                        payment_list.append(payment['payment_name'])

            order.payment_names = ', '.join(payment_list) if payment_list else ''

    @api.depends('invoice_ids', 'invoice_ids.payment_state', 'invoice_ids.line_ids.matched_debit_ids', 'invoice_ids.line_ids.matched_credit_ids')
    def _compute_payment_valid_date(self):
        """
        Calcula la fecha de pago válida como la fecha más reciente de los pagos aplicados a las facturas
        """
        for order in self:
            payment_dates = []

            # Obtener todas las facturas de cliente (no notas de crédito por ahora)
            invoices = order.invoice_ids.filtered(lambda inv: inv.move_type == 'out_invoice' and inv.state == 'posted')

            for invoice in invoices:
                # Solo considerar facturas que están pagadas o parcialmente pagadas
                if invoice.payment_state in ['paid', 'in_payment', 'partial']:
                    # Obtener las fechas de los pagos
                    payments = self._get_payments_for_invoice(invoice)
                    for payment in payments:
                        if payment.get('payment_date'):
                            payment_dates.append(payment['payment_date'])
                        # También considerar la fecha de conciliación
                        if payment.get('reconcile_date'):
                            payment_dates.append(payment['reconcile_date'])

            # Establecer la fecha más reciente como fecha de pago válida
            if payment_dates:
                order.payment_valid_date = max(payment_dates)
            else:
                order.payment_valid_date = False

    def action_mark_commission_paid(self):
        """
        Marca las comisiones como pagadas para las órdenes seleccionadas
        """
        for order in self:
            order.write({
                'commission_paid': True,
                'commission_paid_date': fields.Date.today()
            })
        return True

    def action_unmark_commission_paid(self):
        """
        Desmarca las comisiones como pagadas
        """
        for order in self:
            order.write({
                'commission_paid': False,
                'commission_paid_date': False
            })
        return True


class SaleOrderInvoicePaymentInfo(models.TransientModel):
    _name = 'sale.order.invoice.payment.info'
    _description = 'Información de Facturas y Pagos de Orden de Venta'
    _order = 'invoice_date desc, payment_date desc'

    # Relación con la orden de venta
    order_id = fields.Many2one('sale.order', string='Orden de Venta', required=True, ondelete='cascade')

    # Información de la factura
    invoice_id = fields.Many2one('account.move', string='Factura', ondelete='cascade')
    invoice_name = fields.Char(string='Número de Factura')
    invoice_date = fields.Date(string='Fecha de Factura')
    invoice_amount_total = fields.Monetary(string='Importe Total', currency_field='currency_id')
    invoice_amount_residual = fields.Monetary(string='Importe Pendiente', currency_field='currency_id')
    invoice_partner_id = fields.Many2one('res.partner', string='Cliente Facturado')
    invoice_state = fields.Selection([
        ('draft', 'Borrador'),
        ('posted', 'Contabilizado'),
        ('cancel', 'Cancelado')
    ], string='Estado de Factura')
    invoice_payment_state = fields.Selection([
        ('not_paid', 'No Pagado'),
        ('in_payment', 'En Pago'),
        ('paid', 'Pagado'),
        ('partial', 'Parcialmente Pagado'),
        ('reversed', 'Revertido'),
        ('invoicing_legacy', 'Facturación Heredada')
    ], string='Estado de Pago')

    # Información del pago
    payment_id = fields.Many2one('account.payment', string='Pago')
    payment_name = fields.Char(string='Nombre del Pago')
    payment_ref = fields.Char(string='Referencia del Pago')
    payment_date = fields.Date(string='Fecha del Pago')
    payment_amount = fields.Monetary(string='Monto del Pago', currency_field='currency_id')
    payment_create_date = fields.Datetime(string='Fecha de Creación del Pago')
    reconcile_date = fields.Date(string='Fecha de Conciliación')

    # Campo de moneda
    currency_id = fields.Many2one('res.currency', string='Moneda',
                                   related='order_id.currency_id', readonly=True)

    # Campos computados para las líneas de producto
    invoice_line_ids = fields.One2many(related='invoice_id.invoice_line_ids', string='Líneas de Factura')
