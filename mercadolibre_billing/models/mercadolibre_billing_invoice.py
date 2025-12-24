# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadoliBillingInvoice(models.Model):
    _name = 'mercadolibre.billing.invoice'
    _description = 'Factura de MercadoLibre/MercadoPago'
    _order = 'legal_document_number desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Número de Factura',
        compute='_compute_name',
        store=True
    )

    # Relaciones
    period_id = fields.Many2one(
        'mercadolibre.billing.period',
        string='Periodo',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML/MP',
        related='period_id.account_id',
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='period_id.company_id',
        store=True,
        readonly=True
    )
    billing_group = fields.Selection(
        related='period_id.billing_group',
        store=True,
        readonly=True
    )

    # Información de la factura
    legal_document_number = fields.Char(
        string='Número de Factura Legal',
        required=True,
        index=True
    )
    ml_document_id = fields.Char(
        string='Document ID ML',
        index=True
    )
    legal_document_status = fields.Char(
        string='Estado del Documento'
    )

    # Detalles de la factura
    detail_ids = fields.One2many(
        'mercadolibre.billing.detail',
        'invoice_group_id',
        string='Detalles'
    )

    # Contadores
    detail_count = fields.Integer(
        string='Cantidad de Detalles',
        compute='_compute_counts',
        store=True
    )

    # Montos
    total_amount = fields.Monetary(
        string='Total',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )

    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('complete', 'Completo'),
        ('processing', 'Procesando'),
        ('done', 'Procesado')
    ], string='Estado', default='draft', tracking=True)

    # Factura de proveedor generada
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Factura de Proveedor',
        ondelete='restrict'
    )

    # PDF de MercadoLibre
    ml_pdf_file_id = fields.Char(
        string='File ID PDF ML',
        help='ID del archivo PDF en MercadoLibre para descargar'
    )
    ml_pdf_attachment_id = fields.Many2one(
        'ir.attachment',
        string='PDF Adjunto',
        ondelete='set null'
    )

    _sql_constraints = [
        ('legal_document_number_period_uniq',
         'unique(legal_document_number, period_id)',
         'Esta factura ya existe en el periodo.')
    ]

    @api.depends('legal_document_number')
    def _compute_name(self):
        for record in self:
            record.name = record.legal_document_number or 'Nueva Factura'

    @api.depends('detail_ids')
    def _compute_counts(self):
        for record in self:
            record.detail_count = len(record.detail_ids)

    @api.depends('detail_ids.detail_amount')
    def _compute_totals(self):
        for record in self:
            record.total_amount = sum(record.detail_ids.mapped('detail_amount'))

    def action_mark_complete(self):
        """Marca la factura como completa (todos los detalles descargados)"""
        self.write({'state': 'complete'})

    def action_view_details(self):
        """Ver detalles de la factura"""
        self.ensure_one()
        return {
            'name': _('Detalles de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.billing.detail',
            'view_mode': 'tree,form',
            'domain': [('invoice_group_id', '=', self.id)],
            'context': {'default_invoice_group_id': self.id}
        }

    def action_create_grouped_invoice(self):
        """
        Crea una factura de proveedor agrupando todas las POs
        de los detalles asociados a este documento legal
        """
        self.ensure_one()

        # Verificar si ya existe una factura
        if self.vendor_bill_id:
            raise UserError(_(
                'Ya existe una factura de proveedor para este documento legal: %s'
            ) % self.vendor_bill_id.name)

        # Obtener configuración
        config = self.env['mercadolibre.billing.sync.config'].sudo().search([
            ('account_id', '=', self.account_id.id)
        ], limit=1)

        # Validar que todos los detalles tengan PO
        details_without_po = self.detail_ids.filtered(lambda d: not d.purchase_order_id)
        if details_without_po:
            raise UserError(_(
                'No todos los detalles tienen orden de compra creada.\n'
                'Detalles sin PO: %s\n'
                'Por favor cree las órdenes de compra primero.'
            ) % ', '.join(details_without_po.mapped('ml_detail_id')))

        # Obtener todas las POs
        purchase_orders = self.detail_ids.mapped('purchase_order_id')

        if not purchase_orders:
            raise UserError(_('No hay órdenes de compra para procesar.'))

        # Validar que todas las POs estén confirmadas
        draft_pos = purchase_orders.filtered(lambda po: po.state in ('draft', 'sent', 'to approve'))
        if draft_pos:
            raise UserError(_(
                'Las siguientes órdenes de compra deben estar confirmadas:\n%s'
            ) % '\n'.join(draft_pos.mapped('name')))

        # Verificar si ya existe factura con esta referencia
        if config and config.skip_if_invoice_exists:
            existing_invoice = self.env['account.move'].search([
                ('ref', '=', self.legal_document_number),
                ('move_type', '=', 'in_invoice'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if existing_invoice:
                self.vendor_bill_id = existing_invoice
                self.state = 'done'
                self.message_post(
                    body=_('Factura existente encontrada: %s') % existing_invoice.name
                )
                return existing_invoice

        self.state = 'processing'

        try:
            # Crear factura usando el wizard estándar de Odoo
            invoice = self._create_vendor_bill_from_purchases(purchase_orders, config)

            # Actualizar referencia
            self.vendor_bill_id = invoice
            self.state = 'done'

            # Actualizar detalles
            self.detail_ids.write({
                'invoice_id': invoice.id,
                'state': 'invoiced'
            })

            self.message_post(
                body=_('Factura de proveedor creada: %s') % invoice.name
            )

            # Descargar y adjuntar PDF si está configurado
            if config and config.attach_ml_pdf and self.ml_pdf_file_id:
                try:
                    self._download_and_attach_pdf(invoice)
                except Exception as e:
                    _logger.warning(
                        f'Error al descargar PDF para factura {self.legal_document_number}: {e}'
                    )
                    # No fallar por error en descarga de PDF

            return invoice

        except Exception as e:
            self.state = 'draft'
            _logger.error(f'Error creando factura para {self.legal_document_number}: {e}')
            raise

    def _create_vendor_bill_from_purchases(self, purchase_orders, config):
        """
        Crea una factura de proveedor desde múltiples órdenes de compra
        """
        # Obtener el proveedor (debe ser el mismo en todas las POs)
        vendor = purchase_orders[0].partner_id

        # Preparar valores de la factura
        invoice_vals = {
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'invoice_date': fields.Date.context_today(self),
            'date': fields.Date.context_today(self),
            'ref': self.legal_document_number,
            'company_id': self.company_id.id,
            'currency_id': purchase_orders[0].currency_id.id,
            'ml_billing_period_id': self.period_id.id,
            'ml_is_commission_invoice': True,
        }

        # Configurar diario si existe
        if config and config.journal_id:
            invoice_vals['journal_id'] = config.journal_id.id

        # Crear factura
        invoice = self.env['account.move'].create(invoice_vals)

        # Agregar líneas desde todas las POs
        for po in purchase_orders:
            for po_line in po.order_line:
                # Crear línea de factura
                invoice_line_vals = {
                    'move_id': invoice.id,
                    'product_id': po_line.product_id.id,
                    'name': po_line.name,
                    'quantity': po_line.product_qty,
                    'price_unit': po_line.price_unit,
                    'tax_ids': [(6, 0, po_line.taxes_id.ids)],
                    'purchase_line_id': po_line.id,
                }

                # Configurar cuenta si existe
                if config and config.expense_account_id:
                    invoice_line_vals['account_id'] = config.expense_account_id.id

                self.env['account.move.line'].with_context(check_move_validity=False).create(invoice_line_vals)

        # Agregar línea de nota con el origen
        po_names = ', '.join(purchase_orders.mapped('name'))
        self.env['account.move.line'].with_context(check_move_validity=False).create({
            'move_id': invoice.id,
            'display_type': 'line_note',
            'name': f'Documento Legal ML: {self.legal_document_number}\nÓrdenes: {po_names}',
        })

        # Recalcular impuestos
        invoice._recompute_dynamic_lines(recompute_all_taxes=True)

        # Publicar automáticamente si está configurado
        if config and config.auto_post_invoices:
            invoice.action_post()

        return invoice

    def _download_and_attach_pdf(self, invoice):
        """
        Descarga el PDF desde MercadoLibre y lo adjunta a la factura
        """
        if not self.ml_pdf_file_id:
            _logger.warning(f'No hay file_id para descargar PDF de {self.legal_document_number}')
            return

        # Obtener token válido
        token = self.account_id.get_valid_token()
        if not token:
            raise UserError(_('No se pudo obtener un token válido para descargar el PDF'))

        # Descargar PDF
        url = f'https://api.mercadolibre.com/billing/integration/legal_document/{self.ml_pdf_file_id}'

        import requests
        import base64

        headers = {
            'Authorization': f'Bearer {token}',
        }

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            raise UserError(_(
                'Error al descargar PDF de MercadoLibre.\n'
                'Status: %s\n'
                'Response: %s'
            ) % (response.status_code, response.text[:200]))

        # Convertir a base64
        pdf_data = base64.b64encode(response.content).decode('utf-8')

        # Crear adjunto
        attachment = self.env['ir.attachment'].create({
            'name': f'{self.legal_document_number}.pdf',
            'type': 'binary',
            'datas': pdf_data,
            'res_model': 'account.move',
            'res_id': invoice.id,
            'mimetype': 'application/pdf',
        })

        self.ml_pdf_attachment_id = attachment

        _logger.info(f'PDF descargado y adjuntado para {self.legal_document_number}')

        return attachment
