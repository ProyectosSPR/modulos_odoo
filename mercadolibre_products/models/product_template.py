# -*- coding: utf-8 -*-

import requests
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # =====================================================
    # INDICADORES DE PUBLICACION ML
    # =====================================================
    ml_publish_readiness = fields.Html(
        string='Estado para Publicar en ML',
        compute='_compute_ml_publish_readiness',
        sanitize=False,
    )
    ml_fields_ready = fields.Boolean(
        string='Listo para ML',
        compute='_compute_ml_publish_readiness',
    )
    ml_missing_fields_count = fields.Integer(
        string='Campos Faltantes ML',
        compute='_compute_ml_publish_readiness',
    )

    @api.depends('name', 'list_price', 'qty_available', 'default_code',
                 'description_sale', 'image_1920', 'type', 'barcode',
                 'ml_brand', 'ml_model', 'ml_category_id')
    def _compute_ml_publish_readiness(self):
        """Calcula el estado de preparación para publicar en MercadoLibre"""
        for record in self:
            checks = []
            missing_count = 0

            # Nombre (Requerido)
            if record.name and len(record.name) >= 5:
                checks.append(('✅', 'Nombre', record.name[:40], 'success'))
            else:
                checks.append(('❌', 'Nombre', 'Muy corto o vacío (mín 5 caracteres)', 'danger'))
                missing_count += 1

            # Categoría ML (Requerido para publicación masiva)
            if record.ml_category_id:
                if record.ml_category_id.has_children:
                    # Categoría padre - no se puede usar para publicar
                    checks.append(('❌', 'Categoría ML', f'{record.ml_category_id.name[:30]} (tiene subcategorías - seleccione una categoría hoja)', 'danger'))
                    missing_count += 1
                elif hasattr(record.ml_category_id, 'listing_allowed') and not record.ml_category_id.listing_allowed:
                    # Categoría de catálogo - no permite publicar directamente
                    checks.append(('❌', 'Categoría ML', f'{record.ml_category_id.name[:30]} (solo catálogo - use "Otros" u otra)', 'danger'))
                    missing_count += 1
                else:
                    # Categoría hoja válida - OK
                    checks.append(('✅', 'Categoría ML', record.ml_category_id.name[:40], 'success'))
            else:
                checks.append(('❌', 'Categoría ML', 'No definida (requerida para publicar)', 'danger'))
                missing_count += 1

            # Marca (Requerido para ML User Products)
            if record.ml_brand:
                checks.append(('✅', 'Marca ML', record.ml_brand, 'success'))
            else:
                checks.append(('⚠️', 'Marca ML', 'No definida (se usará "Genérico")', 'warning'))

            # Modelo (Requerido para ML User Products)
            if record.ml_model:
                checks.append(('✅', 'Modelo ML', record.ml_model, 'success'))
            elif record.default_code:
                checks.append(('✅', 'Modelo ML', f'{record.default_code} (desde Ref. Interna)', 'success'))
            else:
                checks.append(('⚠️', 'Modelo ML', 'No definido (se usará parte del nombre)', 'warning'))

            # Precio (Requerido, mín $35)
            if record.list_price and record.list_price >= 35:
                checks.append(('✅', 'Precio', f'${record.list_price:,.2f}', 'success'))
            elif record.list_price and record.list_price > 0:
                checks.append(('⚠️', 'Precio', f'${record.list_price:,.2f} (mín $35 recomendado)', 'warning'))
                missing_count += 1
            else:
                checks.append(('❌', 'Precio', 'Sin precio definido', 'danger'))
                missing_count += 1

            # Tipo de producto y Stock
            if record.type == 'product':
                if record.qty_available > 0:
                    checks.append(('✅', 'Stock', f'{int(record.qty_available)} unidades', 'success'))
                else:
                    checks.append(('⚠️', 'Stock', '0 unidades (sin inventario)', 'warning'))
                    missing_count += 1
            else:
                checks.append(('❌', 'Tipo Producto', f'Es "{record.type}" - debe ser "Almacenable"', 'danger'))
                missing_count += 1

            # Código de barras / GTIN (Recomendado)
            if record.barcode:
                checks.append(('✅', 'Código Barras/GTIN', record.barcode, 'success'))
            else:
                checks.append(('⚠️', 'Código Barras/GTIN', 'No definido (ayuda a posicionar en catálogo)', 'warning'))

            # Descripción (Recomendado)
            if record.description_sale and len(record.description_sale) >= 20:
                checks.append(('✅', 'Descripción Venta', f'{len(record.description_sale)} caracteres', 'success'))
            elif record.description_sale:
                checks.append(('⚠️', 'Descripción Venta', 'Muy corta (recomendado +20 caracteres)', 'warning'))
            else:
                checks.append(('⚠️', 'Descripción Venta', 'Sin descripción', 'warning'))

            # Imagen (Muy recomendado)
            if record.image_1920:
                checks.append(('✅', 'Imagen', 'Tiene imagen principal', 'success'))
            else:
                checks.append(('❌', 'Imagen', 'Sin imagen (muy importante para ML)', 'danger'))
                missing_count += 1

            # Generar HTML
            html_parts = []
            html_parts.append('<div class="ml-publish-checklist" style="font-size: 13px;">')

            # Header con estado general
            if missing_count == 0:
                html_parts.append('<div class="alert alert-success py-2 mb-2">')
                html_parts.append('<strong>✅ Producto listo para publicar en MercadoLibre</strong>')
                html_parts.append('</div>')
            else:
                html_parts.append(f'<div class="alert alert-warning py-2 mb-2">')
                html_parts.append(f'<strong>⚠️ {missing_count} campo(s) requieren atención</strong>')
                html_parts.append('</div>')

            # Tabla de campos
            html_parts.append('<table class="table table-sm table-borderless mb-0" style="font-size: 12px;">')
            html_parts.append('<thead><tr><th style="width:30px;"></th><th>Campo</th><th>Estado</th></tr></thead>')
            html_parts.append('<tbody>')

            for icon, field_name, status, color in checks:
                text_class = f'text-{color}' if color != 'success' else ''
                html_parts.append(f'<tr class="{text_class}">')
                html_parts.append(f'<td>{icon}</td>')
                html_parts.append(f'<td><strong>{field_name}</strong></td>')
                html_parts.append(f'<td>{status}</td>')
                html_parts.append('</tr>')

            html_parts.append('</tbody></table>')
            html_parts.append('</div>')

            record.ml_publish_readiness = Markup(''.join(html_parts))
            record.ml_fields_ready = missing_count == 0
            record.ml_missing_fields_count = missing_count

    # =====================================================
    # CAMPOS PARA MERCADOLIBRE
    # =====================================================
    ml_brand = fields.Char(
        string='Marca ML',
        help='Marca del producto para MercadoLibre. Si está vacío se usará "Genérico"'
    )
    ml_model = fields.Char(
        string='Modelo ML',
        help='Modelo del producto para MercadoLibre. Si está vacío se usará la Referencia Interna'
    )

    # Configuración de publicación
    ml_category_id = fields.Many2one(
        'mercadolibre.category',
        string='Categoría ML',
        help='Categoría de MercadoLibre para este producto. Debe ser una categoría hoja (sin subcategorías).'
    )
    ml_category_is_leaf = fields.Boolean(
        string='Categoría es Hoja',
        compute='_compute_ml_category_is_leaf',
        help='Indica si la categoría seleccionada es una categoría hoja (válida para publicar)'
    )

    @api.depends('ml_category_id', 'ml_category_id.has_children', 'ml_category_id.listing_allowed')
    def _compute_ml_category_is_leaf(self):
        for record in self:
            if record.ml_category_id:
                # Válida si es hoja Y permite publicar
                is_leaf = not record.ml_category_id.has_children
                allows_listing = getattr(record.ml_category_id, 'listing_allowed', True)
                record.ml_category_is_leaf = is_leaf and allows_listing
            else:
                record.ml_category_is_leaf = True  # Sin categoría, no mostrar advertencia

    # =====================================================
    # PREDICCIÓN DE CATEGORÍA ML
    # =====================================================
    ml_predicted_category_id = fields.Char(
        string='ID Categoría Sugerida',
        help='ID de la categoría que MercadoLibre sugiere para este producto'
    )
    ml_predicted_category_name = fields.Char(
        string='Categoría Sugerida ML',
        help='Nombre de la categoría que MercadoLibre sugiere basándose en el nombre del producto'
    )
    ml_category_matches_prediction = fields.Boolean(
        string='Categoría Coincide',
        compute='_compute_category_matches_prediction',
        help='Indica si la categoría seleccionada coincide con la sugerida por MercadoLibre'
    )

    @api.depends('ml_category_id', 'ml_predicted_category_id')
    def _compute_category_matches_prediction(self):
        for record in self:
            if record.ml_category_id and record.ml_predicted_category_id:
                record.ml_category_matches_prediction = (
                    record.ml_category_id.ml_category_id == record.ml_predicted_category_id
                )
            else:
                record.ml_category_matches_prediction = True  # Sin predicción, no mostrar advertencia

    def action_predict_category(self):
        """Consulta la API de ML para obtener la categoría sugerida"""
        self.ensure_one()

        # Obtener nombre limpio del producto
        product_name = self.name
        if isinstance(product_name, dict):
            product_name = product_name.get('es_MX') or product_name.get('en_US') or str(product_name)

        if not product_name or len(product_name) < 3:
            raise UserError(_('El nombre del producto es muy corto para predecir la categoría.'))

        try:
            import urllib.parse
            clean_name = urllib.parse.quote(product_name[:60])
            url = f'https://api.mercadolibre.com/sites/MLM/domain_discovery/search?q={clean_name}'
            response = requests.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    first_result = data[0]
                    predicted_id = first_result.get('category_id')
                    predicted_name = first_result.get('category_name')

                    self.write({
                        'ml_predicted_category_id': predicted_id,
                        'ml_predicted_category_name': predicted_name,
                    })

                    # Verificar si la categoría existe en Odoo, si no, crearla
                    CategoryModel = self.env['mercadolibre.category']
                    existing_cat = CategoryModel.search([
                        ('ml_category_id', '=', predicted_id)
                    ], limit=1)

                    if not existing_cat:
                        # Auto-crear la categoría
                        existing_cat = CategoryModel.get_or_create_from_ml(predicted_id, 'MLM')
                        _logger.info('Categoría %s creada automáticamente', predicted_id)

                    # Determinar mensaje
                    msg_type = 'success'
                    if self.ml_category_id and self.ml_category_id.ml_category_id != predicted_id:
                        msg_type = 'warning'
                        message = _('ML sugiere: %s (%s). Tu categoría actual: %s') % (
                            predicted_name, predicted_id, self.ml_category_id.name
                        )
                    else:
                        message = _('Categoría sugerida: %s (%s)') % (predicted_name, predicted_id)

                    # Recargar la vista para mostrar los cambios
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'product.template',
                        'res_id': self.id,
                        'view_mode': 'form',
                        'target': 'current',
                        'context': {
                            'show_notification': True,
                            'notification_message': message,
                            'notification_type': msg_type,
                        }
                    }
                else:
                    raise UserError(_('No se encontró una categoría sugerida para este producto.'))
            else:
                raise UserError(_('Error al consultar la API de MercadoLibre: %s') % response.status_code)

        except requests.exceptions.RequestException as e:
            raise UserError(_('Error de conexión: %s') % str(e))

    def action_apply_predicted_category(self):
        """Aplica la categoría sugerida al producto"""
        self.ensure_one()

        if not self.ml_predicted_category_id:
            raise UserError(_('Primero debe obtener una predicción de categoría.'))

        CategoryModel = self.env['mercadolibre.category']
        category = CategoryModel.search([
            ('ml_category_id', '=', self.ml_predicted_category_id)
        ], limit=1)

        if not category:
            # Crear la categoría si no existe
            category = CategoryModel.get_or_create_from_ml(self.ml_predicted_category_id, 'MLM')

        self.write({'ml_category_id': category.id})

        # Recargar la vista para mostrar los cambios
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    ml_listing_type = fields.Selection([
        ('gold_special', 'Clásica (gold_special)'),
        ('gold_pro', 'Premium (gold_pro)'),
        ('gold', 'Oro'),
        ('silver', 'Plata'),
        ('bronze', 'Bronce'),
        ('free', 'Gratuita'),
    ], string='Tipo Publicación ML', default='gold_special',
       help='Tipo de publicación en MercadoLibre')
    ml_condition = fields.Selection([
        ('new', 'Nuevo'),
        ('used', 'Usado'),
    ], string='Condición ML', default='new')

    # Envío
    ml_shipping_mode = fields.Selection([
        ('me2', 'Mercado Envíos'),
        ('not_specified', 'A convenir'),
    ], string='Modo Envío ML', default='me2')
    ml_free_shipping = fields.Boolean(
        string='Envío Gratis ML',
        default=False
    )
    ml_local_pick_up = fields.Boolean(
        string='Retiro en Persona ML',
        default=False
    )

    # Garantía
    ml_warranty_type = fields.Selection([
        ('Garantía del vendedor', 'Garantía del vendedor'),
        ('Garantía de fábrica', 'Garantía de fábrica'),
        ('Sin garantía', 'Sin garantía'),
    ], string='Tipo Garantía ML', default='Garantía del vendedor')
    ml_warranty_time = fields.Char(
        string='Tiempo Garantía ML',
        default='30 días',
        help='Ej: 30 días, 6 meses, 1 año'
    )

    # =====================================================
    # VINCULACION CON MERCADOLIBRE
    # =====================================================
    ml_item_ids = fields.One2many(
        'mercadolibre.item',
        'product_tmpl_id',
        string='Publicaciones ML'
    )
    ml_item_count = fields.Integer(
        string='Publicaciones ML',
        compute='_compute_ml_item_count'
    )
    has_ml_items = fields.Boolean(
        string='Tiene Publicaciones ML',
        compute='_compute_ml_item_count',
        store=True
    )

    # =====================================================
    # CONTROL DE SINCRONIZACION
    # =====================================================
    ml_sync_enabled = fields.Boolean(
        string='Sincronizar con ML',
        default=False,
        help='Habilitar sincronizacion automatica con MercadoLibre'
    )
    ml_auto_sync_stock = fields.Boolean(
        string='Auto-sync Stock a ML',
        default=True,
        help='Actualizar stock en ML automaticamente cuando cambie en Odoo'
    )
    ml_auto_sync_price = fields.Boolean(
        string='Auto-sync Precio a ML',
        default=False,
        help='Actualizar precio en ML automaticamente cuando cambie en Odoo'
    )
    ml_last_sync = fields.Datetime(
        string='Ultima Sync ML',
        readonly=True
    )

    # =====================================================
    # STOCK COMPARISON
    # =====================================================
    ml_total_stock = fields.Float(
        string='Stock Total ML',
        compute='_compute_ml_stock_info',
        help='Suma del stock disponible en todas las publicaciones ML'
    )
    ml_stock_difference = fields.Float(
        string='Diferencia Stock ML',
        compute='_compute_ml_stock_info',
        help='Diferencia entre stock Odoo y stock ML total'
    )
    ml_stock_alert = fields.Boolean(
        string='Alerta Stock ML',
        compute='_compute_ml_stock_info',
        store=True
    )

    @api.depends('ml_item_ids')
    def _compute_ml_item_count(self):
        for record in self:
            record.ml_item_count = len(record.ml_item_ids)
            record.has_ml_items = record.ml_item_count > 0

    @api.depends('ml_item_ids', 'ml_item_ids.available_quantity',
                 'qty_available', 'ml_item_ids.is_linked')
    def _compute_ml_stock_info(self):
        for record in self:
            linked_items = record.ml_item_ids.filtered(lambda i: i.is_linked)
            ml_stock = sum(linked_items.mapped('available_quantity'))
            record.ml_total_stock = ml_stock
            record.ml_stock_difference = record.qty_available - ml_stock
            record.ml_stock_alert = abs(record.ml_stock_difference) > 0 and record.has_ml_items

    # =====================================================
    # ACCIONES
    # =====================================================
    def action_view_ml_items(self):
        """Ver publicaciones de ML vinculadas"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicaciones MercadoLibre'),
            'res_model': 'mercadolibre.item',
            'view_mode': 'tree,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {'default_product_tmpl_id': self.id},
        }

    def action_sync_to_ml(self):
        """Sincroniza este producto a todas sus publicaciones en ML"""
        self.ensure_one()

        if not self.ml_item_ids:
            raise UserError(_('Este producto no tiene publicaciones en MercadoLibre vinculadas.'))

        errors = []
        success_count = 0

        for item in self.ml_item_ids:
            try:
                # Sincronizar stock si esta habilitado
                if self.ml_auto_sync_stock or item.auto_sync_stock:
                    item.action_sync_stock_to_ml()
                    success_count += 1

                # Sincronizar precio si esta habilitado
                if self.ml_auto_sync_price or item.auto_sync_price:
                    item.action_sync_price_to_ml()

            except Exception as e:
                errors.append(f'{item.ml_item_id}: {str(e)}')

        self.write({'ml_last_sync': fields.Datetime.now()})

        if errors:
            raise UserError(_('Errores durante la sincronizacion:\n') + '\n'.join(errors))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronizacion Completada'),
                'message': _('Se sincronizaron %d publicaciones.') % success_count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_sync_from_ml(self):
        """Trae datos desde ML para este producto"""
        self.ensure_one()

        if not self.ml_item_ids:
            raise UserError(_('Este producto no tiene publicaciones en MercadoLibre vinculadas.'))

        for item in self.ml_item_ids:
            item.action_sync_from_ml()

        self.write({'ml_last_sync': fields.Datetime.now()})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronizacion Completada'),
                'message': _('Se actualizaron los datos desde MercadoLibre.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_publish_to_ml(self):
        """Abre wizard para publicar este producto en ML"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicar en MercadoLibre'),
            'res_model': 'mercadolibre.product.publish',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_ids': [(6, 0, [self.id])],
            }
        }

    def action_link_ml_item(self):
        """Abre wizard para vincular a item ML existente"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vincular a Item ML'),
            'res_model': 'mercadolibre.product.link',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.id,
                'default_link_mode': 'product_to_item',
            }
        }

    # =====================================================
    # ACCIONES MASIVAS (SERVER ACTIONS)
    # =====================================================
    def action_sync_to_ml_batch(self):
        """Accion para sincronizar varios productos a ML"""
        errors = []
        success_count = 0

        for product in self:
            if not product.ml_item_ids:
                continue
            try:
                for item in product.ml_item_ids:
                    if product.ml_auto_sync_stock or item.auto_sync_stock:
                        item.action_sync_stock_to_ml()
                        success_count += 1
            except Exception as e:
                errors.append(f'{product.name}: {str(e)}')

        msg = _('Se sincronizaron %d publicaciones.') % success_count
        if errors:
            msg += _('\n\nErrores:\n') + '\n'.join(errors[:5])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronizacion Masiva'),
                'message': msg,
                'type': 'success' if not errors else 'warning',
                'sticky': bool(errors),
            }
        }

    def action_sync_from_ml_batch(self):
        """Accion para traer datos de ML para varios productos"""
        errors = []
        success_count = 0

        for product in self:
            if not product.ml_item_ids:
                continue
            try:
                for item in product.ml_item_ids:
                    item.action_sync_from_ml()
                    success_count += 1
            except Exception as e:
                errors.append(f'{product.name}: {str(e)}')

        msg = _('Se actualizaron %d publicaciones.') % success_count
        if errors:
            msg += _('\n\nErrores:\n') + '\n'.join(errors[:5])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronizacion Masiva'),
                'message': msg,
                'type': 'success' if not errors else 'warning',
                'sticky': bool(errors),
            }
        }


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_publish_to_ml(self):
        """Abre wizard para publicar este producto en ML"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicar en MercadoLibre'),
            'res_model': 'mercadolibre.product.publish',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_ids': [(6, 0, [self.product_tmpl_id.id])],
            }
        }

    def action_link_ml_item(self):
        """Abre wizard para vincular a item ML existente"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vincular a Item ML'),
            'res_model': 'mercadolibre.product.link',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.product_tmpl_id.id,
                'default_product_id': self.id,
                'default_link_mode': 'product_to_item',
            }
        }

    def action_sync_to_ml(self):
        """Sincroniza este producto a todas sus publicaciones en ML"""
        return self.product_tmpl_id.action_sync_to_ml()

    def action_sync_from_ml(self):
        """Trae datos desde ML para este producto"""
        return self.product_tmpl_id.action_sync_from_ml()

    def action_view_ml_items(self):
        """Ver publicaciones de ML vinculadas"""
        return self.product_tmpl_id.action_view_ml_items()
