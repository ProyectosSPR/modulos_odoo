# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreLogisticType(models.Model):
    _inherit = 'mercadolibre.logistic.type'

    label_template_id = fields.Many2one(
        'ml.label.template',
        string='Plantilla Etiqueta',
        help='Plantilla para personalizar la etiqueta de envío ML con datos adicionales'
    )

    label_template_preview = fields.Binary(
        related='label_template_id.preview_image',
        string='Preview Plantilla',
        readonly=True
    )

    use_custom_label = fields.Boolean(
        string='Usar Plantilla Personalizada',
        compute='_compute_use_custom_label',
        store=True
    )

    @api.depends('download_shipping_label', 'label_template_id')
    def _compute_use_custom_label(self):
        """Indica si se usará plantilla personalizada"""
        for record in self:
            record.use_custom_label = bool(
                record.download_shipping_label and record.label_template_id
            )

    def action_edit_label_template(self):
        """Abrir editor de plantilla"""
        self.ensure_one()

        if not self.label_template_id:
            # Si no hay plantilla, abrir wizard para crear una
            return {
                'type': 'ir.actions.act_window',
                'name': 'Crear Plantilla de Etiqueta',
                'res_model': 'ml.label.template',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_name': f'Plantilla {self.name}',
                }
            }

        return self.label_template_id.action_open_editor()

    def action_preview_label_template(self):
        """Vista previa con datos de ejemplo"""
        self.ensure_one()

        if not self.label_template_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Plantilla',
                    'message': 'Primero debe configurar una plantilla de etiqueta.',
                    'type': 'warning',
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Vista Previa Plantilla',
            'res_model': 'ml.label.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.label_template_id.id,
                'default_logistic_type_id': self.id,
            }
        }

    def action_create_label_template(self):
        """Crear nueva plantilla para este tipo logístico"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Nueva Plantilla de Etiqueta',
            'res_model': 'ml.label.template',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_name': f'Plantilla {self.name}',
            }
        }
