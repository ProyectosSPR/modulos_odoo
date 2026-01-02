# -*- coding: utf-8 -*-

import base64
import requests
import logging
from io import BytesIO
from odoo import models, api, fields, _
from odoo.exceptions import UserError

try:
    from PIL import Image
except ImportError:
    Image = None

_logger = logging.getLogger(__name__)

# Constantes de MercadoLibre para imágenes
ML_IMAGE_MIN_SIZE = 500  # Mínimo requerido por ML
ML_IMAGE_RECOMMENDED_SIZE = 1200  # Recomendado para zoom
ML_IMAGE_MAX_SIZE = 2048  # Máximo permitido


class MercadolibreImage(models.Model):
    _name = 'mercadolibre.image'
    _description = 'Imagen subida a MercadoLibre'
    _order = 'create_date desc'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='cascade'
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        ondelete='set null'
    )
    ml_picture_id = fields.Char(
        string='ID Imagen ML',
        readonly=True,
        index=True
    )
    ml_url = fields.Char(
        string='URL MercadoLibre',
        readonly=True
    )
    ml_secure_url = fields.Char(
        string='URL Segura (HTTPS)',
        readonly=True
    )
    ml_size = fields.Char(
        string='Tamaño',
        readonly=True
    )
    ml_max_size = fields.Char(
        string='Tamaño Máximo',
        readonly=True
    )
    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('uploaded', 'Subida'),
        ('error', 'Error'),
    ], string='Estado', default='draft')
    error_message = fields.Text(
        string='Mensaje de Error'
    )

    @api.depends('ml_picture_id', 'product_tmpl_id')
    def _compute_name(self):
        for record in self:
            if record.product_tmpl_id:
                record.name = f'{record.product_tmpl_id.name} - {record.ml_picture_id or "Pendiente"}'
            else:
                record.name = record.ml_picture_id or 'Nueva Imagen'


