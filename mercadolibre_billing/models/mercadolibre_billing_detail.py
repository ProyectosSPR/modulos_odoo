# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MercadoliBillingDetail(models.Model):
    _name = 'mercadolibre.billing.detail'
    _description = 'Detalle de Facturación MercadoLibre/MercadoPago'
    _order = 'creation_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
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
    invoice_group_id = fields.Many2one(
        'mercadolibre.billing.invoice',
        string='Factura ML',
        ondelete='cascade',
        index=True,
        help='Agrupa detalles por número de factura legal'
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
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Orden de Compra',
        ondelete='restrict',
        tracking=True
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        ondelete='restrict',
        tracking=True
    )

    # Document Info
    ml_document_id = fields.Char(
        string='Document ID',
        index=True,
        help='ID del documento fiscal'
    )

    # Charge Info (común para ML y MP)
    ml_detail_id = fields.Char(
        string='Detail ID',
        required=True,
        index=True,
        help='ID único del detalle de facturación'
    )
    legal_document_number = fields.Char(
        string='Número de Factura Legal',
        index=True
    )
    legal_document_status = fields.Char(
        string='Estado del Documento'
    )
    legal_document_status_description = fields.Char(
        string='Descripción Estado'
    )
    creation_date = fields.Datetime(
        string='Fecha de Creación',
        index=True
    )
    transaction_detail = fields.Text(
        string='Detalle de Transacción'
    )
    debited_from_operation = fields.Char(
        string='Debitado de Operación'
    )
    debited_from_operation_description = fields.Char(
        string='Descripción Débito'
    )
    charge_status = fields.Char(
        string='Estado del Cargo'
    )
    charge_status_description = fields.Char(
        string='Descripción Estado Cargo'
    )
    charge_bonified_id = fields.Char(
        string='ID Cargo Bonificado',
        help='Si existe, este detalle es una nota de crédito relacionada'
    )
    detail_amount = fields.Monetary(
        string='Monto',
        currency_field='currency_id',
        tracking=True
    )
    detail_type = fields.Selection([
        ('bill', 'Factura'),
        ('credit_note', 'Nota de Crédito'),
        ('other', 'Otro')
    ], string='Tipo de Documento', compute='_compute_detail_type', store=True)
    detail_sub_type = fields.Char(
        string='Subtipo'
    )

    # Discount Info (solo ML)
    amount_without_discount = fields.Monetary(
        string='Monto sin Descuento',
        currency_field='currency_id',
        help='Solo para MercadoLibre'
    )
    discount_amount = fields.Monetary(
        string='Descuento',
        currency_field='currency_id',
        help='Solo para MercadoLibre'
    )
    discount_reason = fields.Char(
        string='Razón del Descuento',
        help='Solo para MercadoLibre'
    )

    # Sales Info (ML) / Operation Info (MP)
    ml_order_id = fields.Char(
        string='Order ID',
        index=True,
        help='ID de la orden ML (solo MercadoLibre)'
    )
    ml_operation_id = fields.Char(
        string='Operation ID / Movement ID',
        help='ML: operation_id, MP: movement_id'
    )
    reference_id = fields.Char(
        string='Reference ID',
        help='Solo para MercadoPago'
    )
    sale_date = fields.Datetime(
        string='Fecha de Venta'
    )
    sales_channel = fields.Char(
        string='Canal de Venta'
    )
    payer_nickname = fields.Char(
        string='Nickname del Pagador'
    )
    state_name = fields.Char(
        string='Estado',
        help='Solo para MercadoLibre'
    )
    transaction_amount = fields.Monetary(
        string='Monto de Transacción',
        currency_field='currency_id'
    )
    operation_type = fields.Char(
        string='Tipo de Operación',
        help='Solo para MercadoPago'
    )
    operation_type_description = fields.Char(
        string='Descripción Tipo Operación',
        help='Solo para MercadoPago'
    )
    store_id = fields.Char(
        string='Store ID',
        help='Solo para MercadoPago'
    )
    store_name = fields.Char(
        string='Store Name',
        help='Solo para MercadoPago'
    )
    external_reference = fields.Char(
        string='Referencia Externa',
        help='Solo para MercadoPago'
    )

    # Shipping Info (solo ML)
    ml_shipping_id = fields.Char(
        string='Shipping ID',
        help='Solo para MercadoLibre'
    )
    ml_pack_id = fields.Char(
        string='Pack ID',
        help='Solo para MercadoLibre'
    )
    receiver_shipping_cost = fields.Monetary(
        string='Costo de Envío',
        currency_field='currency_id',
        help='Solo para MercadoLibre'
    )

    # Items Info (solo ML - primer item)
    ml_item_id = fields.Char(
        string='Item ID',
        help='Solo para MercadoLibre'
    )
    item_title = fields.Char(
        string='Título del Item',
        help='Solo para MercadoLibre'
    )
    item_type = fields.Char(
        string='Tipo de Item',
        help='Solo para MercadoLibre'
    )
    item_category = fields.Char(
        string='Categoría',
        help='Solo para MercadoLibre'
    )
    inventory_id = fields.Char(
        string='Inventory ID',
        help='Solo para MercadoLibre'
    )
    item_amount = fields.Float(
        string='Cantidad',
        help='Solo para MercadoLibre'
    )
    item_price = fields.Monetary(
        string='Precio Unitario',
        currency_field='currency_id',
        help='Solo para MercadoLibre'
    )
    items_info_json = fields.Text(
        string='Items Info (JSON)',
        help='Todos los items en formato JSON (solo MercadoLibre)'
    )

    # Perception Info (solo MP)
    taxable_amount = fields.Monetary(
        string='Monto Imponible',
        currency_field='currency_id',
        help='Solo para MercadoPago'
    )
    aliquot = fields.Float(
        string='Alícuota',
        help='Solo para MercadoPago'
    )

    # Marketplace Info
    marketplace = fields.Char(
        string='Marketplace',
        help='MLM, MLA, MLB, etc.'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )

    # Control
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('purchase_created', 'PO Creada'),
        ('invoiced', 'Facturado'),
        ('error', 'Error')
    ], string='Estado', default='draft', required=True, tracking=True)

    is_credit_note = fields.Boolean(
        string='Es Nota de Crédito',
        compute='_compute_is_credit_note',
        store=True
    )
    error_message = fields.Text(
        string='Mensaje de Error'
    )
    raw_data = fields.Text(
        string='Datos Crudos (JSON)',
        help='Respuesta completa de la API en formato JSON'
    )

    _sql_constraints = [
        ('ml_detail_id_uniq', 'unique(ml_detail_id)',
         'Este detalle de facturación ya existe.')
    ]

    @staticmethod
    def _parse_datetime(datetime_str):
        """
        Convierte fecha ISO 8601 a formato Odoo
        Entrada: '2025-12-01T02:56:34' o '2025-12-01 02:56:34'
        Salida: '2025-12-01 02:56:34'
        """
        if not datetime_str:
            return None

        try:
            # Si ya está en formato correcto, retornar
            if ' ' in str(datetime_str):
                return datetime_str

            # Convertir de ISO 8601 a formato Odoo
            dt = datetime.fromisoformat(str(datetime_str).replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            _logger.warning(f'Error parseando fecha {datetime_str}: {e}')
            return None

    @api.depends('legal_document_number', 'ml_detail_id')
    def _compute_name(self):
        for record in self:
            if record.legal_document_number:
                record.name = record.legal_document_number
            elif record.ml_detail_id:
                record.name = f'Detalle #{record.ml_detail_id}'
            else:
                record.name = 'Nuevo Detalle'

    @api.depends('charge_bonified_id', 'detail_sub_type')
    def _compute_is_credit_note(self):
        for record in self:
            record.is_credit_note = bool(record.charge_bonified_id)

    @api.depends('is_credit_note')
    def _compute_detail_type(self):
        for record in self:
            if record.is_credit_note:
                record.detail_type = 'credit_note'
            elif record.detail_amount:
                record.detail_type = 'bill'
            else:
                record.detail_type = 'other'

    @api.model
    def create_from_api_data(self, data, period):
        """
        Crea o actualiza un detalle de facturación desde datos de la API
        También crea/actualiza el agrupador de factura

        Args:
            data: Diccionario con datos de la API
            period: Registro mercadolibre.billing.period

        Returns:
            tuple: (detail, is_new)
        """
        charge_info = data.get('charge_info', {})
        detail_id = str(charge_info.get('detail_id'))

        if not detail_id:
            _logger.warning('Detalle sin detail_id, saltando')
            return None, False

        # Buscar detalle existente (usar sudo para evitar filtros de seguridad)
        existing = self.sudo().search([('ml_detail_id', '=', detail_id)], limit=1)

        # Preparar valores según el grupo (ML o MP)
        values = self._prepare_values_from_api_data(data, period)

        # Obtener o crear la factura agrupadora
        legal_doc_number = charge_info.get('legal_document_number')
        if legal_doc_number:
            invoice_group = self._get_or_create_invoice_group(
                period, legal_doc_number, data
            )
            values['invoice_group_id'] = invoice_group.id

        if existing:
            existing.write(values)
            return existing, False
        else:
            detail = self.create(values)
            return detail, True

    def _get_or_create_invoice_group(self, period, legal_document_number, data):
        """
        Obtiene o crea el agrupador de factura
        """
        Invoice = self.env['mercadolibre.billing.invoice']

        invoice_group = Invoice.sudo().search([
            ('legal_document_number', '=', legal_document_number),
            ('period_id', '=', period.id)
        ], limit=1)

        if not invoice_group:
            document_info = data.get('document_info', {})
            charge_info = data.get('charge_info', {})

            # Extraer file_id del PDF si existe
            ml_pdf_file_id = None
            legal_document_files = document_info.get('legal_document_files', [])
            if legal_document_files and isinstance(legal_document_files, list):
                for doc_file in legal_document_files:
                    if isinstance(doc_file, dict) and doc_file.get('file_id'):
                        ml_pdf_file_id = str(doc_file.get('file_id'))
                        break

            invoice_group = Invoice.create({
                'period_id': period.id,
                'legal_document_number': legal_document_number,
                'ml_document_id': str(document_info.get('document_id', '')),
                'legal_document_status': charge_info.get('legal_document_status'),
                'ml_pdf_file_id': ml_pdf_file_id,
            })
        else:
            # Actualizar file_id si no existe y viene en los datos
            if not invoice_group.ml_pdf_file_id:
                document_info = data.get('document_info', {})
                legal_document_files = document_info.get('legal_document_files', [])
                if legal_document_files and isinstance(legal_document_files, list):
                    for doc_file in legal_document_files:
                        if isinstance(doc_file, dict) and doc_file.get('file_id'):
                            invoice_group.ml_pdf_file_id = str(doc_file.get('file_id'))
                            break

        return invoice_group

    @api.model
    def _prepare_values_from_api_data(self, data, period):
        """
        Prepara valores para crear/actualizar detalle desde API
        Soporta tanto MercadoLibre (ML) como MercadoPago (MP)
        """
        charge_info = data.get('charge_info', {})
        document_info = data.get('document_info', {})
        marketplace_info = data.get('marketplace_info', {})
        currency_info = data.get('currency_info', {})

        # Valores comunes
        values = {
            'period_id': period.id,
            'company_id': period.company_id.id if period.company_id else None,
            'ml_detail_id': str(charge_info.get('detail_id')),
            'ml_document_id': str(document_info.get('document_id', '')),
            'legal_document_number': charge_info.get('legal_document_number'),
            'legal_document_status': charge_info.get('legal_document_status'),
            'legal_document_status_description': charge_info.get('legal_document_status_description'),
            'creation_date': self._parse_datetime(charge_info.get('creation_date_time')),
            'transaction_detail': charge_info.get('transaction_detail'),
            'debited_from_operation': charge_info.get('debited_from_operation'),
            'debited_from_operation_description': charge_info.get('debited_from_operation_description'),
            'charge_status': charge_info.get('status'),
            'charge_status_description': charge_info.get('status_description'),
            'charge_bonified_id': charge_info.get('charge_bonified_id'),
            'detail_amount': charge_info.get('detail_amount', 0.0),
            'detail_sub_type': charge_info.get('detail_sub_type'),
            'marketplace': marketplace_info.get('marketplace'),
            'raw_data': json.dumps(data, indent=2),
        }

        # Obtener moneda
        currency_code = currency_info.get('currency_id', 'MXN')
        currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
        if currency:
            values['currency_id'] = currency.id

        # Valores específicos según el grupo
        if period.billing_group == 'ML':
            values.update(self._prepare_ml_specific_values(data))
        elif period.billing_group == 'MP':
            values.update(self._prepare_mp_specific_values(data))

        return values

    @api.model
    def _prepare_ml_specific_values(self, data):
        """Valores específicos para MercadoLibre"""
        discount_info = data.get('discount_info') or {}
        sales_info_list = data.get('sales_info') or []
        sales_info = sales_info_list[0] if sales_info_list else {}
        shipping_info = data.get('shipping_info') or {}
        items_info_list = data.get('items_info') or []
        items_info = items_info_list[0] if items_info_list else {}

        values = {
            # Discount Info
            'amount_without_discount': discount_info.get('charge_amount_without_discount', 0.0),
            'discount_amount': discount_info.get('discount_amount', 0.0),
            'discount_reason': discount_info.get('discount_reason'),

            # Sales Info
            'ml_order_id': str(sales_info.get('order_id', '')),
            'ml_operation_id': str(sales_info.get('operation_id', '')),
            'sale_date': self._parse_datetime(sales_info.get('sale_date_time')),
            'sales_channel': sales_info.get('sales_channel'),
            'payer_nickname': sales_info.get('payer_nickname'),
            'state_name': sales_info.get('state_name'),
            'transaction_amount': sales_info.get('transaction_amount', 0.0),

            # Shipping Info
            'ml_shipping_id': str(shipping_info.get('shipping_id', '')),
            'ml_pack_id': str(shipping_info.get('pack_id', '')),
            'receiver_shipping_cost': shipping_info.get('receiver_shipping_cost', 0.0),

            # Items Info (primer item)
            'ml_item_id': str(items_info.get('item_id', '')),
            'item_title': items_info.get('item_title'),
            'item_type': items_info.get('item_type'),
            'item_category': items_info.get('item_category'),
            'inventory_id': str(items_info.get('inventory_id', '')),
            'item_amount': items_info.get('item_amount', 0.0),
            'item_price': items_info.get('item_price', 0.0),
            'items_info_json': json.dumps(items_info_list, indent=2) if items_info_list else None,
        }

        return values

    @api.model
    def _prepare_mp_specific_values(self, data):
        """Valores específicos para MercadoPago"""
        operation_info = data.get('operation_info') or {}
        perception_info = data.get('perception_info') or {}
        charge_info = data.get('charge_info') or {}

        values = {
            # Operation Info
            'ml_operation_id': str(charge_info.get('movement_id', '')),
            'reference_id': str(operation_info.get('reference_id', '')),
            'sales_channel': operation_info.get('sales_channel'),
            'payer_nickname': operation_info.get('payer_nickname'),
            'transaction_amount': operation_info.get('transaction_amount', 0.0),
            'operation_type': operation_info.get('operation_type'),
            'operation_type_description': operation_info.get('operation_type_description'),
            'store_id': str(operation_info.get('store_id', '')),
            'store_name': operation_info.get('store_name'),
            'external_reference': operation_info.get('external_reference'),

            # Perception Info
            'taxable_amount': perception_info.get('taxable_amount', 0.0),
            'aliquot': perception_info.get('aliquot', 0.0),
        }

        return values

    def action_create_purchase_order(self):
        """
        Crea una Purchase Order para este detalle individual
        """
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_('Este detalle ya tiene una orden de compra asociada.'))

        # Obtener configuración
        config = self.env['mercadolibre.billing.sync.config'].sudo().search([
            ('account_id', '=', self.account_id.id)
        ], limit=1)

        if not config:
            # Crear configuración básica si no existe
            config = self.env['mercadolibre.billing.sync.config'].sudo().create({
                'name': f'Config {self.account_id.name}',
                'account_id': self.account_id.id,
            })

        # Obtener/crear proveedor MercadoLibre
        vendor = self._get_or_create_ml_vendor()

        # Obtener producto de comisión
        commission_product = config.commission_product_id
        if not commission_product:
            commission_product = self.env.ref(
                'mercadolibre_billing.product_ml_commission',
                raise_if_not_found=False
            )
            if not commission_product:
                raise UserError(_(
                    'No se ha configurado un producto para comisiones. '
                    'Por favor configure el producto en la configuración de sincronización.'
                ))

        # Determinar precio unitario (negativo para notas de crédito)
        if self.is_credit_note:
            price_unit = -abs(self.detail_amount)
            po_name = f'Nota de Crédito {self.billing_group} - {self.legal_document_number or self.ml_detail_id}'
        else:
            price_unit = abs(self.detail_amount)
            po_name = f'Comisión {self.billing_group} - {self.legal_document_number or self.ml_detail_id}'

        # Preparar partner_ref con información de trazabilidad
        partner_ref_parts = []
        if self.legal_document_number:
            partner_ref_parts.append(f'Fact: {self.legal_document_number}')
        if self.reference_id:  # MercadoPago
            partner_ref_parts.append(f'Ref: {self.reference_id}')
        elif self.ml_order_id:  # MercadoLibre
            partner_ref_parts.append(f'Orden: {self.ml_order_id}')

        partner_ref = ' | '.join(partner_ref_parts) if partner_ref_parts else None

        # Crear Purchase Order
        po_vals = {
            'partner_id': vendor.id,
            'ml_billing_period_id': self.period_id.id,
            'date_order': self.creation_date or fields.Datetime.now(),
            'company_id': self.company_id.id,
            'origin': po_name,
            'currency_id': self.currency_id.id,
            'partner_ref': partner_ref,
        }

        po = self.env['purchase.order'].create(po_vals)

        # Crear línea de PO
        description_parts = []
        if self.transaction_detail:
            description_parts.append(self.transaction_detail)
        if self.legal_document_number:
            description_parts.append(f'Factura: {self.legal_document_number}')
        if self.ml_order_id:
            description_parts.append(f'Orden ML: {self.ml_order_id}')
        if self.reference_id:
            description_parts.append(f'Ref MP: {self.reference_id}')

        line_name = '\n'.join(description_parts) if description_parts else po_name

        po_line_vals = {
            'order_id': po.id,
            'product_id': commission_product.id,
            'name': line_name,
            'product_qty': 1,
            'price_unit': price_unit,
            'date_planned': self.creation_date or fields.Datetime.now(),
        }

        # Aplicar impuesto si está configurado
        if config.purchase_tax_id:
            po_line_vals['taxes_id'] = [(6, 0, [config.purchase_tax_id.id])]

        self.env['purchase.order.line'].create(po_line_vals)

        # Actualizar detalle
        self.write({
            'purchase_order_id': po.id,
            'state': 'purchase_created'
        })

        # Auto-confirmar si está configurado
        if config.auto_validate_purchase_orders:
            po.button_confirm()

        self.message_post(
            body=_('Orden de Compra %s creada.') % po.name
        )

        return po

    def _create_purchase_order_line(self, purchase_order):
        """
        Crea una línea de PO adicional en una orden existente
        Usado cuando múltiples detalles pertenecen a la misma factura
        """
        self.ensure_one()

        # Obtener configuración
        config = self.env['mercadolibre.billing.sync.config'].sudo().search([
            ('account_id', '=', self.account_id.id)
        ], limit=1)

        # Obtener producto de comisión
        commission_product = config.commission_product_id if config else None
        if not commission_product:
            commission_product = self.env.ref(
                'mercadolibre_billing.product_ml_commission',
                raise_if_not_found=False
            )
            if not commission_product:
                raise UserError(_(
                    'No se ha configurado un producto para comisiones.'
                ))

        # Determinar precio unitario
        if self.is_credit_note:
            price_unit = -abs(self.detail_amount)
        else:
            price_unit = abs(self.detail_amount)

        # Crear descripción de la línea
        description_parts = []
        if self.transaction_detail:
            description_parts.append(self.transaction_detail)
        if self.ml_order_id:
            description_parts.append(f'Orden ML: {self.ml_order_id}')
        if self.ml_pack_id:
            description_parts.append(f'Pack: {self.ml_pack_id}')
        if self.reference_id:
            description_parts.append(f'Ref MP: {self.reference_id}')

        line_name = '\n'.join(description_parts) if description_parts else self.transaction_detail or 'Comisión ML'

        # Crear línea
        po_line_vals = {
            'order_id': purchase_order.id,
            'product_id': commission_product.id,
            'name': line_name,
            'product_qty': 1,
            'price_unit': price_unit,
            'date_planned': self.creation_date or fields.Datetime.now(),
        }

        self.env['purchase.order.line'].create(po_line_vals)

        return True

    def _get_or_create_ml_vendor(self):
        """
        Obtiene o crea el proveedor de MercadoLibre/MercadoPago
        """
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
                'vat': 'MLM830624LB5',  # RFC genérico
                'country_id': self.env.ref('base.mx').id,
            })

        return vendor

    def action_view_purchase_order(self):
        """Acción para ver la orden de compra"""
        self.ensure_one()

        if not self.purchase_order_id:
            raise UserError(_('Este detalle no tiene una orden de compra asociada.'))

        return {
            'name': _('Orden de Compra'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': self.purchase_order_id.id,
        }

    def action_view_invoice(self):
        """Acción para ver la factura"""
        self.ensure_one()

        if not self.invoice_id:
            raise UserError(_('Este detalle no tiene una factura asociada.'))

        return {
            'name': _('Factura'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
        }
