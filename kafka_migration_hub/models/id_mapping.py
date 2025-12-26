# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class MigrationIdMapping(models.Model):
    _name = 'migration.id.mapping'
    _description = 'Mapeo de IDs (Origen → Destino)'
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

    # Origen
    source_table = fields.Char(
        string='Tabla Origen',
        required=True,
        index=True,
    )
    source_id = fields.Char(
        string='ID Origen',
        required=True,
        index=True,
    )

    # Destino Odoo
    target_model = fields.Char(
        string='Modelo Odoo',
        required=True,
        index=True,
    )
    target_id = fields.Integer(
        string='ID Odoo',
        required=True,
        index=True,
    )

    # Referencia externa (para trazabilidad)
    external_ref = fields.Char(
        string='Referencia Externa',
        compute='_compute_external_ref',
        store=True,
    )

    _sql_constraints = [
        ('unique_source',
         'UNIQUE(project_id, source_table, source_id)',
         'Ya existe un mapeo para este registro origen'),
    ]

    @api.depends('source_table', 'source_id')
    def _compute_external_ref(self):
        for record in self:
            record.external_ref = f'{record.source_table}:{record.source_id}'

    @api.model
    def get_target_id(self, project_id, source_table, source_id):
        """Obtener ID de Odoo para un registro origen"""
        mapping = self.search([
            ('project_id', '=', project_id),
            ('source_table', '=', source_table),
            ('source_id', '=', str(source_id)),
        ], limit=1)

        if mapping:
            return mapping.target_id
        return None

    @api.model
    def create_mapping(self, project_id, source_table, source_id, target_model, target_id, table_mapping_id=None):
        """Crear mapeo de ID"""
        return self.create({
            'project_id': project_id,
            'table_mapping_id': table_mapping_id,
            'source_table': source_table,
            'source_id': str(source_id),
            'target_model': target_model,
            'target_id': target_id,
        })

    @api.model
    def bulk_create_mappings(self, mappings_data):
        """Crear múltiples mapeos de una vez (más eficiente)"""
        return self.create(mappings_data)

    @api.model
    def get_mappings_for_table(self, project_id, source_table):
        """Obtener todos los mapeos para una tabla"""
        mappings = self.search([
            ('project_id', '=', project_id),
            ('source_table', '=', source_table),
        ])

        return {m.source_id: m.target_id for m in mappings}

    @api.model
    def resolve_foreign_key(self, project_id, fk_table, fk_value):
        """Resolver FK: obtener ID de Odoo para una FK del origen"""
        if not fk_value:
            return None

        target_id = self.get_target_id(project_id, fk_table, fk_value)

        if not target_id:
            _logger.warning(
                f'FK no encontrada: {fk_table}:{fk_value} en proyecto {project_id}'
            )

        return target_id
