# -*- coding: utf-8 -*-

import json
import time
import logging
import pytz
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

MEXICO_TZ = pytz.timezone('America/Mexico_City')


class MercadolibreOrder(models.Model):
    _name = 'mercadolibre.order'
    _description = 'Orden MercadoLibre'
    _order = 'date_closed desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # MercadoLibre IDs
    ml_order_id = fields.Char(
        string='Order ID',
        required=True,
        readonly=True,
        index=True,
        help='ID de la orden en MercadoLibre'
    )
    ml_pack_id = fields.Char(
        string='Pack ID',
        readonly=True,
        index=True,
        help='ID del pack/carrito (agrupa multiples ordenes)'
    )
    ml_shipment_id = fields.Char(
        string='Shipment ID',
        readonly=True,
        index=True,
        help='ID del envio en MercadoLibre'
    )

    # Order Status
    status = fields.Selection([
        ('confirmed', 'Confirmada'),
        ('payment_required', 'Pago Requerido'),
        ('payment_in_process', 'Pago en Proceso'),
        ('partially_paid', 'Parcialmente Pagada'),
        ('paid', 'Pagada'),
        ('partially_refunded', 'Parcialmente Reembolsada'),
        ('pending_cancel', 'Cancelacion Pendiente'),
        ('cancelled', 'Cancelada'),
    ], string='Estado ML', readonly=True, tracking=True, index=True)

    status_detail = fields.Char(
        string='Detalle Estado',
        readonly=True
    )

    # Logistic Info
    logistic_type = fields.Selection([
        ('fulfillment', 'Full (Mercado Libre)'),
        ('xd_drop_off', 'Agencia/Places'),
        ('cross_docking', 'Colectas'),
        ('drop_off', 'Drop Off'),
        ('self_service', 'Flex'),
        ('custom', 'Envio Propio'),
        ('not_specified', 'A Convenir'),
    ], string='Tipo Logistico', readonly=True, tracking=True,
       help='Tipo de logistica del envio')

    logistic_type_id = fields.Many2one(
        'mercadolibre.logistic.type',
        string='Config. Tipo Logistico',
        compute='_compute_logistic_type_id',
        store=True,
        help='Configuracion del tipo logistico para acciones automaticas'
    )

    # Buyer Info
    buyer_id = fields.Many2one(
        'mercadolibre.buyer',
        string='Comprador',
        readonly=True
    )
    ml_buyer_id = fields.Char(
        string='Buyer ID ML',
        readonly=True
    )
    buyer_nickname = fields.Char(
        string='Nickname Comprador',
        readonly=True
    )

    # Amounts
    total_amount = fields.Float(
        string='Monto Total',
        readonly=True,
        digits=(16, 2),
        help='Monto total de la orden (sin descuentos)'
    )
    paid_amount = fields.Float(
        string='Monto Pagado',
        readonly=True,
        digits=(16, 2)
    )
    shipping_cost = fields.Float(
        string='Costo Envio',
        readonly=True,
        digits=(16, 2)
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        readonly=True
    )
    ml_currency = fields.Char(
        string='Moneda ML',
        readonly=True
    )

    # Dates
    date_created = fields.Datetime(
        string='Fecha Creacion',
        readonly=True
    )
    date_closed = fields.Datetime(
        string='Fecha Cierre',
        readonly=True,
        index=True
    )
    date_last_updated = fields.Datetime(
        string='Ultima Actualizacion ML',
        readonly=True
    )

    # Context
    channel = fields.Selection([
        ('marketplace', 'Marketplace'),
        ('mshops', 'Mercado Shops'),
        ('proximity', 'Proximity'),
        ('mp-channel', 'MercadoPago Channel'),
    ], string='Canal', readonly=True)

    # Tags
    ml_tags = fields.Char(
        string='Tags ML',
        readonly=True,
        help='Tags de la orden separados por coma'
    )
    is_pack_order = fields.Boolean(
        string='Es Orden de Pack',
        compute='_compute_is_pack_order',
        store=True
    )
    has_discount = fields.Boolean(
        string='Tiene Descuento',
        compute='_compute_has_discount',
        store=True
    )

    # Items
    item_ids = fields.One2many(
        'mercadolibre.order.item',
        'order_id',
        string='Productos'
    )
    item_count = fields.Integer(
        string='Cantidad Items',
        compute='_compute_item_count',
        store=True
    )

    # Discounts
    discount_ids = fields.One2many(
        'mercadolibre.order.discount',
        'order_id',
        string='Descuentos'
    )
    total_discount = fields.Float(
        string='Total Descuento',
        compute='_compute_total_discount',
        store=True,
        digits=(16, 2),
        help='Total de descuentos aplicados a la orden'
    )
    seller_discount = fields.Float(
        string='Descuento Vendedor',
        compute='_compute_total_discount',
        store=True,
        digits=(16, 2),
        help='Porcion del descuento a cargo del vendedor'
    )
    meli_discount = fields.Float(
        string='Descuento MercadoLibre',
        compute='_compute_total_discount',
        store=True,
        digits=(16, 2),
        help='Porcion del descuento a cargo de MercadoLibre'
    )

    # Sync Status
    sync_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('synced', 'Sincronizado'),
        ('error', 'Error'),
        ('ignored', 'Ignorado'),
    ], string='Estado Sync', default='pending', tracking=True)

    sync_error = fields.Text(
        string='Error Sincronizacion',
        readonly=True
    )
    last_sync_date = fields.Datetime(
        string='Ultima Sincronizacion',
        readonly=True
    )

    # Odoo Integration
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        readonly=True,
        tracking=True,
        help='Orden de venta creada en Odoo'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente Odoo',
        tracking=True
    )

    odoo_order_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('created', 'Creada'),
        ('error', 'Error'),
        ('skipped', 'Omitida'),
    ], string='Estado Orden Odoo', default='pending', tracking=True)

    odoo_order_error = fields.Text(
        string='Error Orden Odoo',
        readonly=True
    )

    # Stock validation tracking
    stock_validation_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('ok', 'Completo'),
        ('partial', 'Parcial'),
        ('failed', 'Sin Stock'),
        ('forced', 'Forzado'),
    ], string='Estado Validacion Stock', default='pending', tracking=True)

    stock_validation_notes = fields.Text(
        string='Notas de Stock',
        readonly=True,
        help='Detalle de productos con problemas de stock'
    )

    has_sale_order = fields.Boolean(
        string='Tiene Orden Odoo',
        compute='_compute_has_sale_order',
        store=True
    )

    # Raw Data
    raw_data = fields.Text(
        string='Datos Crudos',
        readonly=True,
        help='JSON completo de la orden desde MercadoLibre'
    )

    notes = fields.Text(
        string='Notas'
    )

    _sql_constraints = [
        ('ml_order_id_uniq', 'unique(ml_order_id, account_id)',
         'Esta orden ya existe para esta cuenta.')
    ]

    @api.depends('ml_order_id', 'ml_pack_id')
    def _compute_name(self):
        for record in self:
            if record.ml_pack_id:
                record.name = f'PACK-{record.ml_pack_id}'
            elif record.ml_order_id:
                record.name = f'ORD-{record.ml_order_id}'
            else:
                record.name = 'Nueva Orden'

    @api.depends('ml_pack_id')
    def _compute_is_pack_order(self):
        for record in self:
            record.is_pack_order = bool(record.ml_pack_id)

    @api.depends('discount_ids')
    def _compute_has_discount(self):
        for record in self:
            record.has_discount = bool(record.discount_ids)

    @api.depends('item_ids')
    def _compute_item_count(self):
        for record in self:
            record.item_count = len(record.item_ids)

    @api.depends('discount_ids.total_amount', 'discount_ids.seller_amount')
    def _compute_total_discount(self):
        for record in self:
            total = sum(record.discount_ids.mapped('total_amount'))
            seller = sum(record.discount_ids.mapped('seller_amount'))
            record.total_discount = total
            record.seller_discount = seller
            record.meli_discount = total - seller

    @api.depends('sale_order_id')
    def _compute_has_sale_order(self):
        for record in self:
            record.has_sale_order = bool(record.sale_order_id)

    @api.depends('logistic_type', 'account_id')
    def _compute_logistic_type_id(self):
        """Busca la configuracion de tipo logistico correspondiente"""
        LogisticType = self.env['mercadolibre.logistic.type']
        for record in self:
            if record.logistic_type:
                logistic_config = LogisticType.search([
                    ('code', '=', record.logistic_type),
                    '|',
                    ('account_id', '=', record.account_id.id),
                    ('account_id', '=', False),
                ], limit=1, order='account_id desc')
                record.logistic_type_id = logistic_config.id if logistic_config else False
            else:
                record.logistic_type_id = False

    @api.model
    def create_from_ml_data(self, data, account):
        """
        Crea o actualiza una orden desde los datos de MercadoLibre

        Args:
            data: dict con los datos de la orden desde la API
            account: mercadolibre.account record

        Returns:
            (mercadolibre.order record, bool is_new)
        """
        ml_order_id = str(data.get('id', ''))

        if not ml_order_id:
            _logger.error('No se encontro ID de orden en los datos')
            return False, False

        # Buscar orden existente
        existing = self.search([
            ('ml_order_id', '=', ml_order_id),
            ('account_id', '=', account.id)
        ], limit=1)

        # Preparar valores
        currency = self._get_currency(data.get('currency_id', 'MXN'))

        # Buyer info
        buyer_data = data.get('buyer', {}) or {}
        ml_buyer_id = str(buyer_data.get('id', ''))

        # Shipping info
        shipping = data.get('shipping', {}) or {}
        ml_shipment_id = str(shipping.get('id', '')) if shipping.get('id') else ''

        # Context info
        context = data.get('context', {}) or {}
        channel = context.get('channel', '')

        # Tags
        tags = data.get('tags', []) or []
        ml_tags = ','.join(tags) if tags else ''

        # Logistic type - obtener del shipment si existe
        logistic_type = self._get_logistic_type_from_data(data)

        vals = {
            'account_id': account.id,
            'ml_order_id': ml_order_id,
            'ml_pack_id': str(data.get('pack_id', '')) if data.get('pack_id') else '',
            'ml_shipment_id': ml_shipment_id,
            'status': data.get('status', ''),
            'status_detail': data.get('status_detail', ''),
            'logistic_type': logistic_type,
            'ml_buyer_id': ml_buyer_id,
            'buyer_nickname': buyer_data.get('nickname', ''),
            'total_amount': data.get('total_amount', 0.0),
            'paid_amount': data.get('paid_amount', 0.0),
            'shipping_cost': data.get('shipping_cost', 0.0),
            'currency_id': currency.id if currency else False,
            'ml_currency': data.get('currency_id', ''),
            'date_created': self._parse_datetime(data.get('date_created')),
            'date_closed': self._parse_datetime(data.get('date_closed')),
            'date_last_updated': self._parse_datetime(data.get('last_updated')),
            'channel': channel if channel in ['marketplace', 'mshops', 'proximity', 'mp-channel'] else False,
            'ml_tags': ml_tags,
            'raw_data': json.dumps(data, indent=2, ensure_ascii=False),
            'last_sync_date': fields.Datetime.now(),
        }

        if existing:
            _logger.info('Actualizando orden existente: %s', ml_order_id)
            existing.write(vals)
            order = existing
            is_new = False
        else:
            _logger.info('Creando nueva orden: %s', ml_order_id)
            order = self.create(vals)
            is_new = True

        # Crear/actualizar items
        self._sync_items(order, data.get('order_items', []))

        # Crear/actualizar comprador
        if ml_buyer_id:
            buyer = self._sync_buyer(buyer_data, account)
            if buyer:
                order.buyer_id = buyer.id

        return order, is_new

    def _get_logistic_type_from_data(self, data):
        """
        Obtiene el tipo logistico de los datos de la orden.

        El logistic_type puede venir de:
        1. shipping.logistic_type directamente en la orden
        2. Los tags de la orden (como backup)
        3. Consultando el shipment (si no viene en la orden)
        """
        # Mapeo de valores de ML a nuestro selection
        logistic_map = {
            'fulfillment': 'fulfillment',
            'xd_drop_off': 'xd_drop_off',
            'cross_docking': 'cross_docking',
            'drop_off': 'drop_off',
            'self_service': 'self_service',
            'custom': 'custom',
            'not_specified': 'not_specified',
            'default': 'custom',  # me1 default = envio propio
        }

        # 1. Intentar desde shipping.logistic_type (viene en la orden)
        shipping = data.get('shipping', {}) or {}
        logistic_type = shipping.get('logistic_type', '')

        if logistic_type and logistic_type in logistic_map:
            return logistic_map[logistic_type]

        # 2. Intentar desde los tags de la orden
        tags = data.get('tags', []) or []
        tags_str = str(tags).lower()

        if 'fulfillment' in tags_str:
            return 'fulfillment'
        if 'self_service' in tags_str:
            return 'self_service'
        if 'drop_off' in tags_str:
            return 'drop_off'
        if 'cross_docking' in tags_str:
            return 'cross_docking'

        # 3. Inferir del modo de envio
        shipping_mode = shipping.get('mode', '')
        if shipping_mode == 'me1':
            return 'custom'  # me1 generalmente es envio propio
        elif shipping_mode == 'custom':
            return 'custom'
        elif shipping_mode == 'not_specified':
            return 'not_specified'

        # Si no se puede determinar, retornar False para que se actualice despues
        return False

    def _sync_items(self, order, items_data):
        """Sincroniza los items de la orden"""
        ItemModel = self.env['mercadolibre.order.item']

        # Eliminar items existentes
        order.item_ids.unlink()

        for item_data in items_data:
            item_info = item_data.get('item', {}) or {}

            ItemModel.create({
                'order_id': order.id,
                'ml_item_id': item_info.get('id', ''),
                'title': item_info.get('title', ''),
                'category_id': item_info.get('category_id', ''),
                'variation_id': str(item_info.get('variation_id', '')) if item_info.get('variation_id') else '',
                'seller_sku': item_info.get('seller_sku', '') or item_info.get('seller_custom_field', ''),
                'condition': item_info.get('condition', ''),
                'quantity': item_data.get('quantity', 1),
                'unit_price': item_data.get('unit_price', 0.0),
                'full_unit_price': item_data.get('full_unit_price', 0.0),
                'sale_fee': item_data.get('sale_fee', 0.0),
                'listing_type_id': item_data.get('listing_type_id', ''),
            })

    def _sync_buyer(self, buyer_data, account):
        """Crea o actualiza el comprador"""
        BuyerModel = self.env['mercadolibre.buyer']
        ml_buyer_id = str(buyer_data.get('id', ''))

        if not ml_buyer_id:
            return False

        existing = BuyerModel.search([
            ('ml_buyer_id', '=', ml_buyer_id),
            ('account_id', '=', account.id)
        ], limit=1)

        vals = {
            'account_id': account.id,
            'ml_buyer_id': ml_buyer_id,
            'nickname': buyer_data.get('nickname', ''),
            'first_name': buyer_data.get('first_name', ''),
            'last_name': buyer_data.get('last_name', ''),
            'email': buyer_data.get('email', ''),
        }

        if existing:
            existing.write(vals)
            return existing
        else:
            return BuyerModel.create(vals)

    def _get_currency(self, currency_code):
        """Obtiene la moneda de Odoo por codigo"""
        if not currency_code:
            return False

        currency = self.env['res.currency'].search([
            ('name', '=', currency_code)
        ], limit=1)

        return currency

    def _parse_datetime(self, dt_string):
        """Parsea fecha/hora de MercadoLibre"""
        if not dt_string:
            return False

        try:
            if 'T' in dt_string:
                dt_string = dt_string.split('.')[0].replace('T', ' ')
                if '+' in dt_string:
                    dt_string = dt_string.split('+')[0]
                if '-' in dt_string and dt_string.count('-') > 2:
                    parts = dt_string.rsplit('-', 1)
                    dt_string = parts[0]
                return datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
            return datetime.strptime(dt_string, '%Y-%m-%d')
        except (ValueError, TypeError) as e:
            _logger.warning('Error parseando fecha %s: %s', dt_string, str(e))
            return False

    def action_sync_logistic_type(self):
        """
        Sincroniza el logistic_type desde el shipment de MercadoLibre.
        Util cuando el logistic_type no viene en la orden directamente.
        """
        self.ensure_one()
        import requests

        if not self.ml_shipment_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Envio'),
                    'message': _('Esta orden no tiene ID de envio'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        logistic_type = self._fetch_logistic_type_from_shipment()

        if logistic_type:
            self.write({'logistic_type': logistic_type})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Tipo Logistico Actualizado'),
                    'message': _('Tipo logistico: %s') % dict(self._fields['logistic_type'].selection).get(logistic_type, logistic_type),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se pudo obtener el tipo logistico'),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def _fetch_logistic_type_from_shipment(self):
        """
        Obtiene el logistic_type consultando el endpoint /shipments/{id}.
        Retorna el logistic_type mapeado o False.
        """
        self.ensure_one()
        import requests

        if not self.ml_shipment_id:
            return False

        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            _logger.error('Error obteniendo token: %s', str(e))
            return False

        url = f'https://api.mercadolibre.com/shipments/{self.ml_shipment_id}'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()

                # Mapeo de valores de ML a nuestro selection
                logistic_map = {
                    'fulfillment': 'fulfillment',
                    'xd_drop_off': 'xd_drop_off',
                    'cross_docking': 'cross_docking',
                    'drop_off': 'drop_off',
                    'self_service': 'self_service',
                    'custom': 'custom',
                    'not_specified': 'not_specified',
                    'default': 'custom',
                }

                # Log completo de datos recibidos para debug
                _logger.info(
                    'Shipment %s data: logistic_type=%s, logistic=%s, mode=%s, tags=%s',
                    self.ml_shipment_id,
                    data.get('logistic_type'),
                    data.get('logistic'),
                    data.get('mode'),
                    data.get('tags')
                )

                # El logistic_type puede venir directamente o en logistic.type
                logistic_type = data.get('logistic_type', '')

                if not logistic_type:
                    logistic = data.get('logistic', {}) or {}
                    logistic_type = logistic.get('type', '')

                if logistic_type and logistic_type in logistic_map:
                    _logger.info('Logistic type obtenido para shipment %s: %s -> %s',
                               self.ml_shipment_id, logistic_type, logistic_map[logistic_type])
                    return logistic_map[logistic_type]

                # Intentar inferir del modo
                mode = data.get('mode', '')
                if not mode:
                    logistic = data.get('logistic', {}) or {}
                    mode = logistic.get('mode', '')

                if mode == 'me1':
                    _logger.info('Shipment %s: modo me1 -> custom', self.ml_shipment_id)
                    return 'custom'
                elif mode == 'me2':
                    # me2 sin tipo especifico, buscar en tags
                    tags = data.get('tags', []) or []
                    if 'fulfillment' in str(tags).lower():
                        _logger.info('Shipment %s: modo me2 con tag fulfillment -> fulfillment', self.ml_shipment_id)
                        return 'fulfillment'
                    _logger.info('Shipment %s: modo me2 sin fulfillment -> xd_drop_off', self.ml_shipment_id)
                    return 'xd_drop_off'  # Por defecto para me2

                _logger.warning('Shipment %s: no se pudo determinar logistic_type', self.ml_shipment_id)
                return False

            else:
                _logger.error('Error obteniendo shipment %s: %s',
                            self.ml_shipment_id, response.text)
                return False

        except Exception as e:
            _logger.error('Error en request de shipment %s: %s',
                        self.ml_shipment_id, str(e))
            return False

    def action_view_raw_data(self):
        """Muestra los datos crudos de la orden"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Datos Crudos - {self.name}',
            'res_model': 'mercadolibre.order',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('mercadolibre_sales.view_mercadolibre_order_raw_form').id,
            'target': 'new',
        }

    def action_sync_discounts(self):
        """Sincroniza los descuentos de la orden desde la API"""
        self.ensure_one()
        return self._sync_discounts_from_api()

    def _sync_discounts_from_api(self):
        """
        Obtiene y sincroniza los descuentos desde /orders/{id}/discounts
        """
        self.ensure_one()
        import requests

        if not self.ml_order_id:
            return False

        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            _logger.error('Error obteniendo token: %s', str(e))
            return False

        url = f'https://api.mercadolibre.com/orders/{self.ml_order_id}/discounts'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                self._process_discounts(data)
                return True
            elif response.status_code == 404:
                _logger.info('No hay descuentos para orden %s', self.ml_order_id)
                return True
            else:
                _logger.error('Error obteniendo descuentos: %s', response.text)
                return False

        except Exception as e:
            _logger.error('Error en request de descuentos: %s', str(e))
            return False

    def _process_discounts(self, discounts_data):
        """Procesa y crea los registros de descuento"""
        DiscountModel = self.env['mercadolibre.order.discount']

        # Eliminar descuentos existentes
        self.discount_ids.unlink()

        details = discounts_data.get('details', []) or []

        for detail in details:
            discount_type = detail.get('type', '')
            supplier = detail.get('supplier', {}) or {}
            items = detail.get('items', []) or []

            for item in items:
                amounts = item.get('amounts', {}) or {}
                total_amount = amounts.get('total', 0.0)
                seller_amount = amounts.get('seller', 0.0)

                # Solo crear si hay monto de descuento
                if total_amount > 0:
                    DiscountModel.create({
                        'order_id': self.id,
                        'discount_type': discount_type,
                        'ml_item_id': item.get('id', ''),
                        'quantity': item.get('quantity', 1),
                        'total_amount': total_amount,
                        'seller_amount': seller_amount,
                        'meli_campaign': supplier.get('meli_campaign', ''),
                        'offer_id': supplier.get('offer_id', ''),
                        'funding_mode': supplier.get('funding_mode', ''),
                        'coupon_id': str(detail.get('coupon', {}).get('id', '')) if detail.get('coupon') else '',
                        'cashback_id': str(detail.get('cashback', {}).get('id', '')) if detail.get('cashback') else '',
                    })

    def action_create_sale_order(self):
        """
        Accion manual para crear orden de venta en Odoo directamente.
        Busca una configuracion existente o usa valores por defecto.
        """
        self.ensure_one()

        # Si ya tiene orden, mostrarla
        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Orden de Venta'),
                'res_model': 'sale.order',
                'res_id': self.sale_order_id.id,
                'view_mode': 'form',
            }

        # Validar estado
        if self.status not in ('paid', 'partially_paid'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No se puede crear'),
                    'message': _('Solo se pueden crear ordenes para ventas pagadas. Estado actual: %s') % self.status,
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Buscar configuracion existente
        config = self.env['mercadolibre.order.sync.config'].search([
            ('account_id', '=', self.account_id.id),
            ('create_sale_orders', '=', True),
        ], limit=1)

        if not config:
            # Crear configuracion temporal con valores minimos
            config = self.env['mercadolibre.order.sync.config'].new({
                'account_id': self.account_id.id,
                'name': 'Temporal',
                'create_sale_orders': True,
                'auto_confirm_order': False,
            })

        # Crear la orden de venta
        sale_order = self._create_sale_order(config)

        if sale_order:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Orden de Venta Creada'),
                'res_model': 'sale.order',
                'res_id': sale_order.id,
                'view_mode': 'form',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': self.odoo_order_error or _('No se pudo crear la orden de venta'),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_create_sale_order_wizard(self):
        """Abre wizard para crear orden de venta con opciones"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Crear Orden de Venta'),
            'res_model': 'mercadolibre.order.sync',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_account_id': self.account_id.id,
                'default_search_specific': True,
                'default_specific_order_id': self.ml_order_id,
            },
        }

    def action_view_sale_order(self):
        """Abre la orden de venta asociada"""
        self.ensure_one()
        if not self.sale_order_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Orden de Venta'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
        }

    def action_mark_synced(self):
        """Marca la orden como sincronizada"""
        self.write({
            'sync_status': 'synced',
            'sync_error': False,
        })

    def action_mark_ignored(self):
        """Marca la orden como ignorada"""
        self.write({
            'sync_status': 'ignored',
        })

    def action_retry_sync(self):
        """Reintenta la sincronizacion de la orden"""
        self.write({
            'sync_status': 'pending',
            'sync_error': False,
            'odoo_order_state': 'pending',
            'odoo_order_error': False,
        })

    @api.model
    def _cron_create_sale_orders(self):
        """
        Cron para crear ordenes de venta automaticamente.

        Busca ordenes ML sincronizadas que:
        - Esten pagadas (paid o partially_paid)
        - No tengan orden de venta creada
        - No esten en estado de error

        Usa la configuracion del tipo logistico para determinar
        si debe confirmar automaticamente la orden y el picking.
        """
        _logger.info('Iniciando cron de creacion de ordenes de venta')

        # Buscar ordenes pendientes de crear
        orders = self.search([
            ('status', 'in', ['paid', 'partially_paid']),
            ('sale_order_id', '=', False),
            ('odoo_order_state', 'in', ['pending', 'error']),
        ], limit=100)  # Limitar para evitar timeouts

        if not orders:
            _logger.info('No hay ordenes pendientes de crear')
            return

        _logger.info('Procesando %d ordenes pendientes', len(orders))

        created_count = 0
        error_count = 0

        for order in orders:
            try:
                # Buscar configuracion de sincronizacion para esta cuenta
                config = self.env['mercadolibre.order.sync.config'].search([
                    ('account_id', '=', order.account_id.id),
                    ('create_sale_orders', '=', True),
                ], limit=1)

                if not config:
                    # Crear configuracion temporal minima
                    config = self.env['mercadolibre.order.sync.config'].new({
                        'account_id': order.account_id.id,
                        'name': 'Temporal',
                        'create_sale_orders': True,
                    })

                # Crear la orden de venta
                sale_order = order._create_sale_order(config)

                if sale_order:
                    created_count += 1
                    _logger.info('Orden %s creada exitosamente: %s',
                               order.ml_order_id, sale_order.name)
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                _logger.error('Error creando orden para %s: %s',
                            order.ml_order_id, str(e))
                order.write({
                    'odoo_order_state': 'error',
                    'odoo_order_error': str(e),
                })

        _logger.info('Cron finalizado: %d creadas, %d errores',
                    created_count, error_count)

    def _create_sale_order(self, config):
        """
        Crea la orden de venta en Odoo basandose en la configuracion.

        Args:
            config: mercadolibre.order.sync.config record con la configuracion

        Returns:
            sale.order record o False
        """
        self.ensure_one()

        # Validar que no tenga ya una orden creada
        if self.sale_order_id:
            _logger.info('Orden %s ya tiene orden Odoo: %s', self.ml_order_id, self.sale_order_id.name)
            return self.sale_order_id

        # Validar estado de la orden ML
        if self.status not in ('paid', 'partially_paid'):
            self.write({
                'odoo_order_state': 'skipped',
                'odoo_order_error': f'Orden no pagada (estado: {self.status})',
            })
            return False

        try:
            # Obtener o crear partner
            partner = self._get_or_create_partner(config)
            if not partner:
                raise ValidationError(_('No se pudo obtener/crear el cliente'))

            # Obtener configuracion de tipo logistico
            logistic_config = self.logistic_type_id

            # Determinar warehouse (requerido en sale.order)
            warehouse = False
            if logistic_config and logistic_config.warehouse_id:
                warehouse = logistic_config.warehouse_id
            elif config.default_warehouse_id:
                warehouse = config.default_warehouse_id
            if not warehouse:
                # Buscar almacen de la compania
                warehouse = self.env['stock.warehouse'].search([
                    ('company_id', '=', self.company_id.id)
                ], limit=1)
            if not warehouse:
                # Buscar cualquier almacen disponible
                warehouse = self.env['stock.warehouse'].search([], limit=1)
            if not warehouse:
                raise ValidationError(_('No se encontro ningun almacen. Configure un almacen por defecto en la configuracion de sincronizacion.'))

            # Determinar pricelist (prioridad: tipo logistico > sync config > compania)
            pricelist = False
            if logistic_config and logistic_config.pricelist_id:
                pricelist = logistic_config.pricelist_id
            elif config.default_pricelist_id:
                pricelist = config.default_pricelist_id
            if not pricelist:
                # Buscar tarifa de la compania
                pricelist = self.env['product.pricelist'].search([
                    ('company_id', '=', self.company_id.id)
                ], limit=1)
            if not pricelist:
                # Buscar tarifa sin compania (global)
                pricelist = self.env['product.pricelist'].search([
                    ('company_id', '=', False)
                ], limit=1)
            if not pricelist:
                # Buscar cualquier tarifa disponible
                pricelist = self.env['product.pricelist'].search([], limit=1)
            if not pricelist:
                raise ValidationError(_('No se encontro ninguna tarifa de precios. Configure una tarifa por defecto en la configuracion de sincronizacion.'))

            # Preparar valores de la orden
            order_vals = {
                'partner_id': partner.id,
                'company_id': self.company_id.id,
                'date_order': self.date_closed or fields.Datetime.now(),
                'pricelist_id': pricelist.id,
                'warehouse_id': warehouse.id if warehouse else False,
                # Campos ML
                'ml_order_id': self.ml_order_id,
                'ml_pack_id': self.ml_pack_id,
                'ml_shipment_id': self.ml_shipment_id,
                'ml_account_id': self.account_id.id,
                'ml_logistic_type': self.logistic_type,
                'ml_channel': self.channel,
                'ml_sync_date': fields.Datetime.now(),
            }

            # Agregar team si esta configurado
            if logistic_config and logistic_config.team_id:
                order_vals['team_id'] = logistic_config.team_id.id
            elif config.default_team_id:
                order_vals['team_id'] = config.default_team_id.id

            # Agregar carrier si esta configurado en el tipo logistico
            if logistic_config and logistic_config.carrier_id:
                order_vals['carrier_id'] = logistic_config.carrier_id.id

            # Crear orden de venta
            sale_order = self.env['sale.order'].create(order_vals)
            _logger.info('Orden de venta creada: %s para ML orden %s', sale_order.name, self.ml_order_id)

            # Crear lineas de productos
            self._create_sale_order_lines(sale_order, config)

            # Crear lineas de descuento si aplica
            if self.seller_discount > 0:
                self._create_discount_lines(sale_order, config)

            # Manejar aporte de MercadoLibre (co-fondeo)
            meli_order = self._handle_meli_discount(sale_order, config)

            # =========================================================
            # ASIGNAR ETIQUETAS SEGUN CONFIGURACION
            # =========================================================
            tags_to_assign = self.env['crm.tag']

            # 1. Etiquetas por defecto del tipo logistico
            if logistic_config and logistic_config.default_tag_ids:
                tags_to_assign |= logistic_config.default_tag_ids
                _logger.debug('Etiquetas por tipo logistico: %s', logistic_config.default_tag_ids.mapped('name'))

            # 2. Etiquetas por estado de pago
            payment_tags = self.env['mercadolibre.payment.status.config'].get_tags_for_payment_status(
                self.status,
                account_id=self.account_id.id,
                company_id=self.company_id.id
            )
            if payment_tags:
                tags_to_assign |= payment_tags
                _logger.debug('Etiquetas por estado de pago (%s): %s', self.status, payment_tags.mapped('name'))

            # 3. Etiquetas por estado de envio (si hay shipment sincronizado)
            if logistic_config and hasattr(self, 'shipment_id') and self.shipment_id:
                shipment_status = self.shipment_id.status
                shipment_tags = logistic_config.get_tags_for_shipment_status(shipment_status)
                if shipment_tags:
                    tags_to_assign |= shipment_tags
                    _logger.debug('Etiquetas por estado de envio (%s): %s', shipment_status, shipment_tags.mapped('name'))

            # Asignar etiquetas a la orden de venta
            if tags_to_assign:
                sale_order.write({'tag_ids': [(6, 0, tags_to_assign.ids)]})
                _logger.info('Etiquetas asignadas a %s: %s', sale_order.name, tags_to_assign.mapped('name'))

            # Determinar si se debe confirmar automaticamente
            # Prioridad: tipo logistico > sync config
            should_confirm_order = False
            should_confirm_picking = False

            if logistic_config:
                should_confirm_order = logistic_config.auto_confirm_order
                should_confirm_picking = logistic_config.auto_confirm_picking
            elif hasattr(config, 'auto_confirm_order'):
                should_confirm_order = config.auto_confirm_order

            # Confirmar orden automaticamente si esta configurado
            if should_confirm_order:
                try:
                    sale_order.action_confirm()
                    _logger.info('Orden %s confirmada automaticamente', sale_order.name)

                    # Confirmar picking si esta configurado en el tipo logistico
                    if should_confirm_picking:
                        self._auto_confirm_picking(sale_order, logistic_config)

                except Exception as e:
                    _logger.warning('Error al confirmar orden %s: %s', sale_order.name, str(e))

            # =========================================================
            # PROCESAR ETIQUETA DE ENVIO (descarga e impresion)
            # =========================================================
            if logistic_config and (logistic_config.download_shipping_label or logistic_config.auto_print_label):
                try:
                    label_result = self._process_shipping_label(logistic_config, sale_order)
                    if label_result.get('downloaded'):
                        _logger.info('Etiqueta descargada para orden %s', sale_order.name)
                    if label_result.get('printed'):
                        _logger.info('Etiqueta enviada a impresora para orden %s', sale_order.name)
                    if label_result.get('errors'):
                        for error in label_result['errors']:
                            _logger.warning('Error etiqueta %s: %s', sale_order.name, error)
                except Exception as e:
                    _logger.warning('Error procesando etiqueta para %s: %s', sale_order.name, str(e))

            # Actualizar registro ML
            self.write({
                'sale_order_id': sale_order.id,
                'partner_id': partner.id,
                'odoo_order_state': 'created',
                'odoo_order_error': False,
            })

            return sale_order

        except Exception as e:
            error_msg = str(e)
            _logger.error('Error creando orden Odoo para %s: %s', self.ml_order_id, error_msg)
            self.write({
                'odoo_order_state': 'error',
                'odoo_order_error': error_msg,
            })
            return False

    def _get_or_create_partner(self, config):
        """Obtiene o crea el partner para la orden"""
        self.ensure_one()

        # Si ya tiene partner asignado, usarlo
        if self.partner_id:
            return self.partner_id

        # Si tiene comprador registrado con partner, usarlo
        if self.buyer_id and self.buyer_id.partner_id:
            return self.buyer_id.partner_id

        # Buscar por email o nickname
        Partner = self.env['res.partner']

        if self.buyer_id:
            # Buscar por email
            if self.buyer_id.email:
                partner = Partner.search([
                    ('email', '=', self.buyer_id.email),
                    ('company_id', 'in', [self.company_id.id, False])
                ], limit=1)
                if partner:
                    self.buyer_id.partner_id = partner.id
                    return partner

            # Crear nuevo partner
            partner_vals = {
                'name': self.buyer_id.full_name or self.buyer_id.nickname or f'Comprador ML {self.ml_buyer_id}',
                'email': self.buyer_id.email,
                'company_id': self.company_id.id,
                'customer_rank': 1,
                'comment': f'Creado desde MercadoLibre. Buyer ID: {self.ml_buyer_id}',
            }
            partner = Partner.create(partner_vals)
            self.buyer_id.partner_id = partner.id
            return partner

        # Usar cliente por defecto
        return config.default_customer_id

    def _create_sale_order_lines(self, sale_order, config):
        """Crea las lineas de la orden de venta"""
        OrderLine = self.env['sale.order.line']

        for item in self.item_ids:
            # Buscar producto por SKU
            product = False
            if item.seller_sku:
                product = self.env['product.product'].search([
                    ('default_code', '=', item.seller_sku)
                ], limit=1)

            # Si no encuentra, usar producto por defecto
            if not product:
                product = config.default_product_id

            if not product:
                _logger.warning('No se encontro producto para SKU %s', item.seller_sku)
                continue

            line_vals = {
                'order_id': sale_order.id,
                'product_id': product.id,
                'name': item.title or product.name,
                'product_uom_qty': item.quantity,
                'price_unit': item.unit_price,
                'ml_item_id': item.ml_item_id,
                'ml_seller_sku': item.seller_sku,
            }

            OrderLine.create(line_vals)

    def _create_discount_lines(self, sale_order, config):
        """
        Crea lineas de descuento por el aporte del vendedor al co-fondeo.

        Solo se registra la porcion del descuento que paga el vendedor,
        ya que la porcion de MercadoLibre no afecta los ingresos del vendedor.
        """
        if not config.discount_product_id:
            _logger.warning('No hay producto de descuento configurado')
            return

        OrderLine = self.env['sale.order.line']

        # Crear una linea de descuento negativa por el monto que el vendedor aporta
        if self.seller_discount > 0:
            line_vals = {
                'order_id': sale_order.id,
                'product_id': config.discount_product_id.id,
                'name': f'Descuento promocional (Aporte vendedor)',
                'product_uom_qty': 1,
                'price_unit': -self.seller_discount,  # Negativo porque es descuento
            }
            OrderLine.create(line_vals)

    def _handle_meli_discount(self, sale_order, config):
        """
        Maneja el aporte de MercadoLibre en promociones co-fondeadas.

        El meli_discount es la parte del descuento que MercadoLibre aporta al comprador.
        Esto representa un ingreso adicional para el vendedor porque ML le paga esa diferencia.

        Opciones de manejo:
        - ignore: No registrar (por defecto)
        - same_order: Agregar como linea positiva en la misma orden
        - separate_order: Crear orden de venta separada con cliente "MercadoLibre"

        Returns:
            sale.order record si se crea orden separada, False en otro caso
        """
        self.ensure_one()

        # Verificar si hay aporte de ML
        if self.meli_discount <= 0:
            return False

        handling = getattr(config, 'meli_discount_handling', 'ignore')
        if handling == 'ignore':
            return False

        meli_product = getattr(config, 'meli_discount_product_id', False)
        if not meli_product:
            _logger.warning('No hay producto configurado para aporte ML')
            return False

        OrderLine = self.env['sale.order.line']

        if handling == 'same_order':
            # Agregar linea positiva en la misma orden
            line_vals = {
                'order_id': sale_order.id,
                'product_id': meli_product.id,
                'name': f'Aporte MercadoLibre (Co-fondeo)',
                'product_uom_qty': 1,
                'price_unit': self.meli_discount,  # Positivo porque es ingreso
            }
            OrderLine.create(line_vals)
            _logger.info('Aporte ML %.2f agregado a orden %s', self.meli_discount, sale_order.name)
            return False

        elif handling == 'separate_order':
            # Crear orden de venta separada
            meli_partner = getattr(config, 'meli_discount_partner_id', False)
            if not meli_partner:
                _logger.warning('No hay cliente configurado para orden de aporte ML')
                return False

            # Crear orden de venta para el aporte de ML
            meli_order_vals = {
                'partner_id': meli_partner.id,
                'company_id': self.company_id.id,
                'date_order': self.date_closed or fields.Datetime.now(),
                'client_order_ref': f'Aporte ML - {self.ml_order_id}',
                # Campos ML para referencia
                'ml_order_id': f'{self.ml_order_id}-MELI',
                'ml_pack_id': self.ml_pack_id,
                'ml_account_id': self.account_id.id,
                'ml_channel': 'meli_cofunding',
                'ml_sync_date': fields.Datetime.now(),
            }

            # Agregar warehouse si esta configurado
            if config.default_warehouse_id:
                meli_order_vals['warehouse_id'] = config.default_warehouse_id.id

            meli_order = self.env['sale.order'].create(meli_order_vals)

            # Crear linea del aporte
            OrderLine.create({
                'order_id': meli_order.id,
                'product_id': meli_product.id,
                'name': f'Aporte MercadoLibre - Orden {self.ml_order_id}',
                'product_uom_qty': 1,
                'price_unit': self.meli_discount,
            })

            _logger.info('Orden separada %s creada para aporte ML %.2f de orden %s',
                       meli_order.name, self.meli_discount, self.ml_order_id)

            # Confirmar automaticamente si esta configurado
            if config.auto_confirm_order:
                try:
                    meli_order.action_confirm()
                except Exception as e:
                    _logger.warning('Error confirmando orden ML %s: %s', meli_order.name, str(e))

            return meli_order

        return False

    def _auto_confirm_picking(self, sale_order, logistic_config=None):
        """
        Confirma automaticamente los pickings de la orden.

        Proceso:
        1. Busca pickings de la orden
        2. Verifica disponibilidad de stock
        3. Segun la politica de stock:
           - strict: Solo valida si hay stock completo
           - partial: Valida lo disponible, crea backorder
           - force: Valida todo aunque no haya stock
        4. Notifica problemas de stock si esta configurado

        Args:
            sale_order: Orden de venta
            logistic_config: Configuracion del tipo logistico (opcional)

        Returns:
            dict con resultado de la validacion:
            {
                'success': bool,
                'validated_pickings': list,
                'stock_issues': list of dicts con productos sin stock
            }
        """
        result = {
            'success': True,
            'validated_pickings': [],
            'stock_issues': [],
        }

        # Obtener politica de stock
        policy = 'strict'
        notify_issues = True
        notify_user = None

        if logistic_config:
            policy = logistic_config.stock_validation_policy or 'strict'
            notify_issues = logistic_config.notify_stock_issues
            notify_user = logistic_config.stock_issue_user_id

        for picking in sale_order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
            try:
                _logger.info('Procesando picking %s (estado: %s, politica: %s)',
                           picking.name, picking.state, policy)

                # Si el picking esta en borrador, confirmarlo
                if picking.state == 'draft':
                    picking.action_confirm()
                    _logger.debug('Picking %s confirmado (draft -> waiting/confirmed)', picking.name)

                # Si el picking esta esperando o confirmado, intentar asignar stock
                if picking.state in ('waiting', 'confirmed'):
                    picking.action_assign()
                    _logger.debug('Picking %s: intento de asignacion de stock', picking.name)

                # Verificar disponibilidad de stock
                stock_check = self._check_picking_stock_availability(picking)

                if stock_check['fully_available']:
                    # Stock completo, validar normalmente
                    self._set_picking_quantities_done(picking, use_reserved=True)
                    self._validate_picking(picking, create_backorder=False)
                    result['validated_pickings'].append(picking.name)
                    self.write({
                        'stock_validation_status': 'ok',
                        'stock_validation_notes': False,
                    })

                elif stock_check['partially_available']:
                    # Stock parcial
                    result['stock_issues'].extend(stock_check['missing_products'])

                    if policy == 'strict':
                        # No validar, solo notificar
                        self._notify_stock_issues(
                            sale_order, picking, stock_check['missing_products'],
                            notify_issues, notify_user
                        )
                        self.write({
                            'stock_validation_status': 'failed',
                            'stock_validation_notes': self._format_stock_issues(stock_check['missing_products']),
                        })
                        result['success'] = False
                        _logger.warning('Picking %s: stock insuficiente (politica estricta)', picking.name)

                    elif policy == 'partial':
                        # Validar lo disponible, crear backorder
                        self._set_picking_quantities_done(picking, use_reserved=True)
                        self._validate_picking(picking, create_backorder=True)
                        result['validated_pickings'].append(picking.name)
                        self._notify_stock_issues(
                            sale_order, picking, stock_check['missing_products'],
                            notify_issues, notify_user, is_backorder=True
                        )
                        self.write({
                            'stock_validation_status': 'partial',
                            'stock_validation_notes': self._format_stock_issues(
                                stock_check['missing_products'], backorder=True
                            ),
                        })
                        _logger.info('Picking %s: validacion parcial con backorder', picking.name)

                    elif policy == 'force':
                        # Forzar validacion aunque no haya stock
                        self._set_picking_quantities_done(picking, use_reserved=False, force_all=True)
                        self._validate_picking(picking, create_backorder=False)
                        result['validated_pickings'].append(picking.name)
                        self._notify_stock_issues(
                            sale_order, picking, stock_check['missing_products'],
                            notify_issues, notify_user, is_forced=True
                        )
                        self.write({
                            'stock_validation_status': 'forced',
                            'stock_validation_notes': self._format_stock_issues(
                                stock_check['missing_products'], forced=True
                            ),
                        })
                        _logger.warning('Picking %s: validacion forzada sin stock completo', picking.name)

                else:
                    # Sin stock disponible
                    result['stock_issues'].extend(stock_check['missing_products'])

                    if policy == 'force':
                        # Forzar incluso sin nada de stock
                        self._set_picking_quantities_done(picking, use_reserved=False, force_all=True)
                        self._validate_picking(picking, create_backorder=False)
                        result['validated_pickings'].append(picking.name)
                        self._notify_stock_issues(
                            sale_order, picking, stock_check['missing_products'],
                            notify_issues, notify_user, is_forced=True
                        )
                        self.write({
                            'stock_validation_status': 'forced',
                            'stock_validation_notes': self._format_stock_issues(
                                stock_check['missing_products'], forced=True
                            ),
                        })
                    else:
                        # No hay stock, notificar error
                        self._notify_stock_issues(
                            sale_order, picking, stock_check['missing_products'],
                            notify_issues, notify_user
                        )
                        self.write({
                            'stock_validation_status': 'failed',
                            'stock_validation_notes': self._format_stock_issues(stock_check['missing_products']),
                        })
                        result['success'] = False
                        _logger.warning('Picking %s: sin stock disponible', picking.name)

            except Exception as e:
                _logger.error('Error validando picking %s: %s', picking.name, str(e))
                result['success'] = False
                self.write({
                    'stock_validation_status': 'failed',
                    'stock_validation_notes': f'Error: {str(e)}',
                })

        return result

    def _check_picking_stock_availability(self, picking):
        """
        Verifica la disponibilidad de stock para un picking.

        En Odoo 16:
        - El estado 'assigned' indica que hay stock reservado
        - Para cantidad reservada usamos SQL directo a reserved_uom_qty
          ya que no esta expuesto como campo ORM

        Returns:
            dict: {
                'fully_available': bool,
                'partially_available': bool,
                'missing_products': list of dicts
            }
        """
        missing_products = []
        total_demanded = 0
        total_reserved = 0

        for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            demanded = move.product_uom_qty

            # En Odoo 16, obtener cantidad reservada desde la BD
            # porque reserved_uom_qty no esta expuesto como campo ORM directamente
            if move.move_line_ids:
                self.env.cr.execute("""
                    SELECT COALESCE(SUM(reserved_uom_qty), 0)
                    FROM stock_move_line
                    WHERE move_id = %s AND state NOT IN ('done', 'cancel')
                """, (move.id,))
                result = self.env.cr.fetchone()
                reserved = float(result[0]) if result else 0.0
            else:
                reserved = 0.0

            total_demanded += demanded
            total_reserved += reserved

            if reserved < demanded:
                missing_products.append({
                    'product_id': move.product_id.id,
                    'product_name': move.product_id.display_name,
                    'product_code': move.product_id.default_code or '',
                    'demanded': demanded,
                    'reserved': reserved,
                    'missing': demanded - reserved,
                    'uom': move.product_uom.name,
                })

        return {
            'fully_available': len(missing_products) == 0,
            'partially_available': total_reserved > 0 and len(missing_products) > 0,
            'missing_products': missing_products,
        }

    def _set_picking_quantities_done(self, picking, use_reserved=True, force_all=False):
        """
        Establece las cantidades hechas en las lineas de movimiento del picking.

        En Odoo 16:
        - stock.move usa 'quantity' para cantidad hecha (campo computado)
        - stock.move.line usa 'quantity' para cantidad hecha (columna: qty_done)
        - reserved_uom_qty se accede via SQL ya que no es campo ORM

        Args:
            picking: stock.picking a procesar
            use_reserved: Si True, usa la cantidad reservada. Si False, usa la demandada.
            force_all: Si True, fuerza todas las cantidades demandadas aunque no haya stock.
        """
        for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            # Obtener cantidad reservada via SQL
            if move.move_line_ids:
                self.env.cr.execute("""
                    SELECT COALESCE(SUM(reserved_uom_qty), 0)
                    FROM stock_move_line
                    WHERE move_id = %s AND state NOT IN ('done', 'cancel')
                """, (move.id,))
                result = self.env.cr.fetchone()
                reserved_qty = float(result[0]) if result else 0.0
            else:
                reserved_qty = 0.0

            if force_all:
                # Forzar cantidad demandada completa
                qty_to_do = move.product_uom_qty
            elif use_reserved:
                # Usar solo lo reservado
                qty_to_do = reserved_qty
            else:
                qty_to_do = move.product_uom_qty

            # En Odoo 16, usamos move.quantity (campo computado con inverse)
            move.quantity = qty_to_do

            # Actualizar move_line_ids si existen
            if move.move_line_ids:
                for move_line in move.move_line_ids:
                    # Obtener reserved_uom_qty via SQL para esta linea
                    self.env.cr.execute("""
                        SELECT COALESCE(reserved_uom_qty, 0)
                        FROM stock_move_line WHERE id = %s
                    """, (move_line.id,))
                    ml_reserved = float(self.env.cr.fetchone()[0] or 0)

                    if force_all:
                        # Forzar: usar reservado o demandado total
                        move_line.quantity = ml_reserved if ml_reserved > 0 else move.product_uom_qty
                    elif move_line.quantity == 0:
                        # Usar lo reservado
                        move_line.quantity = ml_reserved
            elif force_all and qty_to_do > 0:
                # Crear move_lines si es forzado y no existen
                try:
                    move._action_assign()
                    # Actualizar las lineas creadas
                    for move_line in move.move_line_ids:
                        self.env.cr.execute("""
                            SELECT COALESCE(reserved_uom_qty, 0)
                            FROM stock_move_line WHERE id = %s
                        """, (move_line.id,))
                        ml_reserved = float(self.env.cr.fetchone()[0] or 0)
                        move_line.quantity = ml_reserved if ml_reserved > 0 else move.product_uom_qty
                except Exception:
                    # Si falla la asignacion, crear linea manual
                    self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'picking_id': picking.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'quantity': move.product_uom_qty,
                    })

            _logger.debug(
                'Move %s: producto=%s, demandado=%.2f, reservado=%.2f, hecho=%.2f',
                move.id, move.product_id.name, move.product_uom_qty,
                reserved_qty, move.quantity
            )

    def _validate_picking(self, picking, create_backorder=False):
        """
        Valida un picking manejando los wizards automaticamente.

        Args:
            picking: stock.picking a validar
            create_backorder: Si True, crea backorder para cantidades pendientes
        """
        result = picking.with_context(
            skip_sms=True,
            skip_immediate=True
        ).button_validate()

        # Si retorna un wizard, procesarlo
        if isinstance(result, dict) and result.get('res_model'):
            wizard_model = result.get('res_model')
            wizard_context = result.get('context', {})

            if wizard_model == 'stock.backorder.confirmation':
                wizard = self.env[wizard_model].with_context(wizard_context).create({})
                if create_backorder:
                    wizard.process()
                    _logger.info('Backorder creado para picking %s', picking.name)
                else:
                    wizard.process_cancel_backorder()
                    _logger.debug('Backorder cancelado para picking %s', picking.name)

            elif wizard_model == 'stock.immediate.transfer':
                wizard = self.env[wizard_model].with_context(wizard_context).create({})
                wizard.process()
                _logger.debug('Transferencia inmediata procesada para picking %s', picking.name)

        _logger.info('Picking %s validado', picking.name)

    def _notify_stock_issues(self, sale_order, picking, missing_products,
                            notify=True, notify_user=None,
                            is_backorder=False, is_forced=False):
        """
        Notifica problemas de stock creando una actividad en la orden de venta.

        Args:
            sale_order: Orden de venta
            picking: Picking con problemas
            missing_products: Lista de productos con stock faltante
            notify: Si debe crear notificacion
            notify_user: Usuario a notificar
            is_backorder: Si se creo un backorder
            is_forced: Si se forzo la validacion
        """
        if not notify or not missing_products:
            return

        # Determinar usuario a notificar
        user = notify_user
        if not user:
            # Intentar obtener responsable del almacen
            if picking.picking_type_id.warehouse_id.user_id:
                user = picking.picking_type_id.warehouse_id.user_id
            else:
                user = self.env.user

        # Construir mensaje
        if is_forced:
            title = f'Stock forzado en {picking.name}'
            note_type = 'ADVERTENCIA: Se forzo la validacion sin stock completo'
        elif is_backorder:
            title = f'Backorder creado para {picking.name}'
            note_type = 'Se creo un backorder para los productos faltantes'
        else:
            title = f'Stock insuficiente en {picking.name}'
            note_type = 'No se pudo validar el picking por falta de stock'

        products_list = '\n'.join([
            f"- {p['product_name']} [{p['product_code']}]: "
            f"Faltante {p['missing']:.2f} {p['uom']} "
            f"(Demandado: {p['demanded']:.2f}, Reservado: {p['reserved']:.2f})"
            for p in missing_products
        ])

        note = f"""
<p><strong>{note_type}</strong></p>
<p>Orden ML: {self.ml_order_id}</p>
<p>Orden Odoo: {sale_order.name}</p>
<p>Picking: {picking.name}</p>
<p><strong>Productos con problemas:</strong></p>
<pre>{products_list}</pre>
"""

        # Crear actividad
        try:
            activity_type = self.env.ref('mail.mail_activity_data_warning', raise_if_not_found=False)
            if not activity_type:
                activity_type = self.env['mail.activity.type'].search([
                    ('name', 'ilike', 'warning')
                ], limit=1)
            if not activity_type:
                activity_type = self.env['mail.activity.type'].search([], limit=1)

            self.env['mail.activity'].create({
                'activity_type_id': activity_type.id if activity_type else False,
                'summary': title,
                'note': note,
                'res_model_id': self.env['ir.model']._get('sale.order').id,
                'res_id': sale_order.id,
                'user_id': user.id,
                'date_deadline': fields.Date.today(),
            })
            _logger.info('Actividad creada para orden %s: %s', sale_order.name, title)

        except Exception as e:
            _logger.warning('Error creando actividad de stock: %s', str(e))
            # Si falla la actividad, al menos registrar en el chatter
            try:
                sale_order.message_post(
                    body=note,
                    subject=title,
                    message_type='notification',
                )
            except Exception:
                pass

    def _format_stock_issues(self, missing_products, backorder=False, forced=False):
        """Formatea los problemas de stock para guardar en notas."""
        if not missing_products:
            return False

        lines = []
        if forced:
            lines.append('** VALIDACION FORZADA - PUEDE HABER STOCK NEGATIVO **')
        elif backorder:
            lines.append('** BACKORDER CREADO PARA PRODUCTOS FALTANTES **')
        else:
            lines.append('** NO SE PUDO VALIDAR POR FALTA DE STOCK **')

        lines.append('')
        lines.append('Productos con problemas:')
        for p in missing_products:
            lines.append(
                f"- {p['product_name']} [{p['product_code']}]: "
                f"Faltante {p['missing']:.2f} {p['uom']}"
            )

        return '\n'.join(lines)

    # =========================================================================
    # DESCARGA E IMPRESION DE ETIQUETAS DE ENVIO
    # =========================================================================

    def action_download_shipping_label(self):
        """
        Accion manual para descargar la etiqueta de envio de MercadoLibre.
        Descarga la etiqueta y la guarda como adjunto en la orden de venta.
        """
        self.ensure_one()
        if not self.ml_shipment_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Envio',
                    'message': 'Esta orden no tiene ID de envio de MercadoLibre.',
                    'type': 'warning',
                }
            }

        result = self._download_and_save_shipping_label()
        if result.get('success'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Etiqueta Descargada',
                    'message': f'Etiqueta guardada como adjunto: {result.get("filename")}',
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': result.get('error', 'Error desconocido'),
                    'type': 'danger',
                }
            }

    def action_print_shipping_label(self):
        """
        Accion manual para imprimir la etiqueta de envio.
        Primero descarga si no existe, luego envia a la impresora HTTP.
        """
        self.ensure_one()
        if not self.ml_shipment_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Envio',
                    'message': 'Esta orden no tiene ID de envio de MercadoLibre.',
                    'type': 'warning',
                }
            }

        # Obtener configuracion del tipo logistico
        logistic_config = self._get_logistic_type_config()
        if not logistic_config:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Configuracion',
                    'message': 'No hay configuracion de tipo logistico para esta orden.',
                    'type': 'warning',
                }
            }

        # Descargar etiqueta si no existe
        result = self._download_and_save_shipping_label(logistic_config)
        if not result.get('success'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error Descarga',
                    'message': result.get('error', 'Error descargando etiqueta'),
                    'type': 'danger',
                }
            }

        # Enviar a impresora
        print_result = self._send_label_to_printer(
            result['attachment'],
            logistic_config
        )

        if print_result.get('success'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Etiqueta Enviada',
                    'message': f'Etiqueta enviada a impresora: {logistic_config.printer_name}',
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error Impresion',
                    'message': print_result.get('error', 'Error enviando a impresora'),
                    'type': 'danger',
                }
            }

    def _download_and_save_shipping_label(self, logistic_config=None):
        """
        Descarga la etiqueta de envio desde la API de MercadoLibre
        y la guarda como adjunto en la orden de venta.

        Args:
            logistic_config: Configuracion del tipo logistico (opcional)

        Returns:
            dict con 'success', 'attachment', 'filename' o 'error'
        """
        import requests
        import base64
        self.ensure_one()

        if not self.ml_shipment_id:
            return {'success': False, 'error': 'Sin ID de envio'}

        if not self.sale_order_id:
            return {'success': False, 'error': 'Sin orden de venta asociada'}

        # Verificar si ya existe la etiqueta
        existing = self.env['ir.attachment'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', self.sale_order_id.id),
            ('name', 'ilike', f'etiqueta_ml_{self.ml_shipment_id}')
        ], limit=1)

        if existing:
            _logger.info('Etiqueta ya existe para shipment %s', self.ml_shipment_id)
            return {
                'success': True,
                'attachment': existing,
                'filename': existing.name,
                'already_exists': True
            }

        # Obtener token de acceso
        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            _logger.error('Error obteniendo token: %s', str(e))
            return {'success': False, 'error': f'Error de autenticacion: {str(e)}'}

        # Determinar formato de etiqueta
        label_format = 'pdf'
        if logistic_config and logistic_config.label_format:
            label_format = logistic_config.label_format

        # URL para descargar etiqueta
        # Primero intentamos con el endpoint de labels
        url = f'https://api.mercadolibre.com/shipment_labels'
        params = {
            'shipment_ids': self.ml_shipment_id,
            'response_type': label_format,
        }

        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)

            if response.status_code == 200:
                # Determinar extension
                content_type = response.headers.get('Content-Type', '')
                if 'pdf' in content_type or label_format == 'pdf':
                    extension = 'pdf'
                    mimetype = 'application/pdf'
                else:
                    extension = 'zpl'
                    mimetype = 'text/plain'

                filename = f'etiqueta_ml_{self.ml_shipment_id}.{extension}'

                # Crear adjunto
                attachment = self.env['ir.attachment'].create({
                    'name': filename,
                    'type': 'binary',
                    'datas': base64.b64encode(response.content),
                    'res_model': 'sale.order',
                    'res_id': self.sale_order_id.id,
                    'mimetype': mimetype,
                })

                _logger.info('Etiqueta descargada y guardada: %s', filename)

                # Registrar en el chatter
                self.sale_order_id.message_post(
                    body=f'Etiqueta de envio MercadoLibre descargada: {filename}',
                    attachment_ids=[attachment.id]
                )

                return {
                    'success': True,
                    'attachment': attachment,
                    'filename': filename,
                }

            elif response.status_code == 404:
                # Intentar con endpoint alternativo
                return self._download_label_alternative(access_token, label_format)

            else:
                error_msg = f'Error API ML ({response.status_code}): {response.text[:200]}'
                _logger.error('Error descargando etiqueta: %s', error_msg)
                return {'success': False, 'error': error_msg}

        except requests.Timeout:
            return {'success': False, 'error': 'Timeout al conectar con MercadoLibre'}
        except Exception as e:
            _logger.error('Error descargando etiqueta: %s', str(e))
            return {'success': False, 'error': str(e)}

    def _download_label_alternative(self, access_token, label_format='pdf'):
        """
        Metodo alternativo para descargar etiqueta usando el endpoint de shipments.

        Args:
            access_token: Token de acceso
            label_format: Formato de etiqueta (pdf o zpl2)

        Returns:
            dict con resultado
        """
        import requests
        import base64

        url = f'https://api.mercadolibre.com/shipments/{self.ml_shipment_id}/label'
        params = {'response_type': label_format}
        headers = {'Authorization': f'Bearer {access_token}'}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)

            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'pdf' in content_type:
                    extension = 'pdf'
                    mimetype = 'application/pdf'
                else:
                    extension = 'zpl'
                    mimetype = 'text/plain'

                filename = f'etiqueta_ml_{self.ml_shipment_id}.{extension}'

                attachment = self.env['ir.attachment'].create({
                    'name': filename,
                    'type': 'binary',
                    'datas': base64.b64encode(response.content),
                    'res_model': 'sale.order',
                    'res_id': self.sale_order_id.id,
                    'mimetype': mimetype,
                })

                _logger.info('Etiqueta descargada (alt): %s', filename)

                self.sale_order_id.message_post(
                    body=f'Etiqueta de envio MercadoLibre descargada: {filename}',
                    attachment_ids=[attachment.id]
                )

                return {
                    'success': True,
                    'attachment': attachment,
                    'filename': filename,
                }
            else:
                return {
                    'success': False,
                    'error': f'Error endpoint alternativo ({response.status_code})'
                }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _send_label_to_printer(self, attachment, logistic_config):
        """
        Envia la etiqueta a una impresora HTTP.

        Args:
            attachment: ir.attachment con la etiqueta
            logistic_config: mercadolibre.logistic.type con la configuracion

        Returns:
            dict con 'success' o 'error'
        """
        import requests
        import base64

        if not logistic_config.printer_url:
            return {'success': False, 'error': 'URL de impresora no configurada'}

        if not logistic_config.printer_name:
            return {'success': False, 'error': 'Nombre de impresora no configurado'}

        try:
            # Decodificar el archivo
            file_content = base64.b64decode(attachment.datas)

            # Preparar el request multipart/form-data
            files = {
                'file': (attachment.name, file_content, attachment.mimetype or 'application/pdf')
            }
            data = {
                'printer': logistic_config.printer_name,
                'copies': str(logistic_config.printer_copies or 1),
            }

            response = requests.post(
                logistic_config.printer_url,
                files=files,
                data=data,
                timeout=30
            )

            if response.status_code in (200, 201, 202):
                _logger.info('Etiqueta enviada a impresora %s', logistic_config.printer_name)

                # Registrar en el chatter
                if self.sale_order_id:
                    self.sale_order_id.message_post(
                        body=f'Etiqueta enviada a impresora: {logistic_config.printer_name} '
                             f'({logistic_config.printer_copies} copia(s))'
                    )

                return {'success': True}
            else:
                error_msg = f'Error impresora ({response.status_code}): {response.text[:200]}'
                _logger.error('Error enviando a impresora: %s', error_msg)
                return {'success': False, 'error': error_msg}

        except requests.Timeout:
            return {'success': False, 'error': 'Timeout al conectar con impresora'}
        except Exception as e:
            _logger.error('Error enviando a impresora: %s', str(e))
            return {'success': False, 'error': str(e)}

    def _process_shipping_label(self, logistic_config, sale_order):
        """
        Procesa la etiqueta de envio segun la configuracion del tipo logistico.
        Se llama automaticamente despues de crear la orden de venta.

        Args:
            logistic_config: mercadolibre.logistic.type
            sale_order: sale.order creada

        Returns:
            dict con resultados
        """
        result = {
            'downloaded': False,
            'printed': False,
            'errors': []
        }

        if not logistic_config:
            return result

        # Descargar etiqueta si esta configurado
        if logistic_config.download_shipping_label and self.ml_shipment_id:
            download_result = self._download_and_save_shipping_label(logistic_config)

            if download_result.get('success'):
                result['downloaded'] = True
                result['attachment'] = download_result.get('attachment')

                # Imprimir si esta configurado
                if logistic_config.auto_print_label:
                    print_result = self._send_label_to_printer(
                        download_result['attachment'],
                        logistic_config
                    )
                    if print_result.get('success'):
                        result['printed'] = True
                    else:
                        result['errors'].append(
                            f"Error impresion: {print_result.get('error')}"
                        )
            else:
                result['errors'].append(
                    f"Error descarga: {download_result.get('error')}"
                )

        return result
