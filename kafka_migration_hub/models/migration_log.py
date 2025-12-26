# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class MigrationLog(models.Model):
    _name = 'migration.log'
    _description = 'Log de Migración'
    _order = 'create_date desc'

    project_id = fields.Many2one(
        'migration.project',
        string='Proyecto',
        required=True,
        ondelete='cascade',
        index=True,
    )

    level = fields.Selection([
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ], string='Nivel', default='info', index=True)

    message = fields.Text(
        string='Mensaje',
        required=True,
    )

    # Contexto adicional
    table_mapping_id = fields.Many2one(
        'migration.table.mapping',
        string='Tabla',
    )
    source_table = fields.Char(
        string='Tabla Origen',
    )
    record_id = fields.Char(
        string='ID Registro',
    )

    # Datos adicionales (JSON)
    extra_data = fields.Text(
        string='Datos Extra',
    )

    # Timestamps
    timestamp = fields.Datetime(
        string='Timestamp',
        default=fields.Datetime.now,
        index=True,
    )

    @api.model
    def log(self, project_id, level, message, **kwargs):
        """Método helper para crear logs"""
        return self.create({
            'project_id': project_id,
            'level': level,
            'message': message,
            'table_mapping_id': kwargs.get('table_mapping_id'),
            'source_table': kwargs.get('source_table'),
            'record_id': kwargs.get('record_id'),
            'extra_data': kwargs.get('extra_data'),
        })

    @api.model
    def cleanup_old_logs(self, days=30):
        """Limpiar logs antiguos"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff_date)])
        count = len(old_logs)
        old_logs.unlink()
        return count
