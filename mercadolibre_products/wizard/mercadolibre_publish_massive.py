# -*- coding: utf-8 -*-

import logging
import time
import requests
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MercadolibrePublishMassive(models.TransientModel):
    _name = 'mercadolibre.publish.massive'
    _description = 'Publicación Masiva a MercadoLibre'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta MercadoLibre',
        required=True,
        domain="[('state', '=', 'connected')]"
    )

    # Productos a publicar
    product_tmpl_ids = fields.Many2many(
        'product.template',
        string='Productos'
    )

    # Contadores
    product_count = fields.Integer(
        string='Total Productos',
        compute='_compute_counts'
    )
    ready_count = fields.Integer(
        string='Listos para Publicar',
        compute='_compute_counts'
    )
    missing_category_count = fields.Integer(
        string='Sin Categoría',
        compute='_compute_counts'
    )
    already_published_count = fields.Integer(
        string='Ya Publicados',
        compute='_compute_counts'
    )
    missing_image_count = fields.Integer(
        string='Sin Imagen',
        compute='_compute_counts'
    )

    # Opciones
    check_duplicates = fields.Boolean(
        string='Verificar duplicados por SKU',
        default=True,
        help='Consulta ML antes de publicar para verificar si el SKU ya existe'
    )
    duplicate_action = fields.Selection([
        ('skip', 'Omitir'),
        ('link', 'Vincular existente'),
    ], string='Si el SKU existe', default='skip')

    skip_no_category = fields.Boolean(
        string='Omitir productos sin categoría',
        default=True
    )
    skip_no_image = fields.Boolean(
        string='Omitir productos sin imagen',
        default=True
    )
    validate_category = fields.Boolean(
        string='Validar categoría con ML',
        default=True,
        help='Usa el predictor de MercadoLibre para verificar si la categoría seleccionada '
             'es apropiada para el producto. Puede prevenir que ML pause la publicación.'
    )

    # Preview lines
    preview_line_ids = fields.One2many(
        'mercadolibre.publish.massive.line',
        'wizard_id',
        string='Vista Previa'
    )

    # Estado y resultados
    state = fields.Selection([
        ('draft', 'Configuración'),
        ('preview', 'Vista Previa'),
        ('publishing', 'Publicando'),
        ('done', 'Completado'),
    ], string='Estado', default='draft')

    publish_log = fields.Text(
        string='Log de Publicación',
        readonly=True
    )
    published_count = fields.Integer(
        string='Publicados',
        readonly=True
    )
    skipped_count = fields.Integer(
        string='Omitidos',
        readonly=True
    )
    error_count = fields.Integer(
        string='Errores',
        readonly=True
    )

    @api.depends('product_tmpl_ids', 'account_id')
    def _compute_counts(self):
        for record in self:
            products = record.product_tmpl_ids
            record.product_count = len(products)

            ready = 0
            missing_cat = 0
            already_pub = 0
            missing_img = 0

            for product in products:
                # Ya publicado en esta cuenta?
                if record.account_id and product.ml_item_ids.filtered(
                    lambda i: i.account_id == record.account_id
                ):
                    already_pub += 1
                    continue

                # Sin categoría?
                if not product.ml_category_id:
                    missing_cat += 1
                    continue

                # Sin imagen?
                if not product.image_1920:
                    missing_img += 1
                    continue

                ready += 1

            record.ready_count = ready
            record.missing_category_count = missing_cat
            record.already_published_count = already_pub
            record.missing_image_count = missing_img

    def action_preview(self):
        """Genera vista previa de los productos a publicar"""
        self.ensure_one()

        if not self.account_id:
            raise ValidationError(_('Seleccione una cuenta de MercadoLibre.'))

        if not self.product_tmpl_ids:
            raise ValidationError(_('No hay productos seleccionados.'))

        # Limpiar líneas anteriores
        self.preview_line_ids.unlink()

        lines = []
        for product in self.product_tmpl_ids:
            status = 'ready'
            message = 'Listo para publicar'

            # Ya publicado en esta cuenta?
            existing_item = product.ml_item_ids.filtered(
                lambda i: i.account_id == self.account_id
            )
            if existing_item:
                status = 'already_published'
                message = f'Ya publicado: {existing_item[0].ml_item_id}'

            # Sin categoría?
            elif not product.ml_category_id:
                status = 'no_category'
                message = 'Configurar Categoría ML en el producto'

            # Categoría no es hoja? (tiene subcategorías)
            elif product.ml_category_id.has_children:
                status = 'not_leaf_category'
                cat_name = product.ml_category_id.name or product.ml_category_id.ml_category_id
                message = f'Categoría "{cat_name}" tiene subcategorías. Seleccione una categoría hoja.'

            # Categoría no permite publicar? (solo catálogo)
            elif hasattr(product.ml_category_id, 'listing_allowed') and not product.ml_category_id.listing_allowed:
                status = 'not_leaf_category'  # Reutilizamos el estado de error
                cat_name = product.ml_category_id.name or product.ml_category_id.ml_category_id
                message = f'Categoría "{cat_name}" es solo de catálogo. Use "Otros" u otra categoría que permita publicar.'

            # Sin imagen?
            elif not product.image_1920:
                status = 'no_image'
                message = 'Agregar imagen principal al producto'

            # Precio muy bajo?
            elif product.list_price < 35:
                status = 'low_price'
                message = f'Precio ${product.list_price:.2f} - mínimo recomendado $35'

            # Verificar SKU duplicado en ML
            elif self.check_duplicates and product.default_code:
                existing_ml = self._check_sku_exists_in_ml(product.default_code)
                if existing_ml:
                    status = 'sku_exists'
                    message = f'SKU ya existe en ML: {existing_ml}'

            # Campos para predicción de categoría
            predicted_cat_id = ''
            predicted_cat_name = ''

            # Validar categoría con predictor de ML (solo si pasó las validaciones anteriores)
            if status == 'ready' and self.validate_category and product.ml_category_id:
                # Obtener nombre limpio del producto
                product_name = product.name
                if isinstance(product_name, dict):
                    product_name = product_name.get('es_MX') or product_name.get('en_US') or str(product_name)

                prediction = self._predict_category(product_name, site_id='MLM')
                if prediction:
                    predicted_cat_id = prediction.get('category_id', '')
                    predicted_cat_name = prediction.get('category_name', '')

                    # Comparar con la categoría seleccionada
                    selected_cat_id = product.ml_category_id.ml_category_id
                    if predicted_cat_id and predicted_cat_id != selected_cat_id:
                        # Las categorías no coinciden - ADVERTENCIA
                        status = 'category_mismatch'
                        message = f'ML sugiere: {predicted_cat_name} ({predicted_cat_id}). Seleccionada: {product.ml_category_id.name}'

            lines.append({
                'wizard_id': self.id,
                'product_tmpl_id': product.id,
                'status': status,
                'status_message': message,
                'predicted_category_id': predicted_cat_id,
                'predicted_category_name': predicted_cat_name,
            })

        self.env['mercadolibre.publish.massive.line'].create(lines)

        self.write({'state': 'preview'})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicación Masiva'),
            'res_model': 'mercadolibre.publish.massive',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _check_sku_exists_in_ml(self, sku):
        """Verifica si un SKU ya existe en MercadoLibre"""
        if not sku or not self.account_id:
            return False

        try:
            http = self.env['mercadolibre.http']
            response = http._request(
                account_id=self.account_id.id,
                endpoint=f'/users/{self.account_id.ml_user_id}/items/search',
                method='GET',
                params={'seller_sku': sku, 'status': 'active,paused'}
            )
            results = response.get('data', {}).get('results', [])
            if results:
                return results[0]  # Retorna el ML ID del item existente
        except Exception as e:
            _logger.warning('Error verificando SKU %s: %s', sku, str(e))

        return False

    def _predict_category(self, product_name, site_id='MLM'):
        """
        Usa la API de MercadoLibre para predecir la categoría correcta
        basándose en el nombre del producto.

        Returns:
            dict: {'category_id': str, 'category_name': str, 'domain_name': str} o None
        """
        if not product_name:
            return None

        try:
            # Limpiar el nombre del producto
            import urllib.parse
            clean_name = urllib.parse.quote(product_name[:60])

            url = f'https://api.mercadolibre.com/sites/{site_id}/domain_discovery/search?q={clean_name}'
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    first_result = data[0]
                    return {
                        'category_id': first_result.get('category_id'),
                        'category_name': first_result.get('category_name'),
                        'domain_id': first_result.get('domain_id'),
                        'domain_name': first_result.get('domain_name'),
                    }
        except Exception as e:
            _logger.warning('Error prediciendo categoría para %s: %s', product_name[:30], str(e))

        return None

    def action_publish(self):
        """Publica los productos listos en MercadoLibre"""
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise ValidationError(_('La cuenta no tiene un token válido.'))

        # Cambiar estado
        self.write({'state': 'publishing'})

        log_lines = []
        log_lines.append('=' * 60)
        log_lines.append('    PUBLICACIÓN MASIVA EN MERCADOLIBRE')
        log_lines.append('=' * 60)
        log_lines.append(f'  Cuenta: {self.account_id.name}')
        log_lines.append(f'  Fecha: {fields.Datetime.now()}')
        log_lines.append('')

        http = self.env['mercadolibre.http']
        ItemModel = self.env['mercadolibre.item']

        published_count = 0
        skipped_count = 0
        error_count = 0
        warning_count = 0

        # Filtrar solo los listos
        # Incluir tanto 'ready' como 'category_mismatch' (advertencia, no bloqueo)
        ready_lines = self.preview_line_ids.filtered(lambda l: l.status in ('ready', 'category_mismatch'))
        warning_lines = ready_lines.filtered(lambda l: l.status == 'category_mismatch')

        log_lines.append(f'  Productos a publicar: {len(ready_lines)}')
        if warning_lines:
            log_lines.append(f'  ⚠️ Con advertencia de categoría: {len(warning_lines)}')
        log_lines.append('')
        log_lines.append('-' * 60)

        for line in ready_lines:
            product = line.product_tmpl_id

            try:
                # Preparar datos usando la configuración del producto
                brand_name = product.ml_brand or 'Genérico'
                model_name = product.ml_model or product.default_code or product.name[:30]

                # family_name (requerido por User Products / Catálogo 2.0)
                # IMPORTANTE: Debe incluir marca, modelo y características
                # ML genera el título automáticamente desde family_name
                family_name = f"{brand_name} {model_name}"
                if len(family_name) < 20:
                    family_name = f"{brand_name} {product.name[:40]}"
                family_name = family_name[:60]

                # Imágenes (obtener primero, son requeridas)
                pictures = self._get_product_pictures(product)
                if not pictures:
                    error_count += 1
                    line.write({
                        'status': 'error',
                        'status_message': 'No se pudo subir imagen a MercadoLibre',
                    })
                    log_lines.append(f'  [ERROR] {product.name[:40]}: Sin imagen válida')
                    continue

                body = {
                    'family_name': family_name,  # NO usar 'title', ML lo genera
                    'category_id': product.ml_category_id.ml_category_id,
                    'price': round(product.list_price, 2),  # MXN solo permite 2 decimales
                    'currency_id': product.currency_id.name or 'MXN',
                    'available_quantity': int(product.qty_available) or 1,
                    'buying_mode': 'buy_it_now',
                    'condition': product.ml_condition or 'new',
                    'listing_type_id': product.ml_listing_type or 'gold_special',
                    'pictures': pictures,
                }

                # Atributos
                attributes = [
                    {'id': 'BRAND', 'value_name': brand_name},
                    {'id': 'MODEL', 'value_name': model_name},
                ]
                if product.default_code:
                    attributes.append({'id': 'SELLER_SKU', 'value_name': product.default_code})
                # GTIN solo si es un código de barras válido (numérico, 8-14 dígitos)
                if product.barcode and product.barcode.isdigit() and len(product.barcode) in (8, 12, 13, 14):
                    attributes.append({'id': 'GTIN', 'value_name': product.barcode})

                body['attributes'] = attributes

                # Shipping
                body['shipping'] = {
                    'mode': product.ml_shipping_mode or 'me2',
                    'free_shipping': product.ml_free_shipping or False,
                    'local_pick_up': product.ml_local_pick_up or False,
                }

                # Garantía
                if product.ml_warranty_type and product.ml_warranty_type != 'Sin garantía':
                    sale_terms = [
                        {'id': 'WARRANTY_TYPE', 'value_name': product.ml_warranty_type}
                    ]
                    if product.ml_warranty_time:
                        sale_terms.append({'id': 'WARRANTY_TIME', 'value_name': product.ml_warranty_time})
                    body['sale_terms'] = sale_terms

                # Publicar - intentar primero con family_name (Catálogo 2.0)
                # Si falla, reintentar con title (categorías tradicionales)
                try:
                    response = http._request(
                        account_id=self.account_id.id,
                        endpoint='/items',
                        method='POST',
                        body=body
                    )
                    item_data = response.get('data', {})
                except Exception as api_error:
                    error_str = str(api_error)
                    # Si el error es por family_name inválido, reintentar con title
                    if 'family name is invalid' in error_str or 'required_fields' in error_str:
                        _logger.info('Categoría no soporta family_name, reintentando con title para %s', product.name)
                        # Cambiar family_name por title
                        body['title'] = body.pop('family_name')
                        response = http._request(
                            account_id=self.account_id.id,
                            endpoint='/items',
                            method='POST',
                            body=body
                        )
                        item_data = response.get('data', {})
                    else:
                        raise  # Re-lanzar si es otro error

                ml_item_id = item_data.get('id')

                if ml_item_id:
                    # Enviar descripción por separado
                    if product.description_sale:
                        try:
                            http._request(
                                account_id=self.account_id.id,
                                endpoint=f'/items/{ml_item_id}/description',
                                method='POST',
                                body={'plain_text': product.description_sale}
                            )
                        except Exception:
                            pass

                    # Crear registro local
                    item, _is_new = ItemModel.create_from_ml_data(item_data, self.account_id)
                    item.write({
                        'product_tmpl_id': product.id,
                        'product_id': product.product_variant_id.id,
                    })

                    line.write({
                        'published': True,
                        'ml_item_id': ml_item_id,
                        'status': 'published',
                        'status_message': f'Publicado: {ml_item_id}',
                    })

                    published_count += 1
                    log_lines.append(f'  [OK] {product.name[:40]}')
                    log_lines.append(f'       → {ml_item_id}')
                else:
                    error_count += 1
                    line.write({
                        'status': 'error',
                        'status_message': 'No se obtuvo ID de ML',
                    })
                    log_lines.append(f'  [ERROR] {product.name[:40]}: Sin ID')

                # Rate limit
                time.sleep(0.3)

            except Exception as e:
                error_count += 1
                # Extraer mensaje de error más detallado
                error_msg = str(e)
                # Intentar obtener más detalles del error de la API
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail = e.response.json()
                        error_msg = f"{error_detail.get('message', '')} - {error_detail.get('cause', [])}"
                    except Exception:
                        pass

                line.write({
                    'status': 'error',
                    'status_message': error_msg[:500],
                })
                log_lines.append(f'  [ERROR] {product.name[:40]}')
                log_lines.append(f'          {error_msg[:400]}')
                _logger.error('Error publicando %s: %s', product.name, error_msg)
                _logger.error('Body enviado: %s', body if 'body' in dir() else 'N/A')

        # Contar omitidos
        skipped_count = len(self.preview_line_ids) - len(ready_lines)

        # Resumen
        log_lines.append('')
        log_lines.append('=' * 60)
        log_lines.append('  RESUMEN')
        log_lines.append('=' * 60)
        log_lines.append(f'  Publicados: {published_count}')
        log_lines.append(f'  Omitidos:   {skipped_count}')
        log_lines.append(f'  Errores:    {error_count}')
        log_lines.append('=' * 60)

        self.write({
            'state': 'done',
            'publish_log': '\n'.join(log_lines),
            'published_count': published_count,
            'skipped_count': skipped_count,
            'error_count': error_count,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicación Masiva'),
            'res_model': 'mercadolibre.publish.massive',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_product_pictures(self, product):
        """
        Obtiene las URLs de imágenes para publicar.
        Incluye validación de tamaño y redimensionado automático.
        """
        pictures = []
        ImageService = self.env['mercadolibre.image.service']
        ImageModel = self.env['mercadolibre.image']

        # Lista de imágenes a subir: (imagen_base64, nombre_archivo)
        images_to_upload = []

        # 1. Imagen principal
        if product.image_1920:
            img_b64 = product.image_1920
            if isinstance(img_b64, bytes):
                img_b64 = img_b64.decode('utf-8')
            images_to_upload.append((img_b64, f'{product.default_code or product.id}_main.jpg'))

        # 2. Imágenes adicionales (máximo 9 adicionales = 10 total)
        if hasattr(product, 'product_template_image_ids') and product.product_template_image_ids:
            for idx, extra_img in enumerate(product.product_template_image_ids[:9]):
                if extra_img.image_1920:
                    img_b64 = extra_img.image_1920
                    if isinstance(img_b64, bytes):
                        img_b64 = img_b64.decode('utf-8')
                    images_to_upload.append((img_b64, f'{product.default_code or product.id}_extra_{idx+1}.jpg'))

        # Subir todas las imágenes con validación y resize
        for img_b64, filename in images_to_upload:
            try:
                # Validar y redimensionar si es necesario (mínimo 500px para ML)
                try:
                    validation = ImageService.validate_image_size(img_b64)
                    if validation.get('needs_resize'):
                        _logger.info('Redimensionando imagen %s de %dx%d a 1200px',
                                   filename, validation.get('width', 0), validation.get('height', 0))
                        img_b64 = ImageService.resize_image(img_b64, 1200)
                except Exception as ve:
                    _logger.warning('Error validando imagen %s: %s', filename, str(ve))

                # Subir a ML
                result = ImageService.upload_image_base64(
                    self.account_id.id,
                    img_b64,
                    filename,
                    auto_resize=True  # Respaldo por si la validación falló
                )

                if result.get('success'):
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

        return pictures

    def action_back(self):
        """Volver a configuración"""
        self.write({'state': 'draft'})
        self.preview_line_ids.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicación Masiva'),
            'res_model': 'mercadolibre.publish.massive',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_items(self):
        """Ver items publicados"""
        published_ids = self.preview_line_ids.filtered(
            lambda l: l.published
        ).mapped('product_tmpl_id.ml_item_ids').ids

        return {
            'type': 'ir.actions.act_window',
            'name': _('Items Publicados'),
            'res_model': 'mercadolibre.item',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', published_ids)],
        }


class MercadolibrePublishMassiveLine(models.TransientModel):
    _name = 'mercadolibre.publish.massive.line'
    _description = 'Línea de Publicación Masiva'

    wizard_id = fields.Many2one(
        'mercadolibre.publish.massive',
        string='Wizard',
        ondelete='cascade'
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto'
    )

    # Campos relacionados para mostrar en vista
    product_name = fields.Char(
        related='product_tmpl_id.name',
        string='Nombre'
    )
    product_default_code = fields.Char(
        related='product_tmpl_id.default_code',
        string='SKU'
    )
    ml_category_name = fields.Char(
        related='product_tmpl_id.ml_category_id.name',
        string='Categoría ML'
    )
    product_price = fields.Float(
        related='product_tmpl_id.list_price',
        string='Precio'
    )
    product_qty = fields.Float(
        related='product_tmpl_id.qty_available',
        string='Stock'
    )
    has_image = fields.Boolean(
        string='Imagen',
        compute='_compute_has_image'
    )

    # Estado
    status = fields.Selection([
        ('ready', 'Listo'),
        ('category_mismatch', 'Categoría Incorrecta'),
        ('no_category', 'Sin Categoría'),
        ('not_leaf_category', 'Categoría No Hoja'),
        ('no_image', 'Sin Imagen'),
        ('low_price', 'Precio Bajo'),
        ('already_published', 'Ya Publicado'),
        ('sku_exists', 'SKU Existe en ML'),
        ('published', 'Publicado'),
        ('error', 'Error'),
    ], string='Estado', default='ready')
    status_message = fields.Char(string='Mensaje')

    # Predicción de categoría
    predicted_category_id = fields.Char(string='Categoría Sugerida ID')
    predicted_category_name = fields.Char(string='Categoría Sugerida')

    # Resultado
    published = fields.Boolean(string='Publicado', default=False)
    ml_item_id = fields.Char(string='ID Item ML')

    @api.depends('product_tmpl_id.image_1920')
    def _compute_has_image(self):
        for record in self:
            record.has_image = bool(record.product_tmpl_id.image_1920)
