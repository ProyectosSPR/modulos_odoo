# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class MigrationFieldMapping(models.Model):
    _name = 'migration.field.mapping'
    _description = 'Mapeo de Campo'
    _order = 'sequence, source_column'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
    )

    table_mapping_id = fields.Many2one(
        'migration.table.mapping',
        string='Mapeo de Tabla',
        required=True,
        ondelete='cascade',
    )
    project_id = fields.Many2one(
        related='table_mapping_id.project_id',
        string='Proyecto',
        store=True,
    )

    # Campo origen
    source_column = fields.Char(
        string='Columna Origen',
        required=True,
    )
    source_type = fields.Char(
        string='Tipo Origen',
    )
    source_nullable = fields.Boolean(
        string='Nullable',
        default=True,
    )
    source_is_pk = fields.Boolean(
        string='Es PK',
        default=False,
    )
    source_is_fk = fields.Boolean(
        string='Es FK',
        default=False,
    )
    source_fk_table = fields.Char(
        string='Tabla FK',
        help='Tabla a la que referencia el FK',
    )

    # Campo destino Odoo
    target_field_id = fields.Many2one(
        'ir.model.fields',
        string='Campo Odoo Destino',
        domain="[('model_id', '=', parent.target_model_id)]",
    )
    target_field_name = fields.Char(
        related='target_field_id.name',
        string='Nombre Campo',
        store=True,
    )
    target_field_type = fields.Selection(
        related='target_field_id.ttype',
        string='Tipo Campo',
        store=True,
    )
    target_relation = fields.Char(
        related='target_field_id.relation',
        string='Relación',
    )

    # Tipo de mapeo
    mapping_type = fields.Selection([
        ('direct', 'Directo'),
        ('transform', 'Transformación'),
        ('lookup', 'Lookup (Buscar ID)'),
        ('constant', 'Valor Constante'),
        ('expression', 'Expresión Python'),
        ('ignore', 'Ignorar'),
    ], string='Tipo de Mapeo', default='direct')

    # Configuración de transformación
    transform_function = fields.Selection([
        ('none', 'Ninguna'),
        ('uppercase', 'Mayúsculas'),
        ('lowercase', 'Minúsculas'),
        ('trim', 'Quitar Espacios'),
        ('strip_html', 'Quitar HTML'),
        ('to_date', 'Convertir a Fecha'),
        ('to_datetime', 'Convertir a DateTime'),
        ('to_float', 'Convertir a Float'),
        ('to_int', 'Convertir a Integer'),
        ('to_boolean', 'Convertir a Boolean'),
        ('add_prefix', 'Agregar Prefijo'),
        ('add_suffix', 'Agregar Sufijo'),
        ('replace', 'Reemplazar Texto'),
        ('custom', 'Personalizado'),
    ], string='Función de Transformación', default='none')

    transform_params = fields.Text(
        string='Parámetros de Transformación',
        help='JSON con parámetros para la transformación',
    )

    # Para lookup
    lookup_model = fields.Char(
        string='Modelo para Lookup',
        help='Modelo donde buscar el ID (ej: res.country)',
    )
    lookup_field = fields.Char(
        string='Campo de Búsqueda',
        help='Campo por el cual buscar (ej: code)',
    )
    lookup_create_if_not_found = fields.Boolean(
        string='Crear si no existe',
        default=False,
    )

    # Para valor constante
    constant_value = fields.Char(
        string='Valor Constante',
    )

    # Para expresión Python
    python_expression = fields.Text(
        string='Expresión Python',
        help='Expresión Python que retorna el valor. Variables disponibles: value, record, env',
    )

    # Valor por defecto
    default_value = fields.Char(
        string='Valor por Defecto',
        help='Valor a usar si el origen es nulo',
    )

    # Sugerencias IA
    ai_confidence = fields.Float(
        string='Confianza IA (%)',
        default=0,
    )
    ai_suggestion = fields.Text(
        string='Sugerencia IA',
    )

    # Estado
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('mapped', 'Mapeado'),
        ('ignored', 'Ignorado'),
        ('error', 'Error'),
    ], string='Estado', default='pending')

    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )

    @api.depends('source_column', 'target_field_name')
    def _compute_name(self):
        for record in self:
            if record.source_column and record.target_field_name:
                record.name = f'{record.source_column} → {record.target_field_name}'
            elif record.source_column:
                record.name = record.source_column
            else:
                record.name = 'Nuevo Mapeo'

    def transform_value(self, value, record_data=None):
        """Aplicar transformación al valor"""
        self.ensure_one()

        # Si es nulo y hay default
        if value is None and self.default_value:
            value = self.default_value

        if value is None:
            return None

        # Aplicar tipo de mapeo
        if self.mapping_type == 'ignore':
            return None

        if self.mapping_type == 'constant':
            return self.constant_value

        if self.mapping_type == 'expression':
            return self._evaluate_expression(value, record_data)

        if self.mapping_type == 'lookup':
            return self._do_lookup(value)

        # Aplicar función de transformación
        if self.transform_function and self.transform_function != 'none':
            value = self._apply_transform(value)

        return value

    def _apply_transform(self, value):
        """Aplicar función de transformación"""
        if not value:
            return value

        func = self.transform_function
        params = {}
        if self.transform_params:
            try:
                params = json.loads(self.transform_params)
            except json.JSONDecodeError:
                pass

        if func == 'uppercase':
            return str(value).upper()
        elif func == 'lowercase':
            return str(value).lower()
        elif func == 'trim':
            return str(value).strip()
        elif func == 'strip_html':
            import re
            return re.sub(r'<[^>]+>', '', str(value))
        elif func == 'to_date':
            from datetime import datetime
            fmt = params.get('format', '%Y-%m-%d')
            if isinstance(value, str):
                return datetime.strptime(value, fmt).date()
            return value
        elif func == 'to_datetime':
            from datetime import datetime
            fmt = params.get('format', '%Y-%m-%d %H:%M:%S')
            if isinstance(value, str):
                return datetime.strptime(value, fmt)
            return value
        elif func == 'to_float':
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        elif func == 'to_int':
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return 0
        elif func == 'to_boolean':
            if isinstance(value, bool):
                return value
            return str(value).lower() in ('true', '1', 'yes', 'si', 't')
        elif func == 'add_prefix':
            prefix = params.get('prefix', '')
            return f'{prefix}{value}'
        elif func == 'add_suffix':
            suffix = params.get('suffix', '')
            return f'{value}{suffix}'
        elif func == 'replace':
            old = params.get('old', '')
            new = params.get('new', '')
            return str(value).replace(old, new)
        elif func == 'custom':
            # Usar expresión personalizada
            expression = params.get('expression', 'value')
            return eval(expression, {'value': value})

        return value

    def _do_lookup(self, value):
        """Realizar lookup para obtener ID"""
        if not self.lookup_model or not self.lookup_field:
            return None

        try:
            model = self.env[self.lookup_model]
            record = model.search([(self.lookup_field, '=', value)], limit=1)

            if record:
                return record.id

            if self.lookup_create_if_not_found:
                # Crear el registro si no existe
                new_record = model.create({
                    self.lookup_field: value,
                })
                return new_record.id

            return None

        except Exception as e:
            _logger.error(f'Error en lookup {self.lookup_model}.{self.lookup_field}: {str(e)}')
            return None

    def _evaluate_expression(self, value, record_data):
        """Evaluar expresión Python"""
        try:
            # Contexto seguro para eval
            context = {
                'value': value,
                'record': record_data or {},
                'env': self.env,
                'datetime': __import__('datetime'),
                'json': __import__('json'),
            }
            return eval(self.python_expression, {"__builtins__": {}}, context)
        except Exception as e:
            _logger.error(f'Error evaluando expresión: {str(e)}')
            return None

    def action_set_ignore(self):
        """Marcar campo como ignorado"""
        self.ensure_one()
        self.mapping_type = 'ignore'
        self.state = 'ignored'

    def action_reset(self):
        """Resetear mapeo del campo"""
        self.ensure_one()
        self.write({
            'target_field_id': False,
            'mapping_type': 'direct',
            'transform_function': 'none',
            'state': 'pending',
        })

    def get_portal_data(self):
        """Obtener datos para el portal"""
        self.ensure_one()
        return {
            'id': self.id,
            'source_column': self.source_column,
            'source_type': self.source_type,
            'source_nullable': self.source_nullable,
            'source_is_pk': self.source_is_pk,
            'source_is_fk': self.source_is_fk,
            'source_fk_table': self.source_fk_table,
            'target_field': self.target_field_name,
            'target_type': self.target_field_type,
            'target_relation': self.target_relation,
            'mapping_type': self.mapping_type,
            'transform_function': self.transform_function,
            'ai_confidence': self.ai_confidence,
            'state': self.state,
        }
