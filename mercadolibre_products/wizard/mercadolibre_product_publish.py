# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MercadolibreProductPublish(models.TransientModel):
    _name = 'mercadolibre.product.publish'
    _description = 'Asistente para Publicar Productos en MercadoLibre'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]"
    )
    site_id = fields.Selection([
        ('MLM', 'Mexico (MLM)'),
        ('MLA', 'Argentina (MLA)'),
        ('MLB', 'Brasil (MLB)'),
        ('MLC', 'Chile (MLC)'),
        ('MCO', 'Colombia (MCO)'),
        ('MLU', 'Uruguay (MLU)'),
        ('MPE', 'Peru (MPE)'),
        ('MLV', 'Venezuela (MLV)'),
    ], string='Sitio ML', default='MLM', required=True,
       help='Sitio de MercadoLibre para obtener categorias')

    # Productos a publicar
    product_tmpl_ids = fields.Many2many(
        'product.template',
        string='Productos',
        required=True
    )
    product_count = fields.Integer(
        string='Cantidad',
        compute='_compute_product_count'
    )

    # Configuracion de publicacion
    listing_type_id = fields.Selection([
        ('gold_special', 'Clásico (gold_special)'),
        ('gold_pro', 'Premium (gold_pro)'),
        ('gold', 'Oro'),
        ('silver', 'Plata'),
        ('bronze', 'Bronce'),
        ('free', 'Gratuito'),
    ], string='Tipo Publicación', default='free', required=True,
       help='Gratuito solo disponible en algunas categorías. Use Clásico si falla.')

    condition = fields.Selection([
        ('new', 'Nuevo'),
        ('used', 'Usado'),
    ], string='Condicion', default='new', required=True)

    buying_mode = fields.Selection([
        ('buy_it_now', 'Compra Inmediata'),
    ], string='Modo Compra', default='buy_it_now', required=True)

    # Categoria ML - Sistema en cascada (3 niveles)
    category_level_1 = fields.Many2one(
        'mercadolibre.category',
        string='Categoria Principal',
        domain="[('site_id', '=', site_id), ('parent_id', '=', False)]",
        help='Seleccione la categoria principal'
    )
    category_level_2 = fields.Many2one(
        'mercadolibre.category',
        string='Subcategoria',
        domain="[('parent_id', '=', category_level_1)]",
        help='Seleccione la subcategoria'
    )
    category_level_3 = fields.Many2one(
        'mercadolibre.category',
        string='Subcategoria Final',
        domain="[('parent_id', '=', category_level_2)]",
        help='Seleccione la subcategoria final (si aplica)'
    )
    # Categoria final seleccionada (la mas especifica elegida)
    category_id = fields.Many2one(
        'mercadolibre.category',
        string='Categoria Seleccionada',
        compute='_compute_category_id',
        store=True,
        help='Categoria final que se usara para publicar'
    )
    ml_category_id = fields.Char(
        string='ID Categoria ML',
        related='category_id.ml_category_id',
        readonly=True,
        store=False
    )
    category_path = fields.Char(
        string='Ruta Categoria',
        related='category_id.path_from_root',
        readonly=True,
        store=False
    )
    # Indicadores para saber si hay mas niveles
    has_level_2 = fields.Boolean(
        compute='_compute_has_sublevels',
        string='Tiene Nivel 2'
    )
    has_level_3 = fields.Boolean(
        compute='_compute_has_sublevels',
        string='Tiene Nivel 3'
    )

    # Opciones
    use_product_price = fields.Boolean(
        string='Usar Precio del Producto',
        default=True
    )
    custom_price = fields.Float(
        string='Precio Personalizado',
        digits='Product Price'
    )
    use_product_stock = fields.Boolean(
        string='Usar Stock del Producto',
        default=True
    )
    custom_stock = fields.Integer(
        string='Stock Personalizado',
        default=1
    )

    # SKU
    sku_field = fields.Selection([
        ('default_code', 'Referencia Interna (default_code)'),
        ('barcode', 'Codigo de Barras'),
        ('custom', 'Personalizado'),
    ], string='Campo SKU', default='default_code')
    custom_sku = fields.Char(
        string='SKU Personalizado'
    )

    # Shipping
    shipping_mode = fields.Selection([
        ('me2', 'Mercado Envios'),
        ('not_specified', 'A convenir'),
    ], string='Modo Envío', default='me2')
    free_shipping = fields.Boolean(
        string='Envío Gratis',
        default=False
    )
    local_pick_up = fields.Boolean(
        string='Retiro en Persona',
        default=False,
        help='Permitir que el comprador retire el producto en persona'
    )

    # Garantía
    warranty_type = fields.Selection([
        ('Garantía del vendedor', 'Garantía del vendedor'),
        ('Garantía de fábrica', 'Garantía de fábrica'),
        ('Sin garantía', 'Sin garantía'),
    ], string='Tipo Garantía', default='Garantía del vendedor')
    warranty_time = fields.Char(
        string='Tiempo Garantía',
        default='30 días',
        help='Ej: 30 días, 6 meses, 1 año'
    )

    # GTIN/EAN/UPC
    use_barcode_as_gtin = fields.Boolean(
        string='Usar Código de Barras como GTIN',
        default=True,
        help='Si el producto tiene código de barras, enviarlo como GTIN a MercadoLibre'
    )

    # Tiempo de preparación
    manufacturing_time = fields.Integer(
        string='Días de Preparación',
        default=1,
        help='Días que tardas en tener listo el producto para entregar'
    )

    # Imágenes
    image_source = fields.Selection([
        ('none', 'Sin Imágenes'),
        ('upload_ml', 'Subir a MercadoLibre (Automático)'),
        ('url', 'URL Pública Manual'),
        ('existing_ml', 'Usar Imágenes ya Subidas'),
    ], string='Fuente de Imágenes', default='upload_ml',
       help='Seleccione cómo manejar las imágenes de los productos.')
    custom_image_urls = fields.Text(
        string='URLs de Imágenes',
        help='Ingrese una URL por línea. MercadoLibre acepta hasta 10 imágenes por publicación.'
    )
    image_resize_option = fields.Selection([
        ('none', 'No redimensionar (puede fallar si es pequeña)'),
        ('auto', 'Redimensionar automáticamente a 1200px (Recomendado)'),
        ('min', 'Redimensionar a 500px (mínimo ML)'),
    ], string='Redimensionar Imágenes', default='auto',
       help='Si la imagen es menor a 500px, MercadoLibre la rechazará. '
            'Seleccione cómo manejar imágenes pequeñas.')

    # Tipos de publicación disponibles (se obtienen de la API)
    available_listing_types = fields.Text(
        string='Tipos Disponibles',
        readonly=True,
        help='Tipos de publicación disponibles para la categoría seleccionada'
    )

    # Resultado
    state = fields.Selection([
        ('draft', 'Configuracion'),
        ('preview', 'Vista Previa'),
        ('done', 'Publicado'),
        ('error', 'Error'),
    ], string='Estado', default='draft')

    publish_log = fields.Text(
        string='Log',
        readonly=True
    )
    published_count = fields.Integer(
        string='Publicados',
        readonly=True
    )
    error_count = fields.Integer(
        string='Errores',
        readonly=True
    )

    @api.depends('product_tmpl_ids')
    def _compute_product_count(self):
        for record in self:
            record.product_count = len(record.product_tmpl_ids)

    @api.depends('category_level_1', 'category_level_2', 'category_level_3')
    def _compute_category_id(self):
        """Determina la categoria final (la mas especifica seleccionada)"""
        for record in self:
            if record.category_level_3:
                record.category_id = record.category_level_3
            elif record.category_level_2:
                record.category_id = record.category_level_2
            elif record.category_level_1:
                record.category_id = record.category_level_1
            else:
                record.category_id = False

    @api.depends('category_level_1', 'category_level_2')
    def _compute_has_sublevels(self):
        """Verifica si hay subcategorias disponibles para cada nivel"""
        CategoryModel = self.env['mercadolibre.category']
        for record in self:
            # Verificar nivel 2
            if record.category_level_1:
                record.has_level_2 = CategoryModel.search_count([
                    ('parent_id', '=', record.category_level_1.id)
                ]) > 0
            else:
                record.has_level_2 = False

            # Verificar nivel 3
            if record.category_level_2:
                record.has_level_3 = CategoryModel.search_count([
                    ('parent_id', '=', record.category_level_2.id)
                ]) > 0
            else:
                record.has_level_3 = False

    @api.model
    def default_get(self, fields_list):
        """Sincroniza categorias automaticamente al abrir el wizard"""
        res = super().default_get(fields_list)

        # Sincronizar categorias raiz si no hay ninguna
        CategoryModel = self.env['mercadolibre.category']
        site_id = res.get('site_id', 'MLM')

        existing_categories = CategoryModel.search_count([
            ('site_id', '=', site_id),
            ('parent_id', '=', False)  # Solo raiz
        ])

        if existing_categories == 0:
            try:
                CategoryModel.action_sync_root_categories(site_id=site_id)
            except Exception:
                pass  # Silenciar errores de conexion

        return res

    @api.onchange('account_id')
    def _onchange_account_id(self):
        """Usa el sitio configurado en la cuenta"""
        if self.account_id and self.account_id.site_id:
            self.site_id = self.account_id.site_id

    @api.onchange('site_id')
    def _onchange_site_id(self):
        """Sincroniza categorias cuando cambia el sitio y limpia seleccion"""
        if self.site_id:
            CategoryModel = self.env['mercadolibre.category']
            existing = CategoryModel.search_count([
                ('site_id', '=', self.site_id),
                ('parent_id', '=', False)
            ])
            if existing == 0:
                try:
                    CategoryModel.action_sync_root_categories(site_id=self.site_id)
                except Exception:
                    pass
            # Limpiar selecciones
            self.category_level_1 = False
            self.category_level_2 = False
            self.category_level_3 = False

    @api.onchange('category_level_1')
    def _onchange_category_level_1(self):
        """Carga subcategorias del nivel 1 y limpia niveles inferiores"""
        self.category_level_2 = False
        self.category_level_3 = False

        if self.category_level_1:
            # Cargar subcategorias automaticamente
            CategoryModel = self.env['mercadolibre.category']
            existing_children = CategoryModel.search_count([
                ('parent_id', '=', self.category_level_1.id)
            ])
            if existing_children == 0:
                try:
                    CategoryModel.action_sync_subcategories(
                        self.category_level_1.ml_category_id,
                        self.site_id or 'MLM'
                    )
                except Exception:
                    pass

    @api.onchange('category_level_2')
    def _onchange_category_level_2(self):
        """Carga subcategorias del nivel 2 y limpia nivel 3"""
        self.category_level_3 = False

        if self.category_level_2:
            # Cargar subcategorias automaticamente
            CategoryModel = self.env['mercadolibre.category']
            existing_children = CategoryModel.search_count([
                ('parent_id', '=', self.category_level_2.id)
            ])
            if existing_children == 0:
                try:
                    CategoryModel.action_sync_subcategories(
                        self.category_level_2.ml_category_id,
                        self.site_id or 'MLM'
                    )
                except Exception:
                    pass

    @api.onchange('category_level_3')
    def _onchange_category_level_3(self):
        """Carga subcategorias del nivel 3 si las hay"""
        if self.category_level_3:
            # Verificar si hay mas niveles (para futuras extensiones)
            CategoryModel = self.env['mercadolibre.category']
            existing_children = CategoryModel.search_count([
                ('parent_id', '=', self.category_level_3.id)
            ])
            if existing_children == 0:
                try:
                    CategoryModel.action_sync_subcategories(
                        self.category_level_3.ml_category_id,
                        self.site_id or 'MLM'
                    )
                except Exception:
                    pass

    def _get_product_pictures(self, product):
        """
        Obtiene las URLs de imágenes para publicar.

        Args:
            product: product.template record

        Returns:
            list: Lista de diccionarios {'source': url} para la API de ML
        """
        pictures = []

        if self.image_source == 'none':
            return []

        elif self.image_source == 'upload_ml':
            # Subir imágenes automáticamente a MercadoLibre
            ImageService = self.env['mercadolibre.image.service']
            ImageModel = self.env['mercadolibre.image']

            # Determinar si redimensionar
            target_size = None
            auto_resize = self.image_resize_option != 'none'

            if self.image_resize_option == 'auto':
                target_size = 1200  # Recomendado
            elif self.image_resize_option == 'min':
                target_size = 500  # Mínimo

            # Lista de imágenes a subir: (imagen_base64, nombre_archivo)
            images_to_upload = []

            # 1. Imagen principal
            if product.image_1920:
                img_b64 = product.image_1920
                if isinstance(img_b64, bytes):
                    img_b64 = img_b64.decode('utf-8')
                images_to_upload.append((img_b64, f'{product.default_code or product.id}_main.jpg'))

            # 2. Imágenes adicionales (product.template.image)
            if hasattr(product, 'product_template_image_ids') and product.product_template_image_ids:
                for idx, extra_img in enumerate(product.product_template_image_ids[:9]):  # Max 9 adicionales (10 total)
                    if extra_img.image_1920:
                        img_b64 = extra_img.image_1920
                        if isinstance(img_b64, bytes):
                            img_b64 = img_b64.decode('utf-8')
                        images_to_upload.append((img_b64, f'{product.default_code or product.id}_extra_{idx+1}.jpg'))

            # Subir todas las imágenes
            for img_b64, filename in images_to_upload:
                try:
                    # Validar y redimensionar si es necesario
                    if auto_resize:
                        validation = ImageService.validate_image_size(img_b64)
                        if validation.get('needs_resize'):
                            _logger.info('Redimensionando imagen %s de %dx%d a %d px',
                                       filename, validation['width'], validation['height'], target_size)
                            img_b64 = ImageService.resize_image(img_b64, target_size)

                    # Subir a ML
                    result = ImageService.upload_image_base64(
                        self.account_id.id,
                        img_b64,
                        filename,
                        auto_resize=False  # Ya redimensionamos arriba
                    )

                    if result.get('success'):
                        # Obtener URL (puede ser secure_url, url, o construida desde ID)
                        picture_id = result.get('id')
                        secure_url = result.get('secure_url') or result.get('url')
                        if not secure_url and picture_id:
                            secure_url = f'https://http2.mlstatic.com/D_{picture_id}-F.jpg'

                        if secure_url:
                            # Guardar registro
                            ImageModel.create({
                                'account_id': self.account_id.id,
                                'product_tmpl_id': product.id,
                                'ml_picture_id': picture_id,
                                'ml_url': result.get('url') or secure_url,
                                'ml_secure_url': secure_url,
                                'ml_size': result.get('size'),
                                'ml_max_size': result.get('max_size'),
                                'state': 'uploaded',
                            })
                            pictures.append({'source': secure_url})
                            _logger.info('Imagen subida para %s: %s', product.name, secure_url)
                        else:
                            _logger.warning('Imagen subida pero sin URL para %s', product.name)
                    else:
                        _logger.warning('Error subiendo imagen %s de %s: %s',
                                      filename, product.name, result.get('error'))
                except Exception as e:
                    _logger.error('Error procesando imagen %s: %s', filename, str(e))

        elif self.image_source == 'existing_ml':
            # Usar imágenes ya subidas a ML
            ImageService = self.env['mercadolibre.image.service']
            pictures = ImageService.get_product_ml_pictures(
                self.account_id.id,
                product.id
            )

        elif self.image_source == 'url':
            # Usar URLs personalizadas (manuales)
            if self.custom_image_urls:
                urls = [url.strip() for url in self.custom_image_urls.split('\n') if url.strip()]
                for url in urls[:10]:  # ML acepta máximo 10 imágenes
                    if url.startswith('http'):
                        pictures.append({'source': url})

        return pictures

    def action_check_listing_types(self):
        """Consulta los tipos de publicación disponibles para la categoría seleccionada"""
        self.ensure_one()

        if not self.account_id:
            raise UserError(_('Seleccione una cuenta de MercadoLibre.'))

        if not self.category_id:
            raise UserError(_('Seleccione una categoría primero.'))

        http = self.env['mercadolibre.http']

        try:
            # Obtener user_id de la cuenta
            user_id = self.account_id.ml_user_id

            # Consultar tipos disponibles
            # Endpoint: /users/{user_id}/available_listing_types?category_id={category_id}
            endpoint = f'/users/{user_id}/available_listing_types?category_id={self.ml_category_id}'

            response = http._request(
                account_id=self.account_id.id,
                endpoint=endpoint,
                method='GET'
            )

            data = response.get('data', {})
            available = data.get('available', [])

            if available:
                lines = ['Tipos de publicación disponibles para esta categoría:\n']
                for lt in available:
                    name = lt.get('name', lt.get('id'))
                    lt_id = lt.get('id')
                    remaining = lt.get('remaining_listings')
                    if remaining is not None:
                        lines.append(f'  • {name} ({lt_id}) - Restantes: {remaining}')
                    else:
                        lines.append(f'  • {name} ({lt_id})')

                # Verificar si FREE está disponible
                free_available = any(lt.get('id') == 'free' for lt in available)
                if not free_available:
                    lines.append('\n⚠ "Gratuito" NO está disponible para esta categoría.')
                    lines.append('   Use "Clásico" o "Premium".')

                self.available_listing_types = '\n'.join(lines)
            else:
                self.available_listing_types = 'No se encontraron tipos disponibles. Verifique la categoría.'

        except Exception as e:
            self.available_listing_types = f'Error consultando tipos: {str(e)}'

        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicar en MercadoLibre'),
            'res_model': 'mercadolibre.product.publish',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _validate_leaf_category(self):
        """Verifica que la categoría seleccionada sea una categoría hoja (sin subcategorías)"""
        if not self.category_id:
            return False, "No hay categoría seleccionada"

        # Verificar si tiene subcategorías en Odoo
        CategoryModel = self.env['mercadolibre.category']
        children_count = CategoryModel.search_count([
            ('parent_id', '=', self.category_id.id)
        ])

        if children_count > 0:
            return False, f"La categoría tiene {children_count} subcategorías. Debe seleccionar una categoría final."

        # Verificar con la API de ML si tiene hijos
        if self.category_id.has_children and not self.category_id.children_loaded:
            return False, "Esta categoría puede tener subcategorías. Cargue las subcategorías primero."

        return True, "OK"

    def action_preview(self):
        """Muestra vista previa de la publicacion"""
        self.ensure_one()

        if not self.category_id:
            raise ValidationError(_('Debe seleccionar una categoria de MercadoLibre.'))

        # Validar que sea categoría hoja
        is_leaf, leaf_msg = self._validate_leaf_category()

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append('    VISTA PREVIA DE PUBLICACION')
        log_lines.append('=' * 50)
        log_lines.append('')
        log_lines.append(f'  Cuenta:    {self.account_id.name}')
        log_lines.append(f'  Categoria: {self.category_path} ({self.ml_category_id})')

        if not is_leaf:
            log_lines.append(f'  ⚠ ALERTA CATEGORÍA: {leaf_msg}')

        log_lines.append(f'  Tipo:      {self.listing_type_id}')
        log_lines.append(f'  Condicion: {self.condition}')
        log_lines.append(f'  Imagenes:  {dict(self._fields["image_source"].selection).get(self.image_source, "N/A")}')
        log_lines.append('')
        log_lines.append('-' * 50)
        log_lines.append('  PRODUCTOS A PUBLICAR')
        log_lines.append('-' * 50)

        for product in self.product_tmpl_ids:
            # Calcular precio
            if self.use_product_price:
                price = product.list_price
            else:
                price = self.custom_price

            # Calcular stock
            if self.use_product_stock:
                stock = int(product.qty_available)
            else:
                stock = self.custom_stock

            # SKU
            if self.sku_field == 'default_code':
                sku = product.default_code or ''
            elif self.sku_field == 'barcode':
                sku = product.barcode or ''
            else:
                sku = self.custom_sku or ''

            # Obtener marca y modelo para preview (desde campos ml_brand y ml_model)
            if product.ml_brand:
                brand_name = product.ml_brand
            else:
                brand_name = 'Genérico'

            if product.ml_model:
                model_name = product.ml_model
            elif product.default_code:
                model_name = product.default_code
            else:
                model_name = product.name[:30] if product.name else 'Estándar'

            # Construir family_name como lo hará la publicación
            family_name = f"{brand_name} {model_name}"
            if len(family_name) < 20:
                family_name = f"{brand_name} {product.name[:40]}"
            family_name = family_name[:60]

            log_lines.append('')
            log_lines.append(f'  Producto: {product.name}')
            log_lines.append(f'    Family Name: {family_name}')
            log_lines.append(f'    Marca:       {brand_name}')
            log_lines.append(f'    Modelo:      {model_name}')
            log_lines.append(f'    Precio:      ${price:,.2f}')
            log_lines.append(f'    Stock:       {stock}')
            log_lines.append(f'    SKU:         {sku}')

            # Alertas
            if price < 35:
                log_lines.append(f'    ⚠ ALERTA: Precio muy bajo. Algunas categorías requieren mínimo $35')

            if stock <= 0:
                log_lines.append(f'    ⚠ ALERTA: Stock es 0. Verifique inventario del producto.')

            # Verificar si ya existe publicacion
            existing = self.env['mercadolibre.item'].search([
                ('product_tmpl_id', '=', product.id),
                ('account_id', '=', self.account_id.id),
            ], limit=1)

            if existing:
                log_lines.append(f'    ⚠ AVISO: Ya existe publicacion {existing.ml_item_id}')

        log_lines.append('')
        log_lines.append('=' * 50)

        self.write({
            'state': 'preview',
            'publish_log': '\n'.join(log_lines),
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicar en MercadoLibre'),
            'res_model': 'mercadolibre.product.publish',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_publish(self):
        """Publica los productos en MercadoLibre"""
        self.ensure_one()

        # Prevenir doble clic / doble publicación
        if self.state == 'done':
            raise ValidationError(_('Esta publicación ya fue procesada. Cierre el wizard y abra uno nuevo.'))

        if self.state not in ('draft', 'preview'):
            raise ValidationError(_('El wizard no está en estado válido para publicar.'))

        if not self.account_id.has_valid_token:
            raise ValidationError(_('La cuenta no tiene un token valido.'))

        if not self.category_id:
            raise ValidationError(_('Debe seleccionar una categoria.'))

        # Cambiar estado inmediatamente para prevenir doble publicación
        self.write({'state': 'done', 'publish_log': 'Procesando...'})
        self.env.cr.commit()  # Commit para que otros procesos vean el cambio

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append('    PUBLICACION EN MERCADOLIBRE')
        log_lines.append('=' * 50)
        log_lines.append('')

        http = self.env['mercadolibre.http']
        ItemModel = self.env['mercadolibre.item']

        published_count = 0
        error_count = 0

        for product in self.product_tmpl_ids:
            try:
                # Verificar si ya existe
                existing = ItemModel.search([
                    ('product_tmpl_id', '=', product.id),
                    ('account_id', '=', self.account_id.id),
                ], limit=1)

                if existing:
                    log_lines.append(f'  [OMITIDO] {product.name}: Ya existe {existing.ml_item_id}')
                    continue

                # Preparar datos
                price = product.list_price if self.use_product_price else self.custom_price
                stock = int(product.qty_available) if self.use_product_stock else self.custom_stock

                if self.sku_field == 'default_code':
                    sku = product.default_code or ''
                elif self.sku_field == 'barcode':
                    sku = product.barcode or ''
                else:
                    sku = self.custom_sku or ''

                # Obtener marca del producto (campo ml_brand del producto)
                if product.ml_brand:
                    brand_name = product.ml_brand
                else:
                    # Usar "Genérico" si no hay marca definida
                    brand_name = 'Genérico'

                # Obtener modelo (campo ml_model o referencia interna)
                if product.ml_model:
                    model_name = product.ml_model
                elif product.default_code:
                    model_name = product.default_code
                else:
                    model_name = product.name[:30] if product.name else 'Estándar'

                # family_name (requerido por categorías con User Products / Catálogo 2.0)
                # IMPORTANTE: Debe incluir marca, modelo y características importantes
                # El family_name se usa para generar el título automáticamente
                # Formato recomendado: "Marca Modelo Características"
                family_name = f"{brand_name} {model_name}"
                if len(family_name) < 20:
                    # Agregar más contexto si es muy corto
                    family_name = f"{brand_name} {product.name[:40]}"
                family_name = family_name[:60]  # Máximo 60 caracteres

                # Preparar body para API - MODELO USER PRODUCTS (Precio por Variación)
                # IMPORTANTE: NO enviar 'title', ML lo genera automáticamente desde family_name
                # Referencia: https://developers.mercadolibre.com.ar/es_ar/precio-variacion
                body = {
                    'family_name': family_name,  # Reemplaza a 'title' en User Products
                    'category_id': self.ml_category_id,
                    'price': price,
                    'currency_id': product.currency_id.name or 'MXN',
                    'available_quantity': stock,
                    'buying_mode': self.buying_mode,
                    'condition': self.condition,
                    'listing_type_id': self.listing_type_id,
                }

                # Atributos - requeridos por User Products
                attributes = []

                # BRAND (marca) - REQUERIDO en User Products
                attributes.append({'id': 'BRAND', 'value_name': brand_name})

                # MODEL (modelo) - REQUERIDO en muchas categorías
                attributes.append({'id': 'MODEL', 'value_name': model_name})

                # SKU
                if sku:
                    attributes.append({'id': 'SELLER_SKU', 'value_name': sku})

                if attributes:
                    body['attributes'] = attributes

                # NOTA: La descripción NO se incluye en el body inicial para User Products
                # Se envía después de crear el item via POST /items/{id}/description
                # Esto es requerido por el modelo de Precio por Variación (Catálogo 2.0)

                # GTIN/EAN/UPC - Código de barras
                if self.use_barcode_as_gtin and product.barcode:
                    attributes.append({'id': 'GTIN', 'value_name': product.barcode})

                # Imágenes
                pictures = self._get_product_pictures(product)
                if pictures:
                    body['pictures'] = pictures

                # Shipping
                body['shipping'] = {
                    'mode': self.shipping_mode,
                    'free_shipping': self.free_shipping,
                    'local_pick_up': self.local_pick_up,
                }

                # Sale Terms (Garantía y condiciones)
                sale_terms = []

                # Garantía
                if self.warranty_type and self.warranty_type != 'Sin garantía':
                    sale_terms.append({
                        'id': 'WARRANTY_TYPE',
                        'value_name': self.warranty_type
                    })
                    if self.warranty_time:
                        sale_terms.append({
                            'id': 'WARRANTY_TIME',
                            'value_name': self.warranty_time
                        })

                # Tiempo de fabricación/preparación
                if self.manufacturing_time and self.manufacturing_time > 0:
                    sale_terms.append({
                        'id': 'MANUFACTURING_TIME',
                        'value_name': str(self.manufacturing_time),
                        'value_struct': {
                            'number': self.manufacturing_time,
                            'unit': 'días'
                        }
                    })

                if sale_terms:
                    body['sale_terms'] = sale_terms

                # Crear en ML
                response = http._request(
                    account_id=self.account_id.id,
                    endpoint='/items',
                    method='POST',
                    body=body
                )

                item_data = response.get('data', {})
                ml_item_id = item_data.get('id')

                if ml_item_id:
                    # Enviar descripción por separado (requerido en User Products)
                    # IMPORTANTE: Para items nuevos usar POST, para actualizar usar PUT
                    if product.description_sale:
                        try:
                            http._request(
                                account_id=self.account_id.id,
                                endpoint=f'/items/{ml_item_id}/description',
                                method='POST',  # POST para crear descripción nueva
                                body={'plain_text': product.description_sale}
                            )
                            _logger.info('Descripción enviada para %s', ml_item_id)
                        except Exception as e:
                            # Si POST falla (ya tiene descripción), intentar con PUT
                            _logger.warning('POST descripción falló, intentando PUT para %s: %s', ml_item_id, str(e))
                            try:
                                http._request(
                                    account_id=self.account_id.id,
                                    endpoint=f'/items/{ml_item_id}/description',
                                    method='PUT',
                                    body={'plain_text': product.description_sale}
                                )
                                _logger.info('Descripción actualizada con PUT para %s', ml_item_id)
                            except Exception as e2:
                                _logger.warning('Error enviando descripción para %s: %s', ml_item_id, str(e2))

                    # Crear registro local
                    item, _is_new = ItemModel.create_from_ml_data(item_data, self.account_id)
                    item.write({
                        'product_tmpl_id': product.id,
                        'product_id': product.product_variant_id.id,
                    })

                    published_count += 1
                    log_lines.append(f'  [PUBLICADO] {product.name}: {ml_item_id}')
                    log_lines.append(f'              Link: {item_data.get("permalink", "")}')
                    # Detalles de lo enviado
                    log_lines.append(f'              Precio: ${price:,.2f} | Stock: {stock}')
                    log_lines.append(f'              Imágenes: {len(pictures)} | Descripción: {"Sí" if product.description_sale else "No"}')
                    if item_data.get('status') != 'active':
                        log_lines.append(f'              ⚠ Status: {item_data.get("status")} - {item_data.get("sub_status", [])}')
                else:
                    error_count += 1
                    log_lines.append(f'  [ERROR] {product.name}: No se obtuvo ID')

            except Exception as e:
                error_count += 1
                log_lines.append(f'  [ERROR] {product.name}: {str(e)}')
                _logger.error('Error publicando %s: %s', product.name, str(e))

        # Resumen
        log_lines.append('')
        log_lines.append('=' * 50)
        log_lines.append('  RESUMEN')
        log_lines.append('=' * 50)
        log_lines.append(f'  Publicados: {published_count}')
        log_lines.append(f'  Errores:    {error_count}')
        log_lines.append('=' * 50)

        self.write({
            'state': 'done' if error_count == 0 else 'error',
            'publish_log': '\n'.join(log_lines),
            'published_count': published_count,
            'error_count': error_count,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicar en MercadoLibre'),
            'res_model': 'mercadolibre.product.publish',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_config(self):
        """Vuelve a configuracion"""
        self.write({'state': 'draft', 'publish_log': False})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicar en MercadoLibre'),
            'res_model': 'mercadolibre.product.publish',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_items(self):
        """Ver items publicados"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Items Publicados'),
            'res_model': 'mercadolibre.item',
            'view_mode': 'tree,form',
            'domain': [
                ('account_id', '=', self.account_id.id),
                ('product_tmpl_id', 'in', self.product_tmpl_ids.ids),
            ],
        }
