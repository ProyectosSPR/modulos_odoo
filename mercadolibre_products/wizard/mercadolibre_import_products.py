# -*- coding: utf-8 -*-

import base64
import logging
import requests
import time
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MercadolibreImportProducts(models.TransientModel):
    _name = 'mercadolibre.import.products'
    _description = 'Importar Productos desde MercadoLibre'

    # =====================================================
    # CONFIGURACIÓN
    # =====================================================
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta MercadoLibre',
        required=True,
        domain="[('state', '=', 'connected')]"
    )

    # =====================================================
    # FILTROS DE BÚSQUEDA
    # =====================================================
    filter_status = fields.Selection([
        ('active', 'Solo Activos'),
        ('paused', 'Solo Pausados'),
        ('active_paused', 'Activos y Pausados'),
        ('all', 'Todos (incluye cerrados)'),
    ], string='Estado en ML', default='active_paused')

    filter_unlinked_only = fields.Boolean(
        string='Solo items sin vincular',
        default=True,
        help='Solo mostrar items que no están vinculados a un producto de Odoo'
    )

    filter_category_id = fields.Many2one(
        'mercadolibre.category',
        string='Categoría ML',
        help='Filtrar por categoría de MercadoLibre (opcional)'
    )

    filter_search_text = fields.Char(
        string='Buscar por texto',
        help='Buscar items que contengan este texto en el título'
    )

    # =====================================================
    # OPCIONES DE IMPORTACIÓN
    # =====================================================
    create_products = fields.Boolean(
        string='Crear productos nuevos en Odoo',
        default=True,
        help='Si está activo, creará productos de Odoo para los items seleccionados'
    )

    download_images = fields.Boolean(
        string='Descargar imágenes',
        default=True,
        help='Descarga las imágenes de MercadoLibre y las guarda en el producto de Odoo'
    )

    download_extra_images = fields.Boolean(
        string='Incluir imágenes adicionales',
        default=True,
        help='Además de la imagen principal, descarga las imágenes adicionales'
    )

    import_stock = fields.Boolean(
        string='Importar stock inicial',
        default=True,
        help='Crea el stock inicial en Odoo basado en la cantidad disponible en ML'
    )

    import_description = fields.Boolean(
        string='Importar descripción',
        default=True,
        help='Importa la descripción del producto desde MercadoLibre'
    )

    set_ml_category = fields.Boolean(
        string='Asignar categoría ML al producto',
        default=True,
        help='Configura la categoría ML en el producto de Odoo para futuras publicaciones'
    )

    # =====================================================
    # DESTINO EN ODOO
    # =====================================================
    stock_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación de Stock',
        domain="[('usage', '=', 'internal')]",
        help='Ubicación donde se creará el stock inicial'
    )

    product_category_id = fields.Many2one(
        'product.category',
        string='Categoría de Producto Odoo',
        help='Categoría por defecto para los productos creados'
    )

    # =====================================================
    # ESTADO DEL WIZARD
    # =====================================================
    state = fields.Selection([
        ('draft', 'Configuración'),
        ('preview', 'Vista Previa'),
        ('importing', 'Importando'),
        ('done', 'Completado'),
    ], string='Estado', default='draft')

    # =====================================================
    # LÍNEAS DE PREVIEW
    # =====================================================
    preview_line_ids = fields.One2many(
        'mercadolibre.import.products.line',
        'wizard_id',
        string='Items a Importar'
    )

    # =====================================================
    # CONTADORES
    # =====================================================
    total_found = fields.Integer(
        string='Items Encontrados',
        readonly=True
    )
    total_to_import = fields.Integer(
        string='Items a Importar',
        compute='_compute_totals'
    )
    total_already_linked = fields.Integer(
        string='Ya Vinculados',
        compute='_compute_totals'
    )

    # =====================================================
    # RESULTADOS
    # =====================================================
    imported_count = fields.Integer(string='Importados', readonly=True)
    error_count = fields.Integer(string='Errores', readonly=True)
    skipped_count = fields.Integer(string='Omitidos', readonly=True)
    import_log = fields.Text(string='Log de Importación', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Ubicación por defecto
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if warehouse:
            res['stock_location_id'] = warehouse.lot_stock_id.id
        return res

    @api.depends('preview_line_ids', 'preview_line_ids.selected', 'preview_line_ids.is_linked')
    def _compute_totals(self):
        for record in self:
            record.total_to_import = len(record.preview_line_ids.filtered(
                lambda l: l.selected and not l.is_linked
            ))
            record.total_already_linked = len(record.preview_line_ids.filtered(
                lambda l: l.is_linked
            ))

    # =====================================================
    # ACCIÓN: BUSCAR ITEMS
    # =====================================================
    def action_search_items(self):
        """Busca items en MercadoLibre según los filtros"""
        self.ensure_one()

        if not self.account_id:
            raise ValidationError(_('Seleccione una cuenta de MercadoLibre.'))

        # Limpiar líneas anteriores
        self.preview_line_ids.unlink()

        http = self.env['mercadolibre.http']
        ItemModel = self.env['mercadolibre.item']

        # Construir parámetros de búsqueda
        params = {'limit': 100}

        # Filtro de estado
        if self.filter_status == 'active':
            params['status'] = 'active'
        elif self.filter_status == 'paused':
            params['status'] = 'paused'
        elif self.filter_status == 'active_paused':
            params['status'] = 'active,paused'
        # 'all' no pone filtro de status

        # Filtro de categoría
        if self.filter_category_id:
            params['category'] = self.filter_category_id.ml_category_id

        # Filtro de texto
        if self.filter_search_text:
            params['q'] = self.filter_search_text

        try:
            # Obtener lista de IDs de items
            response = http._request(
                account_id=self.account_id.id,
                endpoint=f'/users/{self.account_id.ml_user_id}/items/search',
                method='GET',
                params=params
            )

            item_ids = response.get('data', {}).get('results', [])
            total_found = len(item_ids)

            if not item_ids:
                self.write({
                    'state': 'preview',
                    'total_found': 0
                })
                return self._return_wizard_action()

            # Obtener detalles de cada item (en lotes de 20)
            lines_data = []
            batch_size = 20

            for i in range(0, len(item_ids), batch_size):
                batch_ids = item_ids[i:i + batch_size]
                ids_param = ','.join(batch_ids)

                try:
                    items_response = http._request(
                        account_id=self.account_id.id,
                        endpoint='/items',
                        method='GET',
                        params={'ids': ids_param}
                    )

                    items_data = items_response.get('data', [])

                    for item_data in items_data:
                        if item_data.get('code') == 200:
                            body = item_data.get('body', {})
                            ml_item_id = body.get('id')

                            # Verificar si ya está vinculado
                            existing_item = ItemModel.search([
                                ('ml_item_id', '=', ml_item_id),
                                ('account_id', '=', self.account_id.id)
                            ], limit=1)

                            is_linked = existing_item and existing_item.product_tmpl_id
                            linked_product = existing_item.product_tmpl_id if is_linked else False

                            # Aplicar filtro de no vinculados
                            if self.filter_unlinked_only and is_linked:
                                continue

                            # Obtener primera imagen
                            pictures = body.get('pictures', [])
                            thumbnail = pictures[0].get('secure_url', '') if pictures else ''

                            # Obtener SKU
                            seller_sku = ''
                            for attr in body.get('attributes', []):
                                if attr.get('id') == 'SELLER_SKU':
                                    seller_sku = attr.get('value_name', '')
                                    break

                            lines_data.append({
                                'wizard_id': self.id,
                                'ml_item_id': ml_item_id,
                                'title': body.get('title', ''),
                                'seller_sku': seller_sku,
                                'price': body.get('price', 0),
                                'currency_id': body.get('currency_id', 'MXN'),
                                'available_quantity': body.get('available_quantity', 0),
                                'status': body.get('status', ''),
                                'category_id': body.get('category_id', ''),
                                'thumbnail_url': thumbnail,
                                'pictures_count': len(pictures),
                                'condition': body.get('condition', 'new'),
                                'is_linked': is_linked,
                                'linked_product_id': linked_product.id if linked_product else False,
                                'selected': not is_linked,  # Pre-seleccionar los no vinculados
                                'item_data_json': str(body),  # Guardar datos completos
                            })

                except Exception as e:
                    _logger.warning('Error obteniendo lote de items: %s', str(e))
                    continue

                # Rate limit
                time.sleep(0.2)

            # Crear líneas de preview
            if lines_data:
                self.env['mercadolibre.import.products.line'].create(lines_data)

            self.write({
                'state': 'preview',
                'total_found': total_found
            })

        except Exception as e:
            raise UserError(_('Error buscando items en MercadoLibre: %s') % str(e))

        return self._return_wizard_action()

    # =====================================================
    # ACCIÓN: IMPORTAR
    # =====================================================
    def action_import(self):
        """Importa los items seleccionados creando productos en Odoo"""
        self.ensure_one()

        if not self.create_products:
            raise ValidationError(_('Debe activar "Crear productos nuevos en Odoo".'))

        # Obtener líneas seleccionadas que no están vinculadas
        lines_to_import = self.preview_line_ids.filtered(
            lambda l: l.selected and not l.is_linked
        )

        if not lines_to_import:
            raise ValidationError(_('No hay items seleccionados para importar.'))

        self.write({'state': 'importing'})

        log_lines = []
        log_lines.append('=' * 60)
        log_lines.append('    IMPORTACIÓN DE PRODUCTOS DESDE MERCADOLIBRE')
        log_lines.append('=' * 60)
        log_lines.append(f'  Cuenta: {self.account_id.name}')
        log_lines.append(f'  Fecha: {fields.Datetime.now()}')
        log_lines.append(f'  Items a importar: {len(lines_to_import)}')
        log_lines.append('')
        log_lines.append('-' * 60)

        http = self.env['mercadolibre.http']
        ItemModel = self.env['mercadolibre.item']
        ProductModel = self.env['product.template']
        CategoryModel = self.env['mercadolibre.category']

        imported_count = 0
        error_count = 0
        skipped_count = 0

        for line in lines_to_import:
            try:
                # 1. Obtener datos completos del item (incluyendo descripción)
                item_response = http._request(
                    account_id=self.account_id.id,
                    endpoint=f'/items/{line.ml_item_id}',
                    method='GET'
                )
                item_data = item_response.get('data', {})

                # 2. Obtener descripción
                description = ''
                if self.import_description:
                    try:
                        desc_response = http._request(
                            account_id=self.account_id.id,
                            endpoint=f'/items/{line.ml_item_id}/description',
                            method='GET'
                        )
                        description = desc_response.get('data', {}).get('plain_text', '')
                    except Exception:
                        pass

                # 3. Descargar imagen principal
                image_base64 = False
                extra_images = []
                if self.download_images:
                    pictures = item_data.get('pictures', [])
                    if pictures:
                        # Imagen principal
                        main_pic_url = pictures[0].get('secure_url') or pictures[0].get('url')
                        if main_pic_url:
                            image_base64 = self._download_image_to_base64(main_pic_url)

                        # Imágenes adicionales
                        if self.download_extra_images and len(pictures) > 1:
                            for pic in pictures[1:10]:  # Máximo 9 adicionales
                                pic_url = pic.get('secure_url') or pic.get('url')
                                if pic_url:
                                    extra_img = self._download_image_to_base64(pic_url)
                                    if extra_img:
                                        extra_images.append(extra_img)

                # 4. Obtener/crear categoría ML
                ml_category = False
                if self.set_ml_category and item_data.get('category_id'):
                    ml_category = CategoryModel.search([
                        ('ml_category_id', '=', item_data.get('category_id'))
                    ], limit=1)
                    if not ml_category:
                        ml_category = CategoryModel.get_or_create_from_ml(
                            item_data.get('category_id'), 'MLM', self.account_id
                        )

                # 5. Extraer marca y modelo
                brand = ''
                model = ''
                seller_sku = ''
                for attr in item_data.get('attributes', []):
                    attr_id = attr.get('id', '')
                    if attr_id == 'BRAND':
                        brand = attr.get('value_name', '')
                    elif attr_id == 'MODEL':
                        model = attr.get('value_name', '')
                    elif attr_id == 'SELLER_SKU':
                        seller_sku = attr.get('value_name', '')

                # 6. Crear producto en Odoo
                product_vals = {
                    'name': item_data.get('title', line.title),
                    'list_price': item_data.get('price', line.price),
                    'type': 'product',  # Almacenable
                    'sale_ok': True,
                    'purchase_ok': True,
                }

                if seller_sku:
                    product_vals['default_code'] = seller_sku

                if description:
                    product_vals['description_sale'] = description

                if image_base64:
                    product_vals['image_1920'] = image_base64

                if self.product_category_id:
                    product_vals['categ_id'] = self.product_category_id.id

                # Campos ML
                if ml_category:
                    product_vals['ml_category_id'] = ml_category.id
                if brand:
                    product_vals['ml_brand'] = brand
                if model:
                    product_vals['ml_model'] = model

                product = ProductModel.create(product_vals)

                # 7. Agregar imágenes adicionales
                if extra_images:
                    for idx, extra_img in enumerate(extra_images):
                        self.env['product.image'].create({
                            'product_tmpl_id': product.id,
                            'name': f'{product.name} - Imagen {idx + 2}',
                            'image_1920': extra_img,
                        })

                # 8. Crear/actualizar item ML y vincular
                item, _ = ItemModel.create_from_ml_data(item_data, self.account_id)
                item.write({
                    'product_tmpl_id': product.id,
                    'product_id': product.product_variant_id.id,
                })

                # 9. Crear stock inicial
                if self.import_stock and self.stock_location_id:
                    qty = item_data.get('available_quantity', 0)
                    if qty > 0:
                        self._create_stock_quant(
                            product.product_variant_id,
                            qty,
                            self.stock_location_id
                        )

                # 10. Actualizar línea
                line.write({
                    'is_linked': True,
                    'linked_product_id': product.id,
                    'import_status': 'success',
                    'import_message': f'Producto creado: {product.default_code or product.id}',
                })

                imported_count += 1
                log_lines.append(f'  [OK] {line.title[:45]}')
                log_lines.append(f'       → Producto: {product.name} (ID: {product.id})')

                # Rate limit
                time.sleep(0.3)

            except Exception as e:
                error_count += 1
                error_msg = str(e)[:200]
                line.write({
                    'import_status': 'error',
                    'import_message': error_msg,
                })
                log_lines.append(f'  [ERROR] {line.title[:45]}')
                log_lines.append(f'          {error_msg}')
                _logger.error('Error importando %s: %s', line.ml_item_id, str(e))

        # Resumen
        log_lines.append('')
        log_lines.append('=' * 60)
        log_lines.append('  RESUMEN')
        log_lines.append('=' * 60)
        log_lines.append(f'  Importados: {imported_count}')
        log_lines.append(f'  Errores:    {error_count}')
        log_lines.append(f'  Omitidos:   {skipped_count}')
        log_lines.append('=' * 60)

        self.write({
            'state': 'done',
            'imported_count': imported_count,
            'error_count': error_count,
            'skipped_count': skipped_count,
            'import_log': '\n'.join(log_lines),
        })

        return self._return_wizard_action()

    # =====================================================
    # MÉTODOS AUXILIARES
    # =====================================================
    def _download_image_to_base64(self, url):
        """Descarga una imagen desde URL y la convierte a base64"""
        if not url:
            return False

        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return base64.b64encode(response.content).decode('utf-8')
        except Exception as e:
            _logger.warning('Error descargando imagen %s: %s', url, str(e))

        return False

    def _create_stock_quant(self, product, qty, location):
        """Crea o actualiza el quant de stock para el producto"""
        if qty <= 0:
            return

        StockQuant = self.env['stock.quant']

        # Buscar quant existente
        quant = StockQuant.search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ], limit=1)

        if quant:
            quant.write({'quantity': qty})
        else:
            StockQuant.create({
                'product_id': product.id,
                'location_id': location.id,
                'quantity': qty,
            })

        _logger.info('Stock creado para %s: %s unidades en %s',
                    product.display_name, qty, location.display_name)

    def _return_wizard_action(self):
        """Retorna la acción para reabrir el wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importar Productos desde MercadoLibre'),
            'res_model': 'mercadolibre.import.products',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back(self):
        """Volver a configuración"""
        self.write({'state': 'draft'})
        self.preview_line_ids.unlink()
        return self._return_wizard_action()

    def action_view_products(self):
        """Ver productos importados"""
        product_ids = self.preview_line_ids.filtered(
            lambda l: l.linked_product_id
        ).mapped('linked_product_id').ids

        return {
            'type': 'ir.actions.act_window',
            'name': _('Productos Importados'),
            'res_model': 'product.template',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', product_ids)],
        }

    def action_select_all(self):
        """Seleccionar todos los items no vinculados"""
        self.preview_line_ids.filtered(lambda l: not l.is_linked).write({'selected': True})
        return self._return_wizard_action()

    def action_deselect_all(self):
        """Deseleccionar todos los items"""
        self.preview_line_ids.write({'selected': False})
        return self._return_wizard_action()


class MercadolibreImportProductsLine(models.TransientModel):
    _name = 'mercadolibre.import.products.line'
    _description = 'Línea de Importación de Productos ML'

    wizard_id = fields.Many2one(
        'mercadolibre.import.products',
        string='Wizard',
        ondelete='cascade'
    )

    # Datos del item ML
    ml_item_id = fields.Char(string='ID Item ML', readonly=True)
    title = fields.Char(string='Título', readonly=True)
    seller_sku = fields.Char(string='SKU', readonly=True)
    price = fields.Float(string='Precio', readonly=True)
    currency_id = fields.Char(string='Moneda', readonly=True)
    available_quantity = fields.Integer(string='Stock ML', readonly=True)
    status = fields.Char(string='Estado ML', readonly=True)
    category_id = fields.Char(string='Categoría ML', readonly=True)
    thumbnail_url = fields.Char(string='URL Imagen', readonly=True)
    pictures_count = fields.Integer(string='# Imágenes', readonly=True)
    condition = fields.Char(string='Condición', readonly=True)

    # Estado de vinculación
    is_linked = fields.Boolean(string='Vinculado', readonly=True)
    linked_product_id = fields.Many2one(
        'product.template',
        string='Producto Odoo',
        readonly=True
    )

    # Selección
    selected = fields.Boolean(string='Seleccionar', default=True)

    # Resultado de importación
    import_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('success', 'Importado'),
        ('error', 'Error'),
        ('skipped', 'Omitido'),
    ], string='Estado Import', default='pending')
    import_message = fields.Char(string='Mensaje')

    # Datos completos (para importación)
    item_data_json = fields.Text(string='Datos JSON')
