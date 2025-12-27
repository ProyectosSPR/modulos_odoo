# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class MigrationError(models.Model):
    _name = 'migration.error'
    _description = 'Error de Migración (Dead Letter Queue)'
    _order = 'create_date desc'

    project_id = fields.Many2one(
        'migration.project',
        string='Proyecto',
        required=True,
        ondelete='cascade',
        index=True,
    )

    table_mapping_id = fields.Many2one(
        'migration.table.mapping',
        string='Mapeo de Tabla',
        index=True,
    )

    # Información del registro con error
    source_table = fields.Char(
        string='Tabla Origen',
        required=True,
    )
    source_record_id = fields.Char(
        string='ID Origen',
    )
    source_data = fields.Text(
        string='Datos Origen (JSON)',
        help='Datos originales del registro',
    )

    # Información del error
    error_type = fields.Selection([
        ('connection', 'Error de Conexión'),
        ('validation', 'Error de Validación'),
        ('constraint', 'Violación de Constraint'),
        ('transform', 'Error de Transformación'),
        ('lookup', 'Error de Lookup'),
        ('duplicate', 'Registro Duplicado'),
        ('missing_dependency', 'Dependencia Faltante'),
        ('unknown', 'Error Desconocido'),
    ], string='Tipo de Error', default='unknown')

    error_message = fields.Text(
        string='Mensaje de Error',
        required=True,
    )
    error_traceback = fields.Text(
        string='Traceback',
    )

    # Estado
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('retrying', 'Reintentando'),
        ('resolved', 'Resuelto'),
        ('ignored', 'Ignorado'),
    ], string='Estado', default='pending', index=True)

    # Reintentos
    retry_count = fields.Integer(
        string='Intentos',
        default=0,
    )
    max_retries = fields.Integer(
        string='Máximo Intentos',
        default=3,
    )
    last_retry_date = fields.Datetime(
        string='Último Intento',
    )

    # Resolución
    resolution_notes = fields.Text(
        string='Notas de Resolución',
    )
    resolved_by = fields.Many2one(
        'res.users',
        string='Resuelto por',
    )
    resolved_date = fields.Datetime(
        string='Fecha Resolución',
    )

    def get_source_data_dict(self):
        """Obtener datos origen como diccionario"""
        self.ensure_one()
        if self.source_data:
            try:
                return json.loads(self.source_data)
            except json.JSONDecodeError:
                return {}
        return {}

    def action_retry(self):
        """Reintentar migración del registro"""
        self.ensure_one()

        if self.retry_count >= self.max_retries:
            raise UserError(_('Se alcanzó el máximo de reintentos (%d)') % self.max_retries)

        self.state = 'retrying'
        self.retry_count += 1
        self.last_retry_date = fields.Datetime.now()

        try:
            # Obtener el servicio de migración
            transformer = self.env['migration.data.transformer']
            source_data = self.get_source_data_dict()

            # Reintentar transformación e inserción
            result = transformer.transform_and_insert(
                self.table_mapping_id,
                source_data,
            )

            if result.get('success'):
                self.state = 'resolved'
                self.resolved_date = fields.Datetime.now()
                self.resolution_notes = 'Resuelto automáticamente por reintento'
                return True
            else:
                self.error_message = result.get('error', 'Error desconocido')
                self.state = 'pending'
                return False

        except Exception as e:
            self.error_message = str(e)
            self.state = 'pending'
            _logger.error(f'Error en reintento: {str(e)}')
            return False

    def action_ignore(self):
        """Marcar error como ignorado"""
        self.ensure_one()
        self.state = 'ignored'
        self.resolution_notes = 'Ignorado por el usuario'

    def action_mark_resolved(self):
        """Marcar como resuelto manualmente"""
        self.ensure_one()
        self.state = 'resolved'
        self.resolved_by = self.env.user
        self.resolved_date = fields.Datetime.now()

    def get_portal_data(self):
        """Obtener datos para el portal"""
        self.ensure_one()
        return {
            'id': self.id,
            'source_table': self.source_table,
            'source_record_id': self.source_record_id,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'state': self.state,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'create_date': self.create_date.isoformat() if self.create_date else None,
        }

    @api.model
    def get_pending_count(self, project_id):
        """Obtener cantidad de errores pendientes"""
        return self.search_count([
            ('project_id', '=', project_id),
            ('state', '=', 'pending'),
        ])