class MercadolibreImageService(models.AbstractModel):
    _name = 'mercadolibre.image.service'
    _description = 'Servicio de Imágenes MercadoLibre'

    @api.model
    def get_image_dimensions(self, image_base64):
        """
        Obtiene las dimensiones de una imagen en base64.

        Args:
            image_base64: Imagen en formato base64

        Returns:
            tuple: (width, height) o (0, 0) si hay error
        """
        if not Image:
            _logger.warning('PIL no está instalado, no se pueden obtener dimensiones')
            return (0, 0)

        # Validar que hay datos de imagen
        if not image_base64:
            _logger.warning('No hay datos de imagen')
            return (0, 0)

        # Convertir bytes a string si es necesario
        if isinstance(image_base64, bytes):
            try:
                image_base64 = image_base64.decode('utf-8')
            except Exception:
                _logger.warning('Error decodificando bytes de imagen')
                return (0, 0)

        # Validar longitud mínima (una imagen válida en base64 tiene al menos ~100 caracteres)
        if len(image_base64) < 100:
            _logger.warning('Datos de imagen muy cortos (%d caracteres), probablemente no es una imagen válida', len(image_base64))
            return (0, 0)

        try:
            # Remover prefijo si existe (data:image/jpeg;base64,)
            if ',' in image_base64:
                image_base64 = image_base64.split(',')[1]

            # Corregir padding de base64 si es necesario
            padding = 4 - (len(image_base64) % 4)
            if padding != 4:
                image_base64 += '=' * padding

            image_data = base64.b64decode(image_base64)
            img = Image.open(BytesIO(image_data))
            return img.size  # (width, height)
        except Exception as e:
            _logger.error('Error obteniendo dimensiones de imagen: %s', str(e))
            return (0, 0)

    @api.model
    def validate_image_size(self, image_base64):
        """
        Valida si una imagen cumple con los requisitos de MercadoLibre.

        Args:
            image_base64: Imagen en formato base64

        Returns:
            dict: {
                'valid': bool,
                'width': int,
                'height': int,
                'min_side': int,
                'needs_resize': bool,
                'message': str
            }
        """
        width, height = self.get_image_dimensions(image_base64)

        if width == 0 or height == 0:
            return {
                'valid': False,
                'width': 0,
                'height': 0,
                'min_side': 0,
                'needs_resize': False,
                'message': _('No se pudo leer la imagen')
            }

        min_side = min(width, height)
        max_side = max(width, height)

        result = {
            'valid': min_side >= ML_IMAGE_MIN_SIZE,
            'width': width,
            'height': height,
            'min_side': min_side,
            'max_side': max_side,
            'needs_resize': min_side < ML_IMAGE_MIN_SIZE,
            'message': ''
        }

        if min_side < ML_IMAGE_MIN_SIZE:
            result['message'] = _(
                'La imagen es muy pequeña (%dx%d px). '
                'MercadoLibre requiere mínimo %d px en un lado. '
                'Recomendado: %dx%d px para zoom.'
            ) % (width, height, ML_IMAGE_MIN_SIZE, ML_IMAGE_RECOMMENDED_SIZE, ML_IMAGE_RECOMMENDED_SIZE)
        elif max_side > ML_IMAGE_MAX_SIZE:
            result['message'] = _(
                'La imagen es muy grande (%dx%d px). '
                'Se redimensionará automáticamente.'
            ) % (width, height)
        else:
            result['message'] = _('Tamaño válido: %dx%d px') % (width, height)

        return result

    @api.model
    def resize_image(self, image_base64, target_size=None, maintain_aspect=True):
        """
        Redimensiona una imagen a un tamaño objetivo.

        Args:
            image_base64: Imagen en formato base64
            target_size: Tamaño objetivo (int) - se aplicará al lado más pequeño
            maintain_aspect: Mantener proporción original

        Returns:
            str: Imagen redimensionada en base64 o None si hay error
        """
        if not Image:
            raise UserError(_('PIL (Pillow) no está instalado. No se puede redimensionar.'))

        if target_size is None:
            target_size = ML_IMAGE_RECOMMENDED_SIZE

        try:
            # Remover prefijo si existe
            if ',' in image_base64:
                image_base64 = image_base64.split(',')[1]

            image_data = base64.b64decode(image_base64)
            img = Image.open(BytesIO(image_data))

            # Obtener dimensiones originales
            orig_width, orig_height = img.size

            if maintain_aspect:
                # Calcular nuevo tamaño manteniendo proporción
                # El lado más pequeño será target_size
                if orig_width <= orig_height:
                    # Imagen vertical o cuadrada
                    new_width = target_size
                    new_height = int(orig_height * (target_size / orig_width))
                else:
                    # Imagen horizontal
                    new_height = target_size
                    new_width = int(orig_width * (target_size / orig_height))
            else:
                # Forzar tamaño cuadrado
                new_width = target_size
                new_height = target_size

            # Redimensionar con alta calidad
            resized_img = img.resize((new_width, new_height), Image.LANCZOS)

            # Convertir a RGB si es necesario (para JPEG)
            if resized_img.mode in ('RGBA', 'P'):
                resized_img = resized_img.convert('RGB')

            # Guardar en buffer
            buffer = BytesIO()
            resized_img.save(buffer, format='JPEG', quality=95)
            buffer.seek(0)

            # Retornar como base64
            return base64.b64encode(buffer.read()).decode('utf-8')

        except Exception as e:
            _logger.error('Error redimensionando imagen: %s', str(e))
            raise UserError(_('Error al redimensionar imagen: %s') % str(e))

    @api.model
    def upload_image_base64(self, account_id, image_base64, filename='image.jpg',
                            auto_resize=False, target_size=None):
        """
        Sube una imagen en base64 a MercadoLibre.

        Args:
            account_id: ID de la cuenta MercadoLibre
            image_base64: Imagen en formato base64 (sin prefijo data:image/...)
            filename: Nombre del archivo
            auto_resize: Si True, redimensiona automáticamente si es muy pequeña
            target_size: Tamaño objetivo para redimensionar (default: 1200)

        Returns:
            dict: Datos de la imagen subida con 'id', 'url', 'secure_url', etc.
        """
        # Validar y redimensionar si es necesario
        if auto_resize:
            validation = self.validate_image_size(image_base64)
            if validation.get('needs_resize'):
                _logger.info('Redimensionando imagen de %dx%d a %d px',
                           validation['width'], validation['height'],
                           target_size or ML_IMAGE_RECOMMENDED_SIZE)
                image_base64 = self.resize_image(image_base64, target_size)
        account = self.env['mercadolibre.account'].browse(account_id)
        if not account.exists():
            raise UserError(_('Cuenta MercadoLibre no encontrada.'))

        # Obtener token válido
        try:
            access_token = account.get_valid_token()
        except Exception as e:
            raise UserError(_('Error al obtener token: %s') % str(e))

        # Decodificar base64
        try:
            # Remover prefijo si existe (data:image/jpeg;base64,)
            if ',' in image_base64:
                image_base64 = image_base64.split(',')[1]
            image_data = base64.b64decode(image_base64)
        except Exception as e:
            raise UserError(_('Error decodificando imagen base64: %s') % str(e))

        # Determinar tipo de contenido
        content_type = 'image/jpeg'
        if filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        elif filename.lower().endswith('.webp'):
            content_type = 'image/webp'

        # Subir a MercadoLibre
        url = 'https://api.mercadolibre.com/pictures/items/upload'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        try:
            files = {
                'file': (filename, BytesIO(image_data), content_type)
            }

            _logger.info('Subiendo imagen a MercadoLibre: %s', filename)
            response = requests.post(url, headers=headers, files=files, timeout=60)

            if response.status_code in [200, 201]:
                data = response.json()
                _logger.info('Imagen subida exitosamente. Respuesta API: %s', data)

                # Obtener ID de la imagen
                picture_id = data.get('id', '')

                # Obtener URLs - la API puede devolverlas de diferentes formas
                url = data.get('url')
                secure_url = data.get('secure_url')

                # Si no hay URLs, construirlas desde el ID
                # Formato estándar ML: https://http2.mlstatic.com/D_{ID}-F.jpg
                if not secure_url and picture_id:
                    secure_url = f'https://http2.mlstatic.com/D_{picture_id}-F.jpg'
                if not url and picture_id:
                    url = f'http://http2.mlstatic.com/D_{picture_id}-F.jpg'

                return {
                    'success': True,
                    'id': picture_id,
                    'url': url,
                    'secure_url': secure_url,
                    'size': data.get('size'),
                    'max_size': data.get('max_size'),
                    'variations': data.get('variations', []),
                }
            else:
                error_msg = response.text
                _logger.error('Error subiendo imagen: %s - %s', response.status_code, error_msg)
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {error_msg}'
                }

        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexión subiendo imagen: %s', str(e))
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}'
            }

    @api.model
    def upload_product_images(self, account_id, product_tmpl_id):
        """
        Sube todas las imágenes de un producto a MercadoLibre.

        Args:
            account_id: ID de la cuenta MercadoLibre
            product_tmpl_id: ID del product.template

        Returns:
            list: Lista de diccionarios con formato {'source': url} para ML API
        """
        product = self.env['product.template'].browse(product_tmpl_id)
        if not product.exists():
            return []

        pictures = []
        ImageModel = self.env['mercadolibre.image']

        # Imagen principal
        if product.image_1920:
            # Verificar si ya existe una imagen subida para este producto
            existing = ImageModel.search([
                ('account_id', '=', account_id),
                ('product_tmpl_id', '=', product_tmpl_id),
                ('state', '=', 'uploaded'),
                ('ml_secure_url', '!=', False),
            ], limit=1)

            if existing:
                pictures.append({'source': existing.ml_secure_url})
            else:
                result = self.upload_image_base64(
                    account_id,
                    product.image_1920.decode('utf-8') if isinstance(product.image_1920, bytes) else product.image_1920,
                    f'{product.default_code or product.id}_main.jpg'
                )

                if result.get('success'):
                    # Guardar registro de la imagen
                    ImageModel.create({
                        'account_id': account_id,
                        'product_tmpl_id': product_tmpl_id,
                        'ml_picture_id': result.get('id'),
                        'ml_url': result.get('url'),
                        'ml_secure_url': result.get('secure_url'),
                        'ml_size': result.get('size'),
                        'ml_max_size': result.get('max_size'),
                        'state': 'uploaded',
                    })
                    pictures.append({'source': result.get('secure_url')})
                else:
                    _logger.warning('No se pudo subir imagen principal: %s', result.get('error'))

        # Imágenes adicionales (product.image si existe el modelo)
        if hasattr(product, 'product_template_image_ids'):
            for idx, img in enumerate(product.product_template_image_ids[:9]):  # Max 9 adicionales
                if img.image_1920:
                    result = self.upload_image_base64(
                        account_id,
                        img.image_1920.decode('utf-8') if isinstance(img.image_1920, bytes) else img.image_1920,
                        f'{product.default_code or product.id}_{idx + 1}.jpg'
                    )
                    if result.get('success'):
                        ImageModel.create({
                            'account_id': account_id,
                            'product_tmpl_id': product_tmpl_id,
                            'ml_picture_id': result.get('id'),
                            'ml_url': result.get('url'),
                            'ml_secure_url': result.get('secure_url'),
                            'ml_size': result.get('size'),
                            'ml_max_size': result.get('max_size'),
                            'state': 'uploaded',
                        })
                        pictures.append({'source': result.get('secure_url')})

        return pictures

    @api.model
    def get_product_ml_pictures(self, account_id, product_tmpl_id):
        """
        Obtiene las URLs de imágenes ya subidas para un producto.

        Returns:
            list: Lista de diccionarios {'source': url}
        """
        images = self.env['mercadolibre.image'].search([
            ('account_id', '=', account_id),
            ('product_tmpl_id', '=', product_tmpl_id),
            ('state', '=', 'uploaded'),
            ('ml_secure_url', '!=', False),
        ])

        return [{'source': img.ml_secure_url} for img in images]


