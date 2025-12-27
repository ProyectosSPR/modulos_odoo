# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class MigrationTableMapping(models.Model):
    _name = 'migration.table.mapping'
    _description = 'Mapeo de Tabla'
    _order = 'sequence, source_table'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
    )

    project_id = fields.Many2one(
        'migration.project',
        string='Proyecto',
        required=True,
        ondelete='cascade',
    )

    # Información de la tabla origen
    source_table = fields.Char(
        string='Tabla Origen',
        required=True,
    )
    source_schema = fields.Char(
        string='Schema Origen',
        default='public',
    )
    row_count = fields.Integer(
        string='Cantidad de Registros',
        default=0,
    )

    # Información de columnas (JSON)
    column_info = fields.Text(
        string='Información de Columnas',
        help='JSON con información de columnas de la tabla origen',
    )
    column_count = fields.Integer(
        string='Cantidad de Columnas',
        compute='_compute_column_count',
    )

    # Tópico asignado
    topic_id = fields.Many2one(
        'migration.topic',
        string='Tópico',
    )
    suggested_topic_id = fields.Many2one(
        'migration.topic',
        string='Tópico Sugerido (IA)',
    )

    # Modelo Odoo destino
    target_model_id = fields.Many2one(
        'ir.model',
        string='Modelo Odoo Destino',
        domain=[('transient', '=', False)],
    )
    target_model = fields.Char(
        related='target_model_id.model',
        string='Nombre Modelo',
        store=True,
    )
    suggested_model = fields.Char(
        string='Modelo Sugerido (IA)',
    )

    # Sugerencias de IA
    ai_confidence = fields.Float(
        string='Confianza IA (%)',
        default=0,
    )
    ai_reason = fields.Text(
        string='Razón de IA',
    )

    # Estado del mapeo
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('suggested', 'Con Sugerencia'),
        ('mapped', 'Mapeado'),
        ('ignored', 'Ignorado'),
        ('error', 'Error'),
    ], string='Estado', default='pending')

    # Mapeo de campos
    field_mapping_ids = fields.One2many(
        'migration.field.mapping',
        'table_mapping_id',
        string='Mapeo de Campos',
    )

    # Configuración de migración
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de migración',
    )
    batch_size = fields.Integer(
        string='Tamaño de Lote',
        default=100,
    )
    use_orm = fields.Boolean(
        string='Usar ORM',
        default=True,
        help='Usar ORM de Odoo o SQL directo',
    )

    # Progreso de migración
    migrated_records = fields.Integer(
        string='Registros Migrados',
        default=0,
    )
    error_records = fields.Integer(
        string='Registros con Error',
        default=0,
    )
    progress_percentage = fields.Float(
        string='Progreso %',
        compute='_compute_progress',
    )
    migration_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('running', 'En Ejecución'),
        ('completed', 'Completado'),
        ('error', 'Error'),
    ], string='Estado de Migración', default='pending')

    @api.depends('source_table', 'target_model')
    def _compute_name(self):
        for record in self:
            if record.source_table and record.target_model:
                record.name = f'{record.source_table} → {record.target_model}'
            elif record.source_table:
                record.name = record.source_table
            else:
                record.name = 'Nuevo Mapeo'

    @api.depends('column_info')
    def _compute_column_count(self):
        for record in self:
            if record.column_info:
                try:
                    columns = json.loads(record.column_info)
                    record.column_count = len(columns) if isinstance(columns, list) else 0
                except json.JSONDecodeError:
                    record.column_count = 0
            else:
                record.column_count = 0

    @api.depends('row_count', 'migrated_records')
    def _compute_progress(self):
        for record in self:
            if record.row_count > 0:
                record.progress_percentage = (record.migrated_records / record.row_count) * 100
            else:
                record.progress_percentage = 0

    def get_columns(self):
        """Obtener lista de columnas de la tabla"""
        self.ensure_one()
        if self.column_info:
            try:
                return json.loads(self.column_info)
            except json.JSONDecodeError:
                return []
        return []

    def set_columns(self, columns):
        """Establecer información de columnas"""
        self.ensure_one()
        self.column_info = json.dumps(columns)

    def action_accept_suggestion(self):
        """Aceptar la sugerencia de la IA"""
        self.ensure_one()
        if self.suggested_topic_id:
            self.topic_id = self.suggested_topic_id
        if self.suggested_model:
            model = self.env['ir.model'].search([('model', '=', self.suggested_model)], limit=1)
            if model:
                self.target_model_id = model
        self.state = 'mapped'
        self._generate_field_mappings()

    def action_ignore(self):
        """Marcar tabla como ignorada"""
        self.ensure_one()
        self.state = 'ignored'

    def action_reset(self):
        """Resetear mapeo"""
        self.ensure_one()
        self.state = 'pending'
        self.topic_id = False
        self.target_model_id = False
        self.field_mapping_ids.unlink()

    def _generate_field_mappings(self):
        """Generar mapeos de campos automáticamente"""
        self.ensure_one()
        if not self.target_model_id:
            return

        # Obtener columnas origen
        source_columns = self.get_columns()
        if not source_columns:
            return

        # Obtener campos del modelo destino
        target_fields = self.env['ir.model.fields'].search([
            ('model_id', '=', self.target_model_id.id),
            ('store', '=', True),
            ('name', 'not in', ['id', 'create_uid', 'create_date', 'write_uid', 'write_date']),
        ])

        # Crear mapeo de campos usando IA o heurísticas
        field_mapping_model = self.env['migration.field.mapping']

        for col in source_columns:
            col_name = col.get('name', '').lower()
            col_type = col.get('type', '').lower()

            # Buscar campo destino similar
            best_match = None
            best_score = 0

            for field in target_fields:
                score = self._calculate_field_similarity(col_name, field.name)
                if score > best_score:
                    best_score = score
                    best_match = field

            field_mapping_model.create({
                'table_mapping_id': self.id,
                'source_column': col.get('name'),
                'source_type': col.get('type'),
                'source_nullable': col.get('nullable', True),
                'target_field_id': best_match.id if best_match and best_score > 0.5 else False,
                'ai_confidence': best_score * 100 if best_match else 0,
                'state': 'mapped' if best_match and best_score > 0.5 else 'pending',
            })

    def _calculate_field_similarity(self, source_name, target_name):
        """Calcular similitud entre nombres de campos"""
        source_name = source_name.lower().replace('_', '')
        target_name = target_name.lower().replace('_', '')

        # Coincidencia exacta
        if source_name == target_name:
            return 1.0

        # Mapeos comunes conocidos
        common_mappings = {
            'customerid': 'partnerid',
            'customername': 'name',
            'clientname': 'name',
            'clientid': 'partnerid',
            'taxid': 'vat',
            'taxnumber': 'vat',
            'rfc': 'vat',
            'phonenumber': 'phone',
            'telephone': 'phone',
            'emailaddress': 'email',
            'mail': 'email',
            'address': 'street',
            'addressline1': 'street',
            'addressline2': 'street2',
            'zipcode': 'zip',
            'postalcode': 'zip',
            'countrycode': 'countryid',
            'statecode': 'stateid',
            'isactive': 'active',
            'enabled': 'active',
            'createdat': 'createdate',
            'updatedat': 'writedate',
            'modifiedat': 'writedate',
        }

        if source_name in common_mappings:
            if common_mappings[source_name] == target_name:
                return 0.9

        # Similitud parcial
        if source_name in target_name or target_name in source_name:
            return 0.7

        return 0.0

    def get_portal_data(self):
        """Obtener datos para el portal"""
        self.ensure_one()
        return {
            'id': self.id,
            'source_table': self.source_table,
            'source_schema': self.source_schema,
            'row_count': self.row_count,
            'column_count': self.column_count,
            'columns': self.get_columns(),
            'topic': {
                'id': self.topic_id.id,
                'name': self.topic_id.name,
                'icon': self.topic_id.icon,
            } if self.topic_id else None,
            'suggested_topic': {
                'id': self.suggested_topic_id.id,
                'name': self.suggested_topic_id.name,
                'icon': self.suggested_topic_id.icon,
            } if self.suggested_topic_id else None,
            'target_model': self.target_model,
            'suggested_model': self.suggested_model,
            'ai_confidence': self.ai_confidence,
            'ai_reason': self.ai_reason,
            'state': self.state,
            'progress': self.progress_percentage,
            'migrated': self.migrated_records,
            'errors': self.error_records,
        }
