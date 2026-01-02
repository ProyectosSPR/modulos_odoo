# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)


class MercadolibreCategoryAttribute(models.Model):
    _name = 'mercadolibre.category.attribute'
    _description = 'Atributo de Categoría MercadoLibre'
    _order = 'is_required desc, sequence, name'

    category_id = fields.Many2one(
        'mercadolibre.category',
        string='Categoría',
        required=True,
        ondelete='cascade',
        index=True
    )
    ml_attribute_id = fields.Char(
        string='ID Atributo ML',
        required=True,
        index=True
    )
    name = fields.Char(
        string='Nombre',
        required=True
    )
    value_type = fields.Selection([
        ('string', 'Texto'),
        ('number', 'Número'),
        ('number_unit', 'Número con Unidad'),
        ('boolean', 'Sí/No'),
        ('list', 'Lista'),
    ], string='Tipo de Valor', default='string')

    is_required = fields.Boolean(
        string='Requerido',
        default=False,
        help='Indica si este atributo es obligatorio para publicar en esta categoría'
    )
    is_allow_variations = fields.Boolean(
        string='Permite Variaciones',
        default=False,
        help='Indica si este atributo puede variar entre variaciones del producto'
    )
    hint = fields.Char(
        string='Ayuda',
        help='Texto de ayuda para completar este atributo'
    )
    tooltip = fields.Text(
        string='Tooltip',
        help='Descripción detallada del atributo'
    )

    # Valores predefinidos
    values_json = fields.Text(
        string='Valores JSON',
        help='Valores predefinidos en formato JSON'
    )
    values_display = fields.Text(
        string='Valores Disponibles',
        compute='_compute_values_display'
    )

    # Configuración
    default_value = fields.Char(
        string='Valor por Defecto'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )

    _sql_constraints = [
        ('category_attribute_uniq', 'unique(category_id, ml_attribute_id)',
         'El atributo ya existe para esta categoría.')
    ]

    @api.depends('values_json')
    def _compute_values_display(self):
        for record in self:
            if record.values_json:
                try:
                    values = json.loads(record.values_json)
                    if isinstance(values, list):
                        display = ', '.join([v.get('name', str(v)) if isinstance(v, dict) else str(v) for v in values[:10]])
                        if len(values) > 10:
                            display += f'... (+{len(values) - 10} más)'
                        record.values_display = display
                    else:
                        record.values_display = str(values)
                except Exception:
                    record.values_display = record.values_json
            else:
                record.values_display = ''

    def get_values_list(self):
        """Retorna la lista de valores disponibles"""
        self.ensure_one()
        if self.values_json:
            try:
                return json.loads(self.values_json)
            except Exception:
                return []
        return []


class MercadolibreCategoryExtended(models.Model):
    _inherit = 'mercadolibre.category'

    attribute_ids = fields.One2many(
        'mercadolibre.category.attribute',
        'category_id',
        string='Atributos'
    )
    attribute_count = fields.Integer(
        string='Cantidad Atributos',
        compute='_compute_attribute_count'
    )
    required_attribute_count = fields.Integer(
        string='Atributos Requeridos',
        compute='_compute_attribute_count'
    )
    attributes_loaded = fields.Boolean(
        string='Atributos Cargados',
        default=False
    )

    @api.depends('attribute_ids', 'attribute_ids.is_required')
    def _compute_attribute_count(self):
        for record in self:
            record.attribute_count = len(record.attribute_ids)
            record.required_attribute_count = len(record.attribute_ids.filtered('is_required'))

    def action_load_attributes(self):
        """Carga los atributos de esta categoría desde MercadoLibre"""
        self.ensure_one()
        import requests

        url = f'https://api.mercadolibre.com/categories/{self.ml_category_id}/attributes'
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                raise UserError(_('Error obteniendo atributos: %s') % response.status_code)

            attributes_data = response.json()

            if not attributes_data:
                self.attributes_loaded = True
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sin Atributos'),
                        'message': _('Esta categoría no tiene atributos definidos.'),
                        'type': 'info',
                        'sticky': False,
                    }
                }

            AttributeModel = self.env['mercadolibre.category.attribute']
            created_count = 0
            updated_count = 0

            for attr_data in attributes_data:
                attr_id = attr_data.get('id')
                if not attr_id:
                    continue

                # Determinar si es requerido
                tags = attr_data.get('tags', {})
                is_required = tags.get('required', False) if isinstance(tags, dict) else False

                # Si tags es una lista, buscar 'required'
                if isinstance(tags, list):
                    is_required = 'required' in tags

                # Obtener valores
                values = attr_data.get('values', [])
                values_json = json.dumps(values) if values else ''

                vals = {
                    'name': attr_data.get('name', attr_id),
                    'value_type': attr_data.get('value_type', 'string'),
                    'is_required': is_required,
                    'is_allow_variations': attr_data.get('attribute_group_id') == 'VARIATIONS',
                    'hint': attr_data.get('hint', ''),
                    'tooltip': attr_data.get('tooltip', ''),
                    'values_json': values_json,
                }

                existing = AttributeModel.search([
                    ('category_id', '=', self.id),
                    ('ml_attribute_id', '=', attr_id)
                ], limit=1)

                if existing:
                    existing.write(vals)
                    updated_count += 1
                else:
                    vals.update({
                        'category_id': self.id,
                        'ml_attribute_id': attr_id,
                    })
                    AttributeModel.create(vals)
                    created_count += 1

            self.attributes_loaded = True

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Atributos Sincronizados'),
                    'message': _('Creados: %d, Actualizados: %d. Requeridos: %d') % (
                        created_count, updated_count, self.required_attribute_count
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error('Error cargando atributos de %s: %s', self.ml_category_id, str(e))
            raise UserError(_('Error cargando atributos: %s') % str(e))

    def get_required_attributes(self):
        """Retorna los atributos requeridos de esta categoría"""
        self.ensure_one()
        if not self.attributes_loaded:
            self.action_load_attributes()
        return self.attribute_ids.filtered('is_required')
