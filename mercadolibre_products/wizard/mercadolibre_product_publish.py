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
        ('gold_special', 'Clasico (gold_special)'),
        ('gold_pro', 'Premium (gold_pro)'),
        ('gold', 'Oro'),
        ('silver', 'Plata'),
        ('bronze', 'Bronce'),
        ('free', 'Gratuito'),
    ], string='Tipo Publicacion', default='gold_special', required=True)

    condition = fields.Selection([
        ('new', 'Nuevo'),
        ('used', 'Usado'),
    ], string='Condicion', default='new', required=True)

    buying_mode = fields.Selection([
        ('buy_it_now', 'Compra Inmediata'),
    ], string='Modo Compra', default='buy_it_now', required=True)

    # Categoria ML
    category_id = fields.Many2one(
        'mercadolibre.category',
        string='Categoria ML',
        help='Categoria de MercadoLibre para la publicacion'
    )
    ml_category_id = fields.Char(
        string='ID Categoria ML',
        related='category_id.ml_category_id',
        readonly=True,
        store=False
    )
    category_name = fields.Char(
        string='Nombre Categoria',
        related='category_id.path_from_root',
        readonly=True,
        store=False
    )
    # Campo para busqueda manual de categoria por ID
    search_category_id = fields.Char(
        string='Buscar por ID',
        help='Ingrese el ID de categoria ML para buscar (ej: MLM1055)'
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
    ], string='Modo Envio', default='me2')
    free_shipping = fields.Boolean(
        string='Envio Gratis',
        default=False
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

    @api.onchange('site_id')
    def _onchange_site_id(self):
        """Sincroniza categorias cuando cambia el sitio"""
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
            # Limpiar categoria seleccionada si es de otro sitio
            if self.category_id and self.category_id.site_id != self.site_id:
                self.category_id = False

    @api.onchange('search_category_id')
    def _onchange_search_category_id(self):
        """Busca o crea la categoria por ID de ML"""
        if self.search_category_id:
            CategoryModel = self.env['mercadolibre.category']
            site_id = self.site_id or 'MLM'

            # Buscar si ya existe
            existing = CategoryModel.search([
                ('ml_category_id', '=', self.search_category_id),
                ('site_id', '=', site_id)
            ], limit=1)

            if existing:
                self.category_id = existing.id
                self.search_category_id = False
            else:
                # Intentar obtener de ML y crear
                try:
                    category = CategoryModel.get_or_create_from_ml(
                        self.search_category_id,
                        site_id=site_id
                    )
                    if category:
                        self.category_id = category.id
                        self.search_category_id = False
                except Exception:
                    pass

    def action_sync_categories(self):
        """Sincroniza categorias raiz de MercadoLibre"""
        CategoryModel = self.env['mercadolibre.category']
        site_id = self.site_id or 'MLM'

        CategoryModel.action_sync_root_categories(site_id=site_id)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicar en MercadoLibre'),
            'res_model': 'mercadolibre.product.publish',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_preview(self):
        """Muestra vista previa de la publicacion"""
        self.ensure_one()

        if not self.category_id:
            raise ValidationError(_('Debe seleccionar una categoria de MercadoLibre.'))

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append('    VISTA PREVIA DE PUBLICACION')
        log_lines.append('=' * 50)
        log_lines.append('')
        log_lines.append(f'  Cuenta:    {self.account_id.name}')
        log_lines.append(f'  Categoria: {self.category_name} ({self.ml_category_id})')
        log_lines.append(f'  Tipo:      {self.listing_type_id}')
        log_lines.append(f'  Condicion: {self.condition}')
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

            log_lines.append('')
            log_lines.append(f'  Producto: {product.name}')
            log_lines.append(f'    Titulo ML: {product.name[:60]}')
            log_lines.append(f'    Precio:    ${price:,.2f}')
            log_lines.append(f'    Stock:     {stock}')
            log_lines.append(f'    SKU:       {sku}')

            # Verificar si ya existe publicacion
            existing = self.env['mercadolibre.item'].search([
                ('product_tmpl_id', '=', product.id),
                ('account_id', '=', self.account_id.id),
            ], limit=1)

            if existing:
                log_lines.append(f'    AVISO: Ya existe publicacion {existing.ml_item_id}')

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

        if not self.account_id.has_valid_token:
            raise ValidationError(_('La cuenta no tiene un token valido.'))

        if not self.category_id:
            raise ValidationError(_('Debe seleccionar una categoria.'))

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

                # Preparar body para API
                body = {
                    'title': product.name[:60],
                    'category_id': self.ml_category_id,
                    'price': price,
                    'currency_id': product.currency_id.name or 'MXN',
                    'available_quantity': stock,
                    'buying_mode': self.buying_mode,
                    'condition': self.condition,
                    'listing_type_id': self.listing_type_id,
                }

                # SKU como atributo
                if sku:
                    body['attributes'] = [
                        {'id': 'SELLER_SKU', 'value_name': sku}
                    ]

                # Descripcion
                if product.description_sale:
                    body['description'] = {'plain_text': product.description_sale}

                # Imagenes
                if product.image_1920:
                    # Nota: ML requiere URLs publicas, no base64
                    # Por ahora omitimos imagenes
                    pass

                # Shipping
                body['shipping'] = {
                    'mode': self.shipping_mode,
                    'free_shipping': self.free_shipping,
                }

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
                    # Crear registro local
                    item, _ = ItemModel.create_from_ml_data(item_data, self.account_id)
                    item.write({
                        'product_tmpl_id': product.id,
                        'product_id': product.product_variant_id.id,
                    })

                    published_count += 1
                    log_lines.append(f'  [PUBLICADO] {product.name}: {ml_item_id}')
                    log_lines.append(f'              Link: {item_data.get("permalink", "")}')
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
