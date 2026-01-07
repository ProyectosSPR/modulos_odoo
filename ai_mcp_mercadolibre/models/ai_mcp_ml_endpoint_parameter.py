# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AiMcpMlEndpointParameter(models.Model):
    _name = 'ai.mcp.ml.endpoint.parameter'
    _description = 'Parametro de Endpoint MCP MercadoLibre'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre del parametro (ej: order_id, status, limit)',
    )
    endpoint_id = fields.Many2one(
        'ai.mcp.ml.endpoint',
        string='Endpoint',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )

    # Tipo de parametro
    param_type = fields.Selection([
        ('string', 'Texto'),
        ('integer', 'Numero Entero'),
        ('number', 'Numero Decimal'),
        ('boolean', 'Booleano'),
        ('array', 'Lista'),
        ('object', 'Objeto'),
    ], string='Tipo', required=True, default='string')

    # Configuracion
    required = fields.Boolean(
        string='Requerido',
        default=False,
        help='Indica si el parametro es obligatorio',
    )
    is_path_param = fields.Boolean(
        string='Es Parametro de Ruta',
        default=False,
        help='Si es True, el parametro se reemplaza en la URL (ej: /orders/{order_id})',
    )
    description = fields.Text(
        string='Descripcion',
        help='Descripcion del parametro para la IA',
    )
    default_value = fields.Char(
        string='Valor por Defecto',
        help='Valor a usar si no se proporciona',
    )
    enum_values = fields.Text(
        string='Valores Permitidos',
        help='Lista JSON de valores permitidos (ej: ["paid", "shipped", "delivered"])',
    )

    # Dependencia de otro endpoint
    from_dependency = fields.Boolean(
        string='Viene de Dependencia',
        default=False,
        help='Este parametro se obtiene del endpoint dependencia',
    )
    dependency_path = fields.Char(
        string='Ruta en Dependencia',
        help='Ruta del campo en la respuesta de la dependencia (ej: shipping.id, results[0].id)',
    )

    # Validacion
    min_value = fields.Float(
        string='Valor Minimo',
        help='Para tipos numericos',
    )
    max_value = fields.Float(
        string='Valor Maximo',
        help='Para tipos numericos',
    )
    pattern = fields.Char(
        string='Patron Regex',
        help='Expresion regular para validar el valor (solo para string)',
    )

    @api.constrains('enum_values')
    def _check_enum_values(self):
        """Validar que enum_values sea JSON valido."""
        for record in self:
            if record.enum_values:
                try:
                    values = json.loads(record.enum_values)
                    if not isinstance(values, list):
                        raise ValidationError(_('Los valores permitidos deben ser una lista JSON'))
                except json.JSONDecodeError:
                    raise ValidationError(_('Los valores permitidos deben ser JSON valido'))

    @api.onchange('is_path_param')
    def _onchange_is_path_param(self):
        """Si es parametro de ruta, es requerido."""
        if self.is_path_param:
            self.required = True

    @api.onchange('from_dependency')
    def _onchange_from_dependency(self):
        """Si viene de dependencia, no es requerido por el usuario."""
        if self.from_dependency:
            self.required = False

    def get_schema(self):
        """Obtener schema JSON del parametro para MCP."""
        self.ensure_one()
        schema = {
            'type': self.param_type,
        }

        if self.description:
            desc = self.description
            if self.from_dependency and self.dependency_path:
                desc += f" (Obtener de: {self.endpoint_id.depends_on_id.code} -> {self.dependency_path})"
            schema['description'] = desc

        if self.default_value:
            # Convertir al tipo correcto
            if self.param_type == 'integer':
                schema['default'] = int(self.default_value)
            elif self.param_type == 'number':
                schema['default'] = float(self.default_value)
            elif self.param_type == 'boolean':
                schema['default'] = self.default_value.lower() in ('true', '1', 'yes')
            else:
                schema['default'] = self.default_value

        if self.enum_values:
            try:
                schema['enum'] = json.loads(self.enum_values)
            except json.JSONDecodeError:
                pass

        if self.param_type in ('integer', 'number'):
            if self.min_value:
                schema['minimum'] = self.min_value
            if self.max_value:
                schema['maximum'] = self.max_value

        if self.param_type == 'string' and self.pattern:
            schema['pattern'] = self.pattern

        return schema