class ProductTemplateMLImages(models.Model):
    _inherit = 'product.template'

    ml_image_ids = fields.One2many(
        'mercadolibre.image',
        'product_tmpl_id',
        string='Imágenes ML'
    )
    ml_image_count = fields.Integer(
        string='Imágenes en ML',
        compute='_compute_ml_image_count'
    )
    ml_has_uploaded_images = fields.Boolean(
        string='Tiene Imágenes en ML',
        compute='_compute_ml_image_count'
    )

    @api.depends('ml_image_ids', 'ml_image_ids.state')
    def _compute_ml_image_count(self):
        for record in self:
            uploaded = record.ml_image_ids.filtered(lambda i: i.state == 'uploaded')
            record.ml_image_count = len(uploaded)
            record.ml_has_uploaded_images = len(uploaded) > 0

    def action_upload_images_to_ml(self):
        """Abre wizard para subir imágenes a MercadoLibre"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Subir Imágenes a MercadoLibre'),
            'res_model': 'mercadolibre.image.upload.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.id,
            }
        }

    def action_view_ml_images(self):
        """Ver imágenes subidas a ML"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imágenes en MercadoLibre'),
            'res_model': 'mercadolibre.image',
            'view_mode': 'tree,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {'default_product_tmpl_id': self.id},
        }
