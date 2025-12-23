# -*- coding: utf-8 -*-

import base64
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MlLabelPreviewWizard(models.TransientModel):
    _name = 'ml.label.preview.wizard'
    _description = 'Wizard de Vista Previa de Plantilla'

    template_id = fields.Many2one(
        'ml.label.template',
        string='Plantilla',
        required=True
    )

    logistic_type_id = fields.Many2one(
        'mercadolibre.logistic.type',
        string='Tipo Logístico'
    )

    # Datos de muestra
    sample_order_name = fields.Char(
        string='Número de Orden',
        default='SO0001',
        help='Ejemplo: SO0001, S00123'
    )

    sample_customer_name = fields.Char(
        string='Nombre Cliente',
        default='Juan Pérez',
        help='Nombre del cliente para la vista previa'
    )

    sample_ml_order_id = fields.Char(
        string='ID Orden ML',
        default='1234567890',
        help='Ejemplo: 1234567890'
    )

    sample_ml_pack_id = fields.Char(
        string='Pack ID',
        default='PACK-001',
        help='Ejemplo: PACK-001'
    )

    sample_company_name = fields.Char(
        string='Compañía',
        default=lambda self: self.env.company.name,
        help='Nombre de la compañía'
    )

    # PDF generado
    preview_pdf = fields.Binary(
        string='PDF Generado',
        readonly=True,
        attachment=False
    )

    preview_pdf_filename = fields.Char(
        string='Nombre Archivo',
        default='preview.pdf'
    )

    state = fields.Selection([
        ('draft', 'Configurar'),
        ('preview', 'Vista Previa'),
    ], default='draft')

    def action_generate_preview(self):
        """Genera el PDF de preview con los datos de muestra"""
        self.ensure_one()

        if not self.template_id.sample_pdf:
            raise UserError(_('La plantilla no tiene un PDF de ejemplo cargado.'))

        try:
            # Crear objeto mock con los datos de muestra
            class MockPartner:
                def __init__(self, name):
                    self.name = name
                    self.display_name = name

            class MockOrder:
                def __init__(self, wizard):
                    self._name = 'sale.order'
                    self.name = wizard.sample_order_name
                    self.partner_id = MockPartner(wizard.sample_customer_name)
                    self.ml_order_id = wizard.sample_ml_order_id
                    self.ml_pack_id = wizard.sample_ml_pack_id

            # Generar preview usando el procesador
            processor = self.env['ml.label.processor']
            pdf_bytes = base64.b64decode(self.template_id.sample_pdf)

            mock_order = MockOrder(self)
            modified_pdf = processor.apply_template(
                pdf_bytes=pdf_bytes,
                template=self.template_id,
                context_record=mock_order
            )

            # Guardar el resultado
            self.preview_pdf = base64.b64encode(modified_pdf)
            self.preview_pdf_filename = f'preview_{self.template_id.name}.pdf'
            self.state = 'preview'

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ml.label.preview.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        except Exception as e:
            _logger.error(f'Error generando preview: {e}', exc_info=True)
            raise UserError(_(
                'Error al generar la vista previa:\n%s'
            ) % str(e))

    def action_download_preview(self):
        """Descarga el PDF de preview"""
        self.ensure_one()

        if not self.preview_pdf:
            raise UserError(_('Primero debe generar la vista previa.'))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=preview_pdf&filename={self.preview_pdf_filename}&download=true',
            'target': 'self',
        }

    def action_back_to_config(self):
        """Volver a la configuración"""
        self.ensure_one()
        self.state = 'draft'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ml.label.preview.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
