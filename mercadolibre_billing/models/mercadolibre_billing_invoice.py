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

    # Indica si todos los detalles son notas de crédito
    is_credit_note = fields.Boolean(
        string='Es Nota de Crédito',
        compute='_compute_is_credit_note',
        store=True,
        help='True si TODOS los detalles de esta factura son notas de crédito'
    )

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

    @api.depends('detail_ids', 'detail_ids.is_credit_note')
    def _compute_is_credit_note(self):
        for record in self:
            if record.detail_ids:
                # Es nota de crédito si TODOS los detalles son notas de crédito
                record.is_credit_note = all(d.is_credit_note for d in record.detail_ids)
            else:
                record.is_credit_note = False

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

    def action_download_pdf(self):
        """
        Descarga manualmente el PDF de MercadoLibre
        y lo adjunta a este registro y a la factura de proveedor si existe
        """
        self.ensure_one()

        if not self.ml_pdf_file_id:
            raise UserError(_('No hay File ID de PDF disponible para descargar.'))

        try:
            # Si ya existe factura de proveedor, adjuntar ahí también
            invoice = self.vendor_bill_id if self.vendor_bill_id else None
            attachment = self._download_and_attach_pdf(invoice)

            if attachment:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('PDF Descargado'),
                        'message': _('El PDF se ha descargado y adjuntado correctamente.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            raise UserError(_('Error al descargar PDF: %s') % str(e))

    def action_create_grouped_invoice(self):
        """
        Abre el wizard para crear la factura de proveedor
        El wizard permite ver el resumen y advierte si se crearán POs automáticamente
        """
        self.ensure_one()

        # Verificar si ya existe una factura
        if self.vendor_bill_id:
            raise UserError(_(
                'Ya existe una factura de proveedor para este documento legal: %s'
            ) % self.vendor_bill_id.name)

        # Abrir wizard de confirmación
        return {
            'type': 'ir.actions.act_window',
            'name': _('Crear Factura de Proveedor'),
            'res_model': 'mercadolibre.billing.create.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_group_id': self.id,
            }
        }

    def _create_invoice_internal(self, config=None):
        """
        Método interno para crear la factura o nota de crédito (llamado desde el wizard)
        - Para facturas: requiere POs confirmadas
        - Para notas de crédito: crea directamente sin PO
        """
        self.ensure_one()

        if not config:
            config = self.env['mercadolibre.billing.sync.config'].sudo().search([
                ('account_id', '=', self.account_id.id)
            ], limit=1)

        # Determinar tipo de movimiento
        move_type = 'in_refund' if self.is_credit_note else 'in_invoice'

        # Verificar si ya existe documento con esta referencia
        if config and config.skip_if_invoice_exists:
            existing_invoice = self.env['account.move'].search([
                ('ref', '=', self.legal_document_number),
                ('move_type', '=', move_type),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if existing_invoice:
                self.vendor_bill_id = existing_invoice
                self.state = 'done'
                self.message_post(
                    body=_('Documento existente encontrado: %s') % existing_invoice.name
                )
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'view_mode': 'form',
                    'res_id': existing_invoice.id,
                }

        self.state = 'processing'

        try:
            # Si es nota de crédito, crear directamente sin PO
            if self.is_credit_note:
                invoice = self._create_credit_note_direct(config)
            else:
                # Obtener todas las POs para facturas normales
                purchase_orders = self.detail_ids.mapped('purchase_order_id')

                if not purchase_orders:
                    raise UserError(_('No hay órdenes de compra para procesar.'))

                # Crear factura desde POs
                invoice = self._create_vendor_bill_from_purchases(purchase_orders, config)

            # Actualizar referencia
            self.vendor_bill_id = invoice
            self.state = 'done'

            # Actualizar detalles
            self.detail_ids.write({
                'invoice_id': invoice.id,
                'state': 'invoiced'
            })

            doc_type = 'Nota de Crédito' if self.is_credit_note else 'Factura de proveedor'
            self.message_post(
                body=_(f'{doc_type} creada: %s') % invoice.name
            )

            # Siempre descargar y adjuntar PDF si existe file_id
            _logger.info(f'Verificando PDF para {self.legal_document_number}: ml_pdf_file_id={self.ml_pdf_file_id}')
            if self.ml_pdf_file_id:
                try:
                    _logger.info(f'Iniciando descarga de PDF para {self.legal_document_number}')
                    self._download_and_attach_pdf(invoice)
                    _logger.info(f'PDF descargado y adjuntado exitosamente para {self.legal_document_number}')
                except Exception as e:
                    _logger.error(
                        f'Error al descargar PDF para factura {self.legal_document_number}: {e}',
                        exc_info=True
                    )
                    # Notificar en el chatter que no se pudo descargar
                    self.message_post(
                        body=_('No se pudo descargar el PDF de MercadoLibre: %s') % str(e),
                        message_type='notification'
                    )
            else:
                _logger.warning(f'No hay ml_pdf_file_id para {self.legal_document_number}, PDF no disponible')

            # Retornar acción para ver la factura creada
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': invoice.id,
            }

        except Exception as e:
            self.state = 'draft'
            _logger.error(f'Error creando factura para {self.legal_document_number}: {e}')
            raise

    def _create_vendor_bill_from_purchases(self, purchase_orders, config):
        """
        Crea una factura de proveedor desde múltiples órdenes de compra
        Compatible con Odoo 16
        """
        # Obtener el proveedor (debe ser el mismo en todas las POs)
        vendor = purchase_orders[0].partner_id

        # Preparar líneas de factura
        invoice_line_vals_list = []

        for po in purchase_orders:
            for po_line in po.order_line:
                line_vals = {
                    'product_id': po_line.product_id.id,
                    'name': po_line.name,
                    'quantity': po_line.product_qty,
                    'price_unit': po_line.price_unit,
                    'tax_ids': [(6, 0, po_line.taxes_id.ids)],
                    'purchase_line_id': po_line.id,
                }

                # Configurar cuenta si existe
                if config and config.expense_account_id:
                    line_vals['account_id'] = config.expense_account_id.id

                invoice_line_vals_list.append((0, 0, line_vals))

        # Agregar línea de nota con el origen
        po_names = ', '.join(purchase_orders.mapped('name'))
        invoice_line_vals_list.append((0, 0, {
            'display_type': 'line_note',
            'name': f'Documento Legal ML: {self.legal_document_number}\nÓrdenes: {po_names}',
        }))

        # Preparar valores de la factura con líneas incluidas
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
            'invoice_line_ids': invoice_line_vals_list,
        }

        # Configurar diario si existe
        if config and config.journal_id:
            invoice_vals['journal_id'] = config.journal_id.id

        # Crear factura con todas las líneas (Odoo 16 recalcula automáticamente)
        invoice = self.env['account.move'].create(invoice_vals)

        # Publicar automáticamente si está configurado
        if config and config.auto_post_invoices:
            invoice.action_post()

        return invoice

    def _create_credit_note_direct(self, config=None):
        """
        Crea una nota de crédito de proveedor directamente sin PO
        Las notas de crédito no requieren orden de compra previa
        """
        self.ensure_one()

        if not config:
            config = self.env['mercadolibre.billing.sync.config'].sudo().search([
                ('account_id', '=', self.account_id.id)
            ], limit=1)

        # Obtener proveedor
        vendor = None
        if config and config.vendor_id:
            vendor = config.vendor_id
        else:
            # Crear o buscar proveedor automáticamente
            vendor_name = 'MercadoLibre' if self.billing_group == 'ML' else 'MercadoPago'
            vendor = self.env['res.partner'].search([
                ('name', '=', vendor_name),
                ('supplier_rank', '>', 0),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if not vendor:
                vendor = self.env['res.partner'].create({
                    'name': vendor_name,
                    'supplier_rank': 1,
                    'company_id': self.company_id.id,
                })

        # Preparar líneas de la nota de crédito
        invoice_line_vals_list = []

        for detail in self.detail_ids:
            # Obtener producto según mapeo de tipo de cargo
            ProductMapping = self.env['mercadolibre.billing.product.mapping']
            product = ProductMapping.get_product_for_charge(
                transaction_detail=detail.transaction_detail,
                account_id=self.account_id.id,
                billing_group=self.billing_group
            )

            # Si no hay mapeo, usar producto de configuración
            if not product:
                product = config.commission_product_id if config else None
                if not product:
                    product = self.env.ref(
                        'mercadolibre_billing.product_ml_commission',
                        raise_if_not_found=False
                    )

            if not product:
                raise UserError(_(
                    'No se ha configurado un producto para comisiones.\n'
                    'Por favor configure el mapeo de cargos.'
                ))

            # El monto de nota de crédito es positivo en el documento
            amount = abs(detail.detail_amount)

            # Descripción de la línea
            description_parts = []
            if detail.transaction_detail:
                description_parts.append(detail.transaction_detail)
            if detail.charge_bonified_id:
                description_parts.append(f'Bonificación cargo: {detail.charge_bonified_id}')
            if detail.ml_order_id:
                description_parts.append(f'Orden ML: {detail.ml_order_id}')
            if detail.reference_id:
                description_parts.append(f'Ref MP: {detail.reference_id}')

            line_name = '\n'.join(description_parts) if description_parts else f'Nota de Crédito {self.billing_group}'

            line_vals = {
                'product_id': product.id,
                'name': line_name,
                'quantity': 1,
                'price_unit': amount,
            }

            # Aplicar impuesto si está configurado
            if config and config.purchase_tax_id:
                line_vals['tax_ids'] = [(6, 0, [config.purchase_tax_id.id])]

            # Configurar cuenta si existe
            if config and config.expense_account_id:
                line_vals['account_id'] = config.expense_account_id.id

            invoice_line_vals_list.append((0, 0, line_vals))

        # Agregar línea de nota con información del documento
        invoice_line_vals_list.append((0, 0, {
            'display_type': 'line_note',
            'name': f'Documento Legal ML: {self.legal_document_number}',
        }))

        # Preparar valores de la nota de crédito
        credit_note_vals = {
            'move_type': 'in_refund',  # Nota de crédito de proveedor
            'partner_id': vendor.id,
            'invoice_date': fields.Date.context_today(self),
            'date': fields.Date.context_today(self),
            'ref': self.legal_document_number,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'ml_billing_period_id': self.period_id.id,
            'ml_is_commission_invoice': True,
            'invoice_line_ids': invoice_line_vals_list,
        }

        # Configurar diario si existe
        if config and config.journal_id:
            credit_note_vals['journal_id'] = config.journal_id.id

        # Crear nota de crédito
        credit_note = self.env['account.move'].create(credit_note_vals)

        # Publicar automáticamente si está configurado
        if config and config.auto_post_invoices:
            credit_note.action_post()

        _logger.info(f'Nota de crédito creada directamente: {credit_note.name} para {self.legal_document_number}')

        return credit_note

    def _download_and_attach_pdf(self, invoice=None):
        """
        Descarga el PDF desde MercadoLibre y lo adjunta a la factura y al registro ML
        El PDF aparece en el chatter y en los adjuntos de ambos registros

        Args:
            invoice: account.move opcional. Si se proporciona, también adjunta el PDF ahí.
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

        _logger.info(f'Descargando PDF desde: {url}')

        import requests
        import base64

        headers = {
            'Authorization': f'Bearer {token}',
        }

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            _logger.error(f'Error descargando PDF: Status {response.status_code}, Response: {response.text[:500]}')
            raise UserError(_(
                'Error al descargar PDF de MercadoLibre.\n'
                'Status: %s\n'
                'Response: %s'
            ) % (response.status_code, response.text[:200]))

        # Convertir a base64
        pdf_data = base64.b64encode(response.content).decode('utf-8')
        pdf_filename = f'{self.legal_document_number}.pdf'

        _logger.info(f'PDF descargado correctamente: {pdf_filename}, tamaño: {len(response.content)} bytes')

        attachment_invoice = None

        # Crear adjunto para la factura de proveedor (account.move) si existe
        if invoice:
            attachment_invoice = self.env['ir.attachment'].create({
                'name': pdf_filename,
                'type': 'binary',
                'datas': pdf_data,
                'res_model': 'account.move',
                'res_id': invoice.id,
                'mimetype': 'application/pdf',
            })

            # Publicar mensaje con adjunto en el chatter de la factura de proveedor
            invoice.message_post(
                body=_('PDF de factura MercadoLibre/MercadoPago adjunto: %s') % self.legal_document_number,
                attachment_ids=[attachment_invoice.id],
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
            _logger.info(f'PDF adjuntado a factura de proveedor: {invoice.name}')

        # Crear adjunto para el registro de factura ML (mercadolibre.billing.invoice)
        attachment_ml = self.env['ir.attachment'].create({
            'name': pdf_filename,
            'type': 'binary',
            'datas': pdf_data,
            'res_model': 'mercadolibre.billing.invoice',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # Publicar mensaje con adjunto en el chatter del registro ML
        self.message_post(
            body=_('PDF de MercadoLibre descargado y adjuntado'),
            attachment_ids=[attachment_ml.id],
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

        # Guardar referencia al adjunto (para compatibilidad)
        self.ml_pdf_attachment_id = attachment_ml

        _logger.info(f'PDF descargado y adjuntado para {self.legal_document_number}')

        # Retornar el adjunto del registro ML (siempre existe)
        return attachment_ml
