# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def parse_ml_datetime(date_str):
    """
    Parsea fechas ISO de MercadoLibre al formato que espera Odoo.
    Ejemplos de entrada:
        - '2025-12-31T00:31:41.138Z'
        - '2025-12-31T00:31:41.000-04:00'
        - '2025-12-31 00:31:41'
    """
    if not date_str:
        return False

    # Si ya es un objeto datetime, retornarlo
    if isinstance(date_str, datetime):
        return date_str

    try:
        # Limpiar la cadena
        date_str = str(date_str).strip()

        # Formato ISO con 'Z' (UTC)
        if 'T' in date_str:
            # Remover la 'Z' y milisegundos si existen
            date_str = date_str.replace('Z', '').replace('z', '')

            # Manejar timezone offset (+00:00 o -04:00)
            if '+' in date_str:
                date_str = date_str.split('+')[0]
            elif date_str.count('-') > 2:
                # Tiene offset negativo como -04:00
                parts = date_str.rsplit('-', 1)
                if ':' in parts[-1]:
                    date_str = parts[0]

            # Remover milisegundos (.000)
            if '.' in date_str:
                date_str = date_str.split('.')[0]

            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')

        # Formato simple sin T
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

    except (ValueError, TypeError) as e:
        _logger.warning('Error parseando fecha ML "%s": %s', date_str, str(e))
        return False


