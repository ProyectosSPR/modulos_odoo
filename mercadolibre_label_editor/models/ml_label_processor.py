# -*- coding: utf-8 -*-

import base64
import io
import re
import logging
from datetime import datetime
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MlLabelProcessor(models.AbstractModel):
    _name = 'ml.label.processor'
    _description = 'Procesador de Etiquetas MercadoLibre'

    @api.model
    def apply_template(self, pdf_bytes, template, context_record):
        """
        Aplica una plantilla sobre un PDF original agregando campos de texto.

        Args:
            pdf_bytes: bytes del PDF original
            template: ml.label.template record
            context_record: sale.order o mercadolibre.order (para resolver variables)

        Returns:
            bytes del PDF modificado

        Raises:
            UserError: Si hay errores en el procesamiento
        """
        if not pdf_bytes:
            raise UserError(_('No se proporcionó PDF para procesar'))

        if not template or not template.field_ids:
            _logger.info('No hay plantilla o campos configurados, retornando PDF original')
            return pdf_bytes

        try:
            from PyPDF2 import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas
            from reportlab.lib.colors import HexColor
        except ImportError as e:
            raise UserError(_(
                'Falta instalar dependencias: PyPDF2 y reportlab.\n'
                'Ejecutar: pip3 install PyPDF2 reportlab'
            ))

        try:
            # 1. Leer PDF original
            original_pdf = PdfReader(io.BytesIO(pdf_bytes))
            if len(original_pdf.pages) == 0:
                raise UserError(_('El PDF original no contiene páginas'))

            page = original_pdf.pages[0]

            # Obtener dimensiones de la página
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            _logger.info(
                f'Procesando PDF: {page_width}x{page_height} pts, '
                f'plantilla: {template.name}, campos: {len(template.field_ids)}'
            )

            # 2. Crear overlay con los campos de texto
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(page_width, page_height))

            # 3. Renderizar cada campo activo
            active_fields = template.field_ids.filtered(lambda f: f.active)
            rendered_count = 0

            # Calcular dimensiones del template en puntos nativos (72 DPI)
            # El template guarda pdf_width/height en escala 150 DPI
            template_width_pts = template.pdf_width * (72 / 150) if template.pdf_width else page_width
            template_height_pts = template.pdf_height * (72 / 150) if template.pdf_height else page_height

            # Factor de escala si el PDF real tiene dimensiones diferentes al template
            scale_x = page_width / template_width_pts if template_width_pts else 1.0
            scale_y = page_height / template_height_pts if template_height_pts else 1.0

            _logger.debug(
                f'Dimensiones template: {template_width_pts:.1f}x{template_height_pts:.1f} pts, '
                f'PDF real: {page_width:.1f}x{page_height:.1f} pts, '
                f'escala: ({scale_x:.3f}, {scale_y:.3f})'
            )

            for field in active_fields:
                try:
                    text = self._resolve_field_value(field, context_record)

                    if not text:
                        _logger.warning(f'Campo {field.name} resultó en texto vacío')
                        continue

                    # Las coordenadas en BD están en puntos nativos (72 DPI)
                    # position_y está invertida (Y=0 abajo en formato PyPDF2)
                    # Solo necesitamos escalar si el PDF real tiene diferente tamaño
                    x_pts = field.position_x * scale_x

                    # La posición Y en BD ya está en formato PyPDF2 (desde abajo)
                    # Solo escalar proporcionalmente
                    y_pts = field.position_y * scale_y

                    # Configurar estilo de fuente
                    can.setFont(field.font_family, field.font_size)

                    # Configurar color
                    try:
                        can.setFillColor(HexColor(field.color))
                    except:
                        _logger.warning(f'Color inválido {field.color}, usando negro')
                        can.setFillColor(HexColor('#000000'))

                    # Aplicar rotación y dibujar texto
                    if field.rotation and field.rotation != 0:
                        can.saveState()
                        can.translate(x_pts, y_pts)
                        can.rotate(field.rotation)

                        # Alineación con rotación
                        x_offset = self._calculate_text_offset(
                            can, text, field.align, field.font_family, field.font_size
                        )
                        can.drawString(x_offset, 0, str(text))
                        can.restoreState()
                    else:
                        # Sin rotación
                        x_offset = self._calculate_text_offset(
                            can, text, field.align, field.font_family, field.font_size
                        )
                        can.drawString(x_pts + x_offset, y_pts, str(text))

                    rendered_count += 1
                    _logger.debug(
                        f'Campo renderizado: {field.name} = "{text}" '
                        f'en ({x_pts:.1f}, {y_pts:.1f})'
                    )

                except Exception as e:
                    _logger.error(f'Error renderizando campo {field.name}: {e}')
                    # Continuar con el siguiente campo

            can.save()
            _logger.info(f'Renderizados {rendered_count}/{len(active_fields)} campos')

            # 4. Combinar PDFs (overlay sobre original)
            packet.seek(0)
            overlay_pdf = PdfReader(packet)
            page.merge_page(overlay_pdf.pages[0])

            # 5. Escribir resultado final
            output = PdfWriter()
            output.add_page(page)

            result_stream = io.BytesIO()
            output.write(result_stream)
            result_bytes = result_stream.getvalue()

            _logger.info(
                f'PDF procesado exitosamente: '
                f'{len(pdf_bytes)} bytes -> {len(result_bytes)} bytes'
            )

            return result_bytes

        except Exception as e:
            _logger.error(f'Error procesando PDF con plantilla: {e}', exc_info=True)
            raise UserError(_(
                'Error al procesar la etiqueta con la plantilla:\n%s'
            ) % str(e))

    def _calculate_text_offset(self, canvas_obj, text, align, font_name, font_size):
        """
        Calcula el offset X según la alineación del texto.

        Args:
            canvas_obj: objeto canvas de reportlab
            text: texto a medir
            align: 'left', 'center', 'right'
            font_name: nombre de la fuente
            font_size: tamaño de la fuente

        Returns:
            offset en puntos
        """
        if align == 'left':
            return 0

        text_width = canvas_obj.stringWidth(str(text), font_name, font_size)

        if align == 'center':
            return -text_width / 2
        elif align == 'right':
            return -text_width

        return 0

    def _resolve_field_value(self, field, record):
        """
        Resuelve el valor de un campo (estático o dinámico).

        Args:
            field: ml.label.template.field record
            record: registro de contexto (sale.order, mercadolibre.order, etc.)

        Returns:
            string con el valor resuelto
        """
        if field.field_type == 'static':
            return field.value

        # Procesar variables dinámicas ${...}
        value = field.value
        pattern = r'\$\{([^}]+)\}'

        def replace_var(match):
            var_path = match.group(1).strip()
            return self._resolve_variable(var_path, record)

        try:
            resolved = re.sub(pattern, replace_var, value)
            return resolved
        except Exception as e:
            _logger.error(f'Error resolviendo valor dinámico "{value}": {e}')
            return value  # Retornar valor original si falla

    def _resolve_variable(self, var_path, record):
        """
        Resuelve una variable individual como 'sale_order.name' o 'today'.

        Args:
            var_path: ruta de la variable (ej: 'sale_order.name')
            record: registro de contexto

        Returns:
            string con el valor resuelto
        """
        # Variables especiales
        if var_path == 'today':
            return datetime.now().strftime('%Y-%m-%d')
        elif var_path == 'now':
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        elif var_path.startswith('company.'):
            # Acceder a la compañía del usuario
            company = self.env.company
            attr = var_path.replace('company.', '')
            return str(self._safe_getattr(company, attr))

        # Variables de modelos
        # Soportar 'sale_order.name', 'ml_order.ml_order_id', etc.
        parts = var_path.split('.', 1)
        model_alias = parts[0]
        field_path = parts[1] if len(parts) > 1 else None

        # Mapear alias a registro real
        target_record = None

        if model_alias == 'sale_order':
            if record._name == 'sale.order':
                target_record = record
            elif hasattr(record, 'sale_order_id'):
                target_record = record.sale_order_id

        elif model_alias == 'ml_order':
            if record._name == 'mercadolibre.order':
                target_record = record
            elif hasattr(record, 'ml_order_ids') and record.ml_order_ids:
                target_record = record.ml_order_ids[0]

        elif model_alias == 'partner':
            if hasattr(record, 'partner_id'):
                target_record = record.partner_id

        else:
            # Intentar acceder directamente al campo en el registro actual
            if hasattr(record, model_alias):
                target_record = record
                field_path = var_path

        # Resolver el campo navegando por la ruta
        if target_record and field_path:
            return str(self._safe_getattr(target_record, field_path))
        elif target_record:
            return str(target_record.display_name)

        # Si no se pudo resolver, retornar la variable sin procesar
        _logger.warning(f'No se pudo resolver variable: ${{{var_path}}}')
        return f'${{{var_path}}}'

    def _safe_getattr(self, obj, attr_path):
        """
        Obtiene un atributo de manera segura navegando por relaciones.

        Args:
            obj: objeto Odoo
            attr_path: ruta del atributo (ej: 'partner_id.name')

        Returns:
            valor del atributo o cadena vacía
        """
        try:
            value = obj
            for attr in attr_path.split('.'):
                if not value:
                    return ''
                value = getattr(value, attr, '')

            # Formatear según tipo
            if isinstance(value, datetime):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(value, (int, float)):
                return str(value)
            elif hasattr(value, 'name'):
                return value.name
            else:
                return str(value) if value else ''
        except Exception as e:
            _logger.warning(f'Error obteniendo atributo {attr_path}: {e}')
            return ''

    @api.model
    def preview_template(self, template, sample_data=None):
        """
        Genera un PDF de preview usando datos de muestra.

        Args:
            template: ml.label.template record
            sample_data: dict con datos de ejemplo (opcional)

        Returns:
            bytes del PDF generado
        """
        if not template.sample_pdf:
            raise UserError(_('La plantilla no tiene un PDF de ejemplo'))

        # Crear objeto mock con datos de muestra
        class MockRecord:
            def __init__(self, data):
                self._name = 'mock.record'
                for key, value in (data or {}).items():
                    setattr(self, key, value)

        default_sample = {
            'name': 'SO0001',
            'partner_id': type('obj', (object,), {'name': 'Cliente Ejemplo'}),
            'date_order': datetime.now(),
            'ml_order_id': '123456789',
            'ml_pack_id': 'PACK-001',
        }

        mock_record = MockRecord(sample_data or default_sample)
        pdf_bytes = base64.b64decode(template.sample_pdf)

        return self.apply_template(pdf_bytes, template, mock_record)
