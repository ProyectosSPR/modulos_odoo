# -*- coding: utf-8 -*-

import base64
import io
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MlLabelTemplate(models.Model):
    _name = 'ml.label.template'
    _description = 'Plantilla de Etiqueta MercadoLibre'
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de la plantilla'
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )

    # PDF de muestra para diseñar
    sample_pdf = fields.Binary(
        string='PDF Ejemplo',
        required=True,
        attachment=True,
        help='PDF de ejemplo para diseñar la plantilla (generalmente una etiqueta ML descargada)'
    )
    sample_pdf_filename = fields.Char(
        string='Nombre Archivo'
    )

    # Preview generado (imagen primera página)
    preview_image = fields.Binary(
        string='Vista Previa',
        compute='_compute_preview_image',
        store=True,
        attachment=True
    )

    # Campos de texto configurados
    field_ids = fields.One2many(
        'ml.label.template.field',
        'template_id',
        string='Campos',
        copy=True
    )

    # Dimensiones del PDF (auto-detectadas)
    pdf_width = fields.Integer(
        string='Ancho PDF (px)',
        readonly=True,
        help='Ancho en píxeles del PDF'
    )
    pdf_height = fields.Integer(
        string='Alto PDF (px)',
        readonly=True,
        help='Alto en píxeles del PDF'
    )

    # Estadísticas
    field_count = fields.Integer(
        string='N° Campos',
        compute='_compute_field_count'
    )
    usage_count = fields.Integer(
        string='Usos',
        compute='_compute_usage_count',
        help='Cantidad de tipos logísticos que usan esta plantilla'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )

    description = fields.Text(
        string='Descripción',
        help='Notas sobre esta plantilla'
    )

    @api.depends('sample_pdf')
    def _compute_preview_image(self):
        """Genera imagen preview del PDF usando pdf2image o PyMuPDF"""
        for record in self:
            if not record.sample_pdf:
                record.preview_image = False
                continue

            try:
                # Intentar con pdf2image (requiere poppler)
                try:
                    from pdf2image import convert_from_bytes

                    pdf_bytes = base64.b64decode(record.sample_pdf)
                    images = convert_from_bytes(
                        pdf_bytes,
                        first_page=1,
                        last_page=1,
                        dpi=150
                    )

                    if images:
                        img_buffer = io.BytesIO()
                        images[0].save(img_buffer, format='PNG')
                        record.preview_image = base64.b64encode(img_buffer.getvalue())
                    else:
                        record.preview_image = False

                except ImportError:
                    # Fallback: intentar con PyMuPDF (fitz)
                    try:
                        import fitz

                        pdf_bytes = base64.b64decode(record.sample_pdf)
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        page = doc[0]

                        # Renderizar a imagen
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img_bytes = pix.tobytes("png")

                        record.preview_image = base64.b64encode(img_bytes)
                        doc.close()

                    except ImportError:
                        _logger.warning(
                            'No se pudo generar preview: instalar pdf2image o PyMuPDF'
                        )
                        record.preview_image = False

            except Exception as e:
                _logger.error(f'Error generando preview para plantilla {record.name}: {e}')
                record.preview_image = False

    @api.depends('field_ids')
    def _compute_field_count(self):
        for record in self:
            record.field_count = len(record.field_ids.filtered(lambda f: f.active))

    def _compute_usage_count(self):
        for record in self:
            record.usage_count = self.env['mercadolibre.logistic.type'].search_count([
                ('label_template_id', '=', record.id)
            ])

    @api.onchange('sample_pdf')
    def _onchange_sample_pdf(self):
        """Auto-detectar dimensiones del PDF"""
        if not self.sample_pdf:
            self.pdf_width = 0
            self.pdf_height = 0
            return

        try:
            from PyPDF2 import PdfReader

            pdf_bytes = base64.b64decode(self.sample_pdf)
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))

            if len(pdf_reader.pages) > 0:
                page = pdf_reader.pages[0]
                # Convertir de puntos a píxeles (72 DPI es estándar PDF)
                # Para visualización usamos 150 DPI
                dpi_scale = 150 / 72
                self.pdf_width = int(float(page.mediabox.width) * dpi_scale)
                self.pdf_height = int(float(page.mediabox.height) * dpi_scale)
            else:
                self.pdf_width = 0
                self.pdf_height = 0

        except Exception as e:
            _logger.error(f'Error detectando dimensiones PDF: {e}')
            self.pdf_width = 0
            self.pdf_height = 0

    @api.constrains('sample_pdf')
    def _check_sample_pdf(self):
        """Validar que sea un PDF válido"""
        for record in self:
            if record.sample_pdf:
                try:
                    from PyPDF2 import PdfReader

                    pdf_bytes = base64.b64decode(record.sample_pdf)
                    pdf_reader = PdfReader(io.BytesIO(pdf_bytes))

                    if len(pdf_reader.pages) == 0:
                        raise ValidationError(_('El PDF no contiene páginas.'))

                    if len(pdf_reader.pages) > 1:
                        _logger.warning(
                            f'Plantilla {record.name}: PDF tiene {len(pdf_reader.pages)} páginas, '
                            'solo se usará la primera.'
                        )

                except Exception as e:
                    raise ValidationError(_(
                        'El archivo no es un PDF válido o está corrupto: %s'
                    ) % str(e))

    def action_open_editor(self):
        """Abre el editor visual"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Editor - {self.name}',
            'res_model': 'ml.label.template',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('mercadolibre_label_editor.view_ml_label_template_editor').id,
            'target': 'fullscreen',
        }

    def action_preview_with_sample_data(self):
        """Abre wizard de preview con datos de ejemplo"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vista Previa con Datos',
            'res_model': 'ml.label.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
            }
        }

    def action_duplicate_template(self):
        """Duplica la plantilla con todos sus campos"""
        self.ensure_one()
        new_template = self.copy({
            'name': _('%s (Copia)') % self.name
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Plantilla Duplicada',
            'res_model': 'ml.label.template',
            'res_id': new_template.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_usage(self):
        """Ver tipos logísticos que usan esta plantilla"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Uso de {self.name}',
            'res_model': 'mercadolibre.logistic.type',
            'view_mode': 'tree,form',
            'domain': [('label_template_id', '=', self.id)],
        }
