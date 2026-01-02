# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Constantes
ML_IMAGE_MIN_SIZE = 500
ML_IMAGE_RECOMMENDED_SIZE = 1200


class MercadolibreImageUploadWizard(models.TransientModel):
    _name = 'mercadolibre.image.upload.wizard'
    _description = 'Subir Imágenes a MercadoLibre'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]"
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto',
        required=True
    )
    product_image = fields.Binary(
        string='Imagen del Producto',
        related='product_tmpl_id.image_1920',
        readonly=True
    )
    has_image = fields.Boolean(
        compute='_compute_has_image'
    )

    # Información de la imagen
    image_width = fields.Integer(
        string='Ancho (px)',
        compute='_compute_image_info',
        store=False
    )
    image_height = fields.Integer(
        string='Alto (px)',
        compute='_compute_image_info',
        store=False
    )
    image_size_text = fields.Char(
        string='Tamaño',
        compute='_compute_image_info',
        store=False
    )
    image_valid = fields.Boolean(
        string='Tamaño Válido',
        compute='_compute_image_info',
        store=False
    )
    image_needs_resize = fields.Boolean(
        string='Necesita Redimensionar',
        compute='_compute_image_info',
        store=False
    )
    image_warning = fields.Text(
        string='Advertencia',
        compute='_compute_image_info',
        store=False
    )

    # Opciones de redimensionado
    resize_option = fields.Selection([
        ('none', 'No redimensionar (puede fallar)'),
        ('min', 'Redimensionar a 500x500 (mínimo ML)'),
        ('recommended', 'Redimensionar a 1200x1200 (recomendado)'),
    ], string='Opción de Redimensionado', default='recommended')

    # Resultados
    state = fields.Selection([
        ('draft', 'Configuración'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], string='Estado', default='draft')

    result_log = fields.Text(
        string='Resultado',
        readonly=True
    )
    uploaded_count = fields.Integer(
        string='Imágenes Subidas',
        readonly=True
    )
    uploaded_urls = fields.Text(
        string='URLs Generadas',
        readonly=True
    )

    @api.depends('product_tmpl_id', 'product_tmpl_id.image_1920')
    def _compute_has_image(self):
        for record in self:
            record.has_image = bool(record.product_tmpl_id and record.product_tmpl_id.image_1920)

    @api.depends('product_tmpl_id', 'product_tmpl_id.image_1920')
    def _compute_image_info(self):
        ImageService = self.env['mercadolibre.image.service']
        for record in self:
            if record.product_tmpl_id and record.product_tmpl_id.image_1920:
                image_b64 = record.product_tmpl_id.image_1920
                if isinstance(image_b64, bytes):
                    image_b64 = image_b64.decode('utf-8')

                validation = ImageService.validate_image_size(image_b64)

                record.image_width = validation.get('width', 0)
                record.image_height = validation.get('height', 0)
                record.image_size_text = '%d x %d px' % (record.image_width, record.image_height)
                record.image_valid = validation.get('valid', False)
                record.image_needs_resize = validation.get('needs_resize', False)
                record.image_warning = validation.get('message', '')
            else:
                record.image_width = 0
                record.image_height = 0
                record.image_size_text = 'Sin imagen'
                record.image_valid = False
                record.image_needs_resize = False
                record.image_warning = ''

    def action_upload(self):
        """Sube las imágenes del producto a MercadoLibre"""
        self.ensure_one()

        if not self.has_image:
            raise UserError(_('El producto no tiene imagen para subir.'))

        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token válido.'))

        ImageService = self.env['mercadolibre.image.service']
        log_lines = []
        urls = []

        log_lines.append('=' * 50)
        log_lines.append('  SUBIDA DE IMÁGENES A MERCADOLIBRE')
        log_lines.append('=' * 50)
        log_lines.append('')
        log_lines.append(f'Producto: {self.product_tmpl_id.name}')
        log_lines.append(f'Cuenta: {self.account_id.name}')
        log_lines.append(f'Tamaño original: {self.image_size_text}')
        log_lines.append('')

        # Determinar si redimensionar y a qué tamaño
        auto_resize = self.resize_option != 'none'
        target_size = None
        if self.resize_option == 'min':
            target_size = ML_IMAGE_MIN_SIZE
            log_lines.append(f'Redimensionando a: {ML_IMAGE_MIN_SIZE}x{ML_IMAGE_MIN_SIZE} px')
        elif self.resize_option == 'recommended':
            target_size = ML_IMAGE_RECOMMENDED_SIZE
            log_lines.append(f'Redimensionando a: {ML_IMAGE_RECOMMENDED_SIZE}x{ML_IMAGE_RECOMMENDED_SIZE} px')
        else:
            log_lines.append('Sin redimensionar (puede fallar si es muy pequeña)')
        log_lines.append('')

        try:
            # Obtener imagen
            image_b64 = self.product_tmpl_id.image_1920
            if isinstance(image_b64, bytes):
                image_b64 = image_b64.decode('utf-8')

            # Redimensionar si es necesario
            if auto_resize and self.image_needs_resize:
                log_lines.append('Redimensionando imagen...')
                image_b64 = ImageService.resize_image(image_b64, target_size)
                # Verificar nuevo tamaño
                new_validation = ImageService.validate_image_size(image_b64)
                log_lines.append(f'Nuevo tamaño: {new_validation["width"]}x{new_validation["height"]} px')
                log_lines.append('')

            # Subir imagen
            log_lines.append('Subiendo a MercadoLibre...')
            result = ImageService.upload_image_base64(
                self.account_id.id,
                image_b64,
                f'{self.product_tmpl_id.default_code or self.product_tmpl_id.id}_main.jpg',
                auto_resize=False  # Ya redimensionamos arriba
            )

            if result.get('success'):
                # Obtener URLs (manejar None)
                ml_url = result.get('url') or ''
                ml_secure_url = result.get('secure_url') or ''
                ml_id = result.get('id') or ''

                # Guardar registro de la imagen
                self.env['mercadolibre.image'].create({
                    'account_id': self.account_id.id,
                    'product_tmpl_id': self.product_tmpl_id.id,
                    'ml_picture_id': ml_id,
                    'ml_url': ml_url,
                    'ml_secure_url': ml_secure_url,
                    'ml_size': result.get('size') or '',
                    'ml_max_size': result.get('max_size') or '',
                    'state': 'uploaded',
                })

                # Usar secure_url o url, lo que esté disponible
                url = ml_secure_url or ml_url or f'https://http2.mlstatic.com/D_{ml_id}-F.jpg'
                urls.append(url)

                log_lines.append('')
                log_lines.append('✓ Imagen subida exitosamente')
                log_lines.append(f'  ID: {ml_id}')
                log_lines.append(f'  URL: {url}')

                self.write({
                    'state': 'done',
                    'result_log': '\n'.join(log_lines),
                    'uploaded_count': 1,
                    'uploaded_urls': '\n'.join(urls),
                })
            else:
                log_lines.append('')
                log_lines.append(f'✗ Error: {result.get("error", "Error desconocido")}')
                self.write({
                    'state': 'error',
                    'result_log': '\n'.join(log_lines),
                })

        except Exception as e:
            log_lines.append('')
            log_lines.append(f'✗ Error: {str(e)}')
            self.write({
                'state': 'error',
                'result_log': '\n'.join(log_lines),
            })
            _logger.error('Error subiendo imágenes: %s', str(e))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Subir Imágenes a MercadoLibre'),
            'res_model': 'mercadolibre.image.upload.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_copy_urls(self):
        """Acción para indicar que se copiaron las URLs"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('URLs Copiadas'),
                'message': _('Copie las URLs del campo "URLs Generadas" para usarlas.'),
                'type': 'info',
                'sticky': False,
            }
        }