class MercadolibreItem(models.Model):
    _name = 'mercadolibre.item'
    _description = 'Publicacion MercadoLibre'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'write_date desc'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )

    # =====================================================
    # IDENTIFICADORES
    # =====================================================
    ml_item_id = fields.Char(
        string='ID Item ML',
        required=True,
        readonly=True,
        index=True,
        tracking=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # =====================================================
    # VINCULACION CON ODOO
    # =====================================================
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Plantilla Producto',
        ondelete='set null',
        index=True,
        tracking=True,
        help='Producto de Odoo vinculado a esta publicacion'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Variante Producto',
        ondelete='set null',
        index=True,
        help='Variante especifica de Odoo (para items sin variaciones ML)'
    )
    is_linked = fields.Boolean(
        string='Vinculado',
        compute='_compute_is_linked',
        store=True
    )

    # =====================================================
    # DATOS DEL ITEM ML
    # =====================================================
    title = fields.Char(
        string='Titulo',
        tracking=True
    )
    category_id = fields.Many2one(
        'mercadolibre.category',
        string='Categoria ML'
    )
    price = fields.Float(
        string='Precio',
        digits='Product Price',
        tracking=True
    )
    original_price = fields.Float(
        string='Precio Original',
        digits='Product Price',
        help='Precio sin descuento'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda'
    )
    available_quantity = fields.Integer(
        string='Stock Disponible ML',
        tracking=True
    )
    initial_quantity = fields.Integer(
        string='Stock Inicial'
    )
    sold_quantity = fields.Integer(
        string='Vendidos',
        readonly=True
    )

    # Condicion y tipo
    condition = fields.Selection([
        ('new', 'Nuevo'),
        ('used', 'Usado'),
        ('not_specified', 'No Especificado'),
    ], string='Condicion')
    listing_type_id = fields.Char(
        string='Tipo Publicacion',
        help='gold_special, gold_pro, gold, silver, bronze, free'
    )
    buying_mode = fields.Selection([
        ('buy_it_now', 'Compra Inmediata'),
        ('auction', 'Subasta'),
    ], string='Modo Compra', default='buy_it_now')

    # =====================================================
    # ESTADO
    # =====================================================
    status = fields.Selection([
        ('active', 'Activo'),
        ('paused', 'Pausado'),
        ('closed', 'Cerrado'),
        ('under_review', 'En Revision'),
        ('inactive', 'Inactivo'),
    ], string='Estado', tracking=True, index=True)
    sub_status = fields.Char(
        string='Sub-estado',
        help='Ej: out_of_stock, deleted'
    )

    # =====================================================
    # SKU Y VINCULACION
    # =====================================================
    seller_custom_field = fields.Char(
        string='seller_custom_field',
        index=True,
        tracking=True,
        help='Campo interno del vendedor (uso libre)'
    )
    seller_sku = fields.Char(
        string='SELLER_SKU',
        index=True,
        tracking=True,
        help='Atributo SELLER_SKU - Visible en ordenes'
    )

    # =====================================================
    # VARIACIONES
    # =====================================================
    variation_ids = fields.One2many(
        'mercadolibre.item.variation',
        'item_id',
        string='Variaciones'
    )
    has_variations = fields.Boolean(
        string='Tiene Variaciones',
        compute='_compute_has_variations',
        store=True
    )
    variation_count = fields.Integer(
        string='Num. Variaciones',
        compute='_compute_has_variations',
        store=True
    )

    # =====================================================
    # IMAGENES Y DESCRIPCION
    # =====================================================
    picture_urls = fields.Text(
        string='URLs Imagenes',
        help='JSON array con URLs de imagenes'
    )
    main_picture_url = fields.Char(
        string='Imagen Principal',
        compute='_compute_main_picture'
    )
    description = fields.Text(
        string='Descripcion'
    )
    permalink = fields.Char(
        string='Link Publicacion'
    )
    thumbnail = fields.Char(
        string='Thumbnail URL'
    )

    # =====================================================
    # SHIPPING
    # =====================================================
    shipping_mode = fields.Char(
        string='Modo Envio'
    )
    free_shipping = fields.Boolean(
        string='Envio Gratis'
    )
    logistic_type = fields.Char(
        string='Tipo Logistico',
        help='fulfillment, cross_docking, drop_off, etc'
    )

    # =====================================================
    # ATRIBUTOS
    # =====================================================
    attributes_json = fields.Text(
        string='Atributos (JSON)',
        help='Atributos del item en formato JSON'
    )
    brand = fields.Char(
        string='Marca',
        compute='_compute_brand_model',
        store=True
    )
    model = fields.Char(
        string='Modelo',
        compute='_compute_brand_model',
        store=True
    )

    # =====================================================
    # FECHAS
    # =====================================================
    date_created = fields.Datetime(
        string='Fecha Creacion ML'
    )
    last_updated = fields.Datetime(
        string='Ultima Actualizacion ML'
    )
    start_time = fields.Datetime(
        string='Fecha Inicio'
    )
    stop_time = fields.Datetime(
        string='Fecha Fin'
    )

    # =====================================================
    # SYNC CONTROL
    # =====================================================
    last_sync = fields.Datetime(
        string='Ultima Sincronizacion',
        readonly=True
    )
    sync_status = fields.Selection([
        ('synced', 'Sincronizado'),
        ('pending_to_ml', 'Pendiente enviar a ML'),
        ('pending_from_ml', 'Pendiente traer de ML'),
        ('error', 'Error'),
    ], string='Estado Sync', default='synced')
    sync_error = fields.Text(
        string='Error de Sync'
    )
    auto_sync_stock = fields.Boolean(
        string='Auto-sync Stock',
        default=True,
        help='Sincronizar stock automaticamente cuando cambie en Odoo'
    )
    auto_sync_price = fields.Boolean(
        string='Auto-sync Precio',
        default=False,
        help='Sincronizar precio automaticamente cuando cambie en Odoo'
    )
    # Opciones para sincronización ML -> Odoo
    sync_price_to_odoo = fields.Boolean(
        string='Sincronizar Precio a Odoo',
        default=True,
        help='Al sincronizar desde ML, actualizar el precio en el producto Odoo'
    )
    sync_stock_to_odoo = fields.Boolean(
        string='Sincronizar Stock a Odoo',
        default=True,
        help='Al sincronizar desde ML, actualizar el stock en Odoo'
    )
    sync_description_to_odoo = fields.Boolean(
        string='Sincronizar Descripción a Odoo',
        default=False,
        help='Al sincronizar desde ML, actualizar la descripción de venta en Odoo'
    )
    sync_images_to_odoo = fields.Boolean(
        string='Sincronizar Imagen a Odoo',
        default=False,
        help='Al sincronizar desde ML, actualizar la imagen principal en Odoo'
    )

    # =====================================================
    # STOCK COMPARISON
    # =====================================================
    odoo_stock = fields.Float(
        string='Stock Odoo',
        compute='_compute_odoo_stock',
        help='Stock disponible en Odoo del producto vinculado'
    )
    stock_difference = fields.Float(
        string='Diferencia Stock',
        compute='_compute_stock_difference',
        store=True,
        help='Diferencia entre stock ML y Odoo (positivo = ML tiene mas)'
    )
    stock_alert = fields.Boolean(
        string='Alerta Stock',
        compute='_compute_stock_difference',
        store=True,
        help='Indica si hay diferencia de stock significativa'
    )

    _sql_constraints = [
        ('ml_item_id_account_uniq', 'unique(ml_item_id, account_id)',
         'El item ya existe para esta cuenta.')
    ]

    @api.depends('title', 'ml_item_id')
    def _compute_name(self):
        for record in self:
            if record.title:
                record.name = f'[{record.ml_item_id}] {record.title[:50]}'
            else:
                record.name = record.ml_item_id or 'Nuevo Item'

    @api.depends('product_tmpl_id', 'product_id')
    def _compute_is_linked(self):
        for record in self:
            record.is_linked = bool(record.product_tmpl_id or record.product_id)

    @api.depends('variation_ids')
    def _compute_has_variations(self):
        for record in self:
            record.variation_count = len(record.variation_ids)
            record.has_variations = record.variation_count > 0

    @api.depends('picture_urls')
    def _compute_main_picture(self):
        for record in self:
            if record.picture_urls:
                try:
                    pictures = json.loads(record.picture_urls)
                    if pictures and len(pictures) > 0:
                        record.main_picture_url = pictures[0].get('url') or pictures[0].get('secure_url', '')
                    else:
                        record.main_picture_url = False
                except (json.JSONDecodeError, TypeError):
                    record.main_picture_url = record.thumbnail or False
            else:
                record.main_picture_url = record.thumbnail or False

    @api.depends('attributes_json')
    def _compute_brand_model(self):
        for record in self:
            record.brand = False
            record.model = False
            if record.attributes_json:
                try:
                    attributes = json.loads(record.attributes_json)
                    for attr in attributes:
                        attr_id = attr.get('id', '')
                        if attr_id == 'BRAND':
                            record.brand = attr.get('value_name', '')
                        elif attr_id == 'MODEL':
                            record.model = attr.get('value_name', '')
                except (json.JSONDecodeError, TypeError):
                    pass

    @api.depends('product_tmpl_id', 'product_id', 'product_tmpl_id.qty_available',
                 'product_id.qty_available', 'variation_ids.product_id.qty_available')
    def _compute_odoo_stock(self):
        for record in self:
            if record.has_variations:
                # Sumar stock de todas las variaciones vinculadas
                total = 0
                for var in record.variation_ids:
                    if var.product_id:
                        total += var.product_id.qty_available
                record.odoo_stock = total
            elif record.product_id:
                record.odoo_stock = record.product_id.qty_available
            elif record.product_tmpl_id:
                record.odoo_stock = record.product_tmpl_id.qty_available
            else:
                record.odoo_stock = 0

    @api.depends('available_quantity', 'odoo_stock', 'product_tmpl_id', 'product_id')
    def _compute_stock_difference(self):
        for record in self:
            if record.is_linked:
                record.stock_difference = record.available_quantity - record.odoo_stock
                record.stock_alert = abs(record.stock_difference) > 0
            else:
                record.stock_difference = 0
                record.stock_alert = False

    # =====================================================
    # CRUD METHODS
    # =====================================================
    @api.model
    def create_from_ml_data(self, data, account):
        """
        Crea o actualiza un item desde datos de la API de ML.

        Args:
            data: dict con datos del item de ML
            account: mercadolibre.account record

        Returns:
            tuple: (mercadolibre.item record, bool is_new)
        """
        ml_item_id = data.get('id')
        if not ml_item_id:
            raise ValidationError(_('El item no tiene ID'))

        existing = self.search([
            ('ml_item_id', '=', ml_item_id),
            ('account_id', '=', account.id)
        ], limit=1)

        # Obtener o crear categoria
        category = False
        if data.get('category_id'):
            CategoryModel = self.env['mercadolibre.category']
            category = CategoryModel.get_or_create_from_ml(data['category_id'])

        # Obtener moneda
        currency = False
        if data.get('currency_id'):
            currency = self.env['res.currency'].search([
                ('name', '=', data['currency_id'])
            ], limit=1)

        # Parsear imagenes
        pictures = data.get('pictures', [])
        picture_urls = json.dumps(pictures) if pictures else False

        # Extraer seller_sku de atributos
        seller_sku = data.get('seller_sku', '')
        attributes = data.get('attributes', [])
        if attributes and not seller_sku:
            for attr in attributes:
                if attr.get('id') == 'SELLER_SKU':
                    seller_sku = attr.get('value_name', '')
                    break

        vals = {
            'ml_item_id': ml_item_id,
            'account_id': account.id,
            'title': data.get('title', ''),
            'category_id': category.id if category else False,
            'price': data.get('price', 0),
            'original_price': data.get('original_price') or data.get('price', 0),
            'currency_id': currency.id if currency else False,
            'available_quantity': data.get('available_quantity', 0),
            'initial_quantity': data.get('initial_quantity', 0),
            'sold_quantity': data.get('sold_quantity', 0),
            'condition': data.get('condition', 'new'),
            'listing_type_id': data.get('listing_type_id', ''),
            'buying_mode': data.get('buying_mode', 'buy_it_now'),
            'status': data.get('status', 'active'),
            'sub_status': ','.join(data.get('sub_status', [])) if data.get('sub_status') else '',
            'seller_custom_field': data.get('seller_custom_field', ''),
            'seller_sku': seller_sku,
            'picture_urls': picture_urls,
            'thumbnail': data.get('thumbnail', ''),
            'permalink': data.get('permalink', ''),
            'description': data.get('description', {}).get('plain_text', '') if isinstance(data.get('description'), dict) else '',
            'shipping_mode': data.get('shipping', {}).get('mode', '') if data.get('shipping') else '',
            'free_shipping': data.get('shipping', {}).get('free_shipping', False) if data.get('shipping') else False,
            'logistic_type': data.get('shipping', {}).get('logistic_type', '') if data.get('shipping') else '',
            'attributes_json': json.dumps(attributes) if attributes else False,
            'date_created': parse_ml_datetime(data.get('date_created')),
            'last_updated': parse_ml_datetime(data.get('last_updated')),
            'start_time': parse_ml_datetime(data.get('start_time')),
            'stop_time': parse_ml_datetime(data.get('stop_time')),
            'last_sync': fields.Datetime.now(),
            'sync_status': 'synced',
            'sync_error': False,
        }

        if existing:
            existing.write(vals)
            item = existing
            is_new = False
        else:
            item = self.create(vals)
            is_new = True

        # Procesar variaciones
        variations = data.get('variations', [])
        if variations:
            VariationModel = self.env['mercadolibre.item.variation']
            # Marcar variaciones existentes como eliminadas si no vienen
            existing_var_ids = item.variation_ids.mapped('ml_variation_id')
            incoming_var_ids = [str(v.get('id')) for v in variations]

            for var_id in existing_var_ids:
                if var_id not in incoming_var_ids:
                    var_record = item.variation_ids.filtered(
                        lambda v: v.ml_variation_id == var_id
                    )
                    if var_record:
                        var_record.write({'active': False})

            for var_data in variations:
                VariationModel.create_from_ml_data(var_data, item)

        return item, is_new

    # =====================================================
    # SYNC METHODS
    # =====================================================
    def action_sync_from_ml(self):
        """
        Sincroniza este item desde MercadoLibre y opcionalmente al producto Odoo.
        Utiliza las opciones configuradas en el registro (sync_price_to_odoo, etc.)
        """
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token valido.'))

        http = self.env['mercadolibre.http']
        try:
            response = http._request(
                account_id=self.account_id.id,
                endpoint=f'/items/{self.ml_item_id}',
                method='GET'
            )
            data = response.get('data', {})
            self.create_from_ml_data(data, self.account_id)

            # Sincronizar al producto Odoo si está vinculado
            odoo_sync_msg = ''
            if self.is_linked:
                result = self.sync_to_odoo_product(
                    sync_price=self.sync_price_to_odoo,
                    sync_stock=self.sync_stock_to_odoo,
                    sync_description=self.sync_description_to_odoo,
                    sync_images=self.sync_images_to_odoo
                )
                if result.get('success'):
                    odoo_sync_msg = '\n' + _('Producto Odoo: %s') % result.get('message', '')
                else:
                    odoo_sync_msg = '\n' + _('Error Odoo: %s') % result.get('message', '')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronizacion Exitosa'),
                    'message': _('El item se sincronizo correctamente.') + odoo_sync_msg,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.write({
                'sync_status': 'error',
                'sync_error': str(e)
            })
            raise UserError(_('Error sincronizando item: %s') % str(e))

    def action_sync_to_odoo_only(self):
        """
        Sincroniza los datos del item actual al producto Odoo vinculado.
        No consulta la API de ML, solo usa los datos ya almacenados.
        """
        self.ensure_one()

        if not self.is_linked:
            raise UserError(_('El item no está vinculado a un producto de Odoo.'))

        result = self.sync_to_odoo_product(
            sync_price=self.sync_price_to_odoo,
            sync_stock=self.sync_stock_to_odoo,
            sync_description=self.sync_description_to_odoo,
            sync_images=self.sync_images_to_odoo
        )

        if result.get('success'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización a Odoo'),
                    'message': result.get('message', _('Completado')),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError(result.get('message', _('Error desconocido')))

    def action_sync_stock_to_ml(self):
        """Envia el stock de Odoo a MercadoLibre"""
        self.ensure_one()

        if not self.is_linked:
            raise UserError(_('El item no esta vinculado a un producto de Odoo.'))

        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token valido.'))

        new_quantity = int(self.odoo_stock)
        http = self.env['mercadolibre.http']

        try:
            if self.has_variations:
                # Actualizar stock por variacion
                for variation in self.variation_ids:
                    if variation.product_id:
                        var_qty = int(variation.product_id.qty_available)
                        http._request(
                            account_id=self.account_id.id,
                            endpoint=f'/items/{self.ml_item_id}/variations/{variation.ml_variation_id}',
                            method='PUT',
                            body={'available_quantity': var_qty}
                        )
                        variation.write({
                            'available_quantity': var_qty,
                            'last_sync': fields.Datetime.now()
                        })
            else:
                # Actualizar stock del item
                http._request(
                    account_id=self.account_id.id,
                    endpoint=f'/items/{self.ml_item_id}',
                    method='PUT',
                    body={'available_quantity': new_quantity}
                )

            self.write({
                'available_quantity': new_quantity,
                'last_sync': fields.Datetime.now(),
                'sync_status': 'synced',
                'sync_error': False,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Stock Actualizado'),
                    'message': _('El stock se actualizo en MercadoLibre: %d unidades.') % new_quantity,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.write({
                'sync_status': 'error',
                'sync_error': str(e)
            })
            raise UserError(_('Error actualizando stock: %s') % str(e))

    def action_sync_price_to_ml(self):
        """Envia el precio de Odoo a MercadoLibre"""
        self.ensure_one()

        if not self.is_linked:
            raise UserError(_('El item no esta vinculado a un producto de Odoo.'))

        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token valido.'))

        # Obtener precio del producto
        product = self.product_id or (self.product_tmpl_id.product_variant_id if self.product_tmpl_id else False)
        if not product:
            raise UserError(_('No se encontro producto vinculado.'))

        new_price = product.lst_price
        http = self.env['mercadolibre.http']

        try:
            http._request(
                account_id=self.account_id.id,
                endpoint=f'/items/{self.ml_item_id}',
                method='PUT',
                body={'price': new_price}
            )

            self.write({
                'price': new_price,
                'last_sync': fields.Datetime.now(),
                'sync_status': 'synced',
                'sync_error': False,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Precio Actualizado'),
                    'message': _('El precio se actualizo en MercadoLibre: $%.2f') % new_price,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.write({
                'sync_status': 'error',
                'sync_error': str(e)
            })
            raise UserError(_('Error actualizando precio: %s') % str(e))

    def action_sync_description_to_ml(self):
        """Envia la descripción del producto de Odoo a MercadoLibre"""
        self.ensure_one()

        if not self.is_linked:
            raise UserError(_('El item no esta vinculado a un producto de Odoo.'))

        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token valido.'))

        # Obtener descripción del producto
        product = self.product_tmpl_id
        if not product:
            raise UserError(_('No se encontro producto vinculado.'))

        new_description = product.description_sale or ''
        if not new_description:
            raise UserError(_('El producto no tiene descripción de venta definida.'))

        http = self.env['mercadolibre.http']

        try:
            # Para items existentes, usar PUT para actualizar la descripción
            http._request(
                account_id=self.account_id.id,
                endpoint=f'/items/{self.ml_item_id}/description',
                method='PUT',
                body={'plain_text': new_description}
            )

            self.write({
                'description': new_description,
                'last_sync': fields.Datetime.now(),
                'sync_status': 'synced',
                'sync_error': False,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Descripción Actualizada'),
                    'message': _('La descripción se actualizó en MercadoLibre (%d caracteres)') % len(new_description),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.write({
                'sync_status': 'error',
                'sync_error': str(e)
            })
            raise UserError(_('Error actualizando descripción: %s') % str(e))

    def action_sync_brand_model_to_ml(self):
        """Envía la marca y modelo del producto de Odoo a MercadoLibre"""
        self.ensure_one()

        if not self.is_linked:
            raise UserError(_('El item no está vinculado a un producto de Odoo.'))

        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token válido.'))

        # Obtener producto
        product = self.product_tmpl_id
        if not product:
            raise UserError(_('No se encontró producto vinculado.'))

        # Obtener marca
        if product.ml_brand:
            brand_name = product.ml_brand
        else:
            brand_name = 'Genérico'

        # Obtener modelo
        if product.ml_model:
            model_name = product.ml_model
        elif product.default_code:
            model_name = product.default_code
        else:
            model_name = product.name[:30] if product.name else 'Estándar'

        http = self.env['mercadolibre.http']

        try:
            # Actualizar atributos via PUT /items/{id}
            attributes = [
                {'id': 'BRAND', 'value_name': brand_name},
                {'id': 'MODEL', 'value_name': model_name},
            ]

            http._request(
                account_id=self.account_id.id,
                endpoint=f'/items/{self.ml_item_id}',
                method='PUT',
                body={'attributes': attributes}
            )

            self.write({
                'brand': brand_name,
                'model': model_name,
                'last_sync': fields.Datetime.now(),
                'sync_status': 'synced',
                'sync_error': False,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Marca y Modelo Actualizados'),
                    'message': _('Se actualizó en MercadoLibre: %s - %s') % (brand_name, model_name),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.write({
                'sync_status': 'error',
                'sync_error': str(e)
            })
            raise UserError(_('Error actualizando marca/modelo: %s') % str(e))

    def action_pause_item(self):
        """Pausa la publicacion en MercadoLibre"""
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token valido.'))

        http = self.env['mercadolibre.http']
        try:
            http._request(
                account_id=self.account_id.id,
                endpoint=f'/items/{self.ml_item_id}',
                method='PUT',
                body={'status': 'paused'}
            )
            self.write({
                'status': 'paused',
                'last_sync': fields.Datetime.now(),
            })
        except Exception as e:
            raise UserError(_('Error pausando item: %s') % str(e))

    def action_activate_item(self):
        """Activa la publicacion en MercadoLibre"""
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token valido.'))

        http = self.env['mercadolibre.http']
        try:
            http._request(
                account_id=self.account_id.id,
                endpoint=f'/items/{self.ml_item_id}',
                method='PUT',
                body={'status': 'active'}
            )
            self.write({
                'status': 'active',
                'last_sync': fields.Datetime.now(),
            })
        except Exception as e:
            raise UserError(_('Error activando item: %s') % str(e))

    def action_view_on_ml(self):
        """Abre la publicacion en MercadoLibre"""
        self.ensure_one()
        if self.permalink:
            return {
                'type': 'ir.actions.act_url',
                'url': self.permalink,
                'target': 'new',
            }

    def action_link_product(self):
        """Abre wizard para vincular producto"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vincular Producto'),
            'res_model': 'mercadolibre.product.link',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_item_id': self.id,
                'default_account_id': self.account_id.id,
            }
        }

    # =====================================================
    # SYNC TO ODOO PRODUCT
    # =====================================================
    def sync_to_odoo_product(self, sync_price=True, sync_stock=True, sync_description=False, sync_images=False):
        """
        Sincroniza los datos del item ML hacia el producto Odoo vinculado.

        Args:
            sync_price: Sincronizar precio (lst_price)
            sync_stock: Sincronizar stock disponible
            sync_description: Sincronizar descripcion de venta
            sync_images: Sincronizar imagen principal

        Returns:
            dict: Resultado de la sincronizacion
        """
        self.ensure_one()

        if not self.is_linked:
            return {'success': False, 'message': _('El item no está vinculado a un producto de Odoo')}

        product_tmpl = self.product_tmpl_id
        if not product_tmpl:
            return {'success': False, 'message': _('No hay producto template vinculado')}

        updates = {}
        messages = []

        # Sincronizar precio
        if sync_price and self.price:
            if product_tmpl.list_price != self.price:
                updates['list_price'] = self.price
                messages.append(_('Precio: $%.2f') % self.price)

        # Sincronizar descripcion
        if sync_description and self.description:
            if product_tmpl.description_sale != self.description:
                updates['description_sale'] = self.description
                messages.append(_('Descripción actualizada'))

        # Sincronizar imagen principal
        if sync_images and self.main_picture_url:
            try:
                import requests
                import base64
                response = requests.get(self.main_picture_url, timeout=30)
                if response.status_code == 200:
                    image_data = base64.b64encode(response.content).decode('utf-8')
                    if image_data:
                        updates['image_1920'] = image_data
                        messages.append(_('Imagen actualizada'))
            except Exception as e:
                _logger.warning('Error descargando imagen: %s', str(e))

        # Aplicar actualizaciones al producto
        if updates:
            try:
                product_tmpl.write(updates)
            except Exception as e:
                return {'success': False, 'message': _('Error actualizando producto: %s') % str(e)}

        # Sincronizar stock
        if sync_stock:
            try:
                self._sync_stock_to_odoo_product()
                messages.append(_('Stock: %d unidades') % self.available_quantity)
            except Exception as e:
                _logger.warning('Error sincronizando stock: %s', str(e))
                messages.append(_('Error en stock: %s') % str(e))

        return {
            'success': True,
            'message': ', '.join(messages) if messages else _('Sin cambios'),
            'fields_updated': list(updates.keys())
        }

    def _sync_stock_to_odoo_product(self):
        """
        Sincroniza el stock del item ML al producto Odoo.
        Crea o actualiza el quant en la ubicacion de stock.
        """
        self.ensure_one()

        if not self.is_linked:
            return False

        product = self.product_id or (self.product_tmpl_id.product_variant_id if self.product_tmpl_id else False)
        if not product:
            return False

        # Obtener ubicacion de stock principal
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([], limit=1)

        if not warehouse:
            _logger.warning('No se encontró almacén para sincronizar stock')
            return False

        location = warehouse.lot_stock_id

        # Buscar quant existente
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ], limit=1)

        new_qty = self.available_quantity

        if quant:
            # Actualizar quant existente
            if quant.quantity != new_qty:
                quant.sudo().write({'quantity': new_qty})
                _logger.info('Stock actualizado para %s: %d -> %d', product.default_code or product.name, quant.quantity, new_qty)
        else:
            # Crear nuevo quant
            self.env['stock.quant'].sudo().create({
                'product_id': product.id,
                'location_id': location.id,
                'quantity': new_qty,
            })
            _logger.info('Stock creado para %s: %d', product.default_code or product.name, new_qty)

        return True

    def action_auto_link_by_sku(self):
        """Intenta vincular automaticamente por SKU"""
        linked_count = 0
        for item in self:
            if item.is_linked:
                continue

            product = False
            # Buscar por seller_sku
            if item.seller_sku:
                product = self.env['product.product'].search([
                    ('default_code', '=', item.seller_sku)
                ], limit=1)

            # Si no, buscar por seller_custom_field
            if not product and item.seller_custom_field:
                product = self.env['product.product'].search([
                    ('default_code', '=', item.seller_custom_field)
                ], limit=1)

            if product:
                item.write({
                    'product_id': product.id,
                    'product_tmpl_id': product.product_tmpl_id.id,
                })
                linked_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vinculacion Automatica'),
                'message': _('Se vincularon %d items.') % linked_count,
                'type': 'success' if linked_count > 0 else 'warning',
                'sticky': False,
            }
        }
