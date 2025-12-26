# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class OdooConnection(models.Model):
    """Conexión a una instancia Odoo para comparación/migración"""
    _name = 'migration.odoo.connection'
    _description = 'Conexión Odoo para Migración'
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de la conexión (ej: "Odoo 16 Producción")',
    )
    url = fields.Char(
        string='URL',
        required=True,
        help='URL de la instancia Odoo (ej: https://mi-odoo.com)',
    )
    database = fields.Char(
        string='Base de Datos',
        required=True,
    )
    username = fields.Char(
        string='Usuario',
        required=True,
    )
    password = fields.Char(
        string='Contraseña',
        required=True,
    )

    # Estado de conexión
    state = fields.Selection([
        ('draft', 'Sin probar'),
        ('connected', 'Conectado'),
        ('error', 'Error'),
    ], string='Estado', default='draft')

    # Información de la instancia
    odoo_version = fields.Char(
        string='Versión Odoo',
        readonly=True,
    )
    last_check = fields.Datetime(
        string='Última Verificación',
        readonly=True,
    )
    error_message = fields.Text(
        string='Mensaje de Error',
        readonly=True,
    )

    # Tipo de conexión
    connection_type = fields.Selection([
        ('source', 'Origen (migrar desde)'),
        ('target', 'Destino (migrar hacia)'),
        ('both', 'Ambos'),
    ], string='Tipo', default='source')

    # Compañía
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )

    # Estadísticas
    model_count = fields.Integer(
        string='Modelos Encontrados',
        readonly=True,
    )

    _sql_constraints = [
        ('unique_connection', 'unique(url, database, company_id)',
         'Ya existe una conexión a esta instancia y base de datos'),
    ]

    def action_test_connection(self):
        """Probar la conexión a la instancia Odoo"""
        self.ensure_one()

        Comparator = self.env['migration.odoo.comparator']
        result = Comparator.connect_to_odoo(
            self.url,
            self.database,
            self.username,
            self.password
        )

        if result.get('success'):
            # Obtener cantidad de modelos
            models = Comparator.get_remote_models({
                **result,
                'password': self.password,
            })

            self.write({
                'state': 'connected',
                'odoo_version': result.get('version', 'Unknown'),
                'last_check': fields.Datetime.now(),
                'error_message': False,
                'model_count': len(models),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexión Exitosa'),
                    'message': _('Odoo %s - %d modelos encontrados') % (
                        result.get('version'), len(models)
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            self.write({
                'state': 'error',
                'last_check': fields.Datetime.now(),
                'error_message': result.get('error'),
            })

            raise UserError(result.get('error'))

    def get_connection_data(self):
        """Obtener datos de conexión para usar en comparador"""
        self.ensure_one()

        if self.state != 'connected':
            raise UserError(_('Primero pruebe la conexión'))

        Comparator = self.env['migration.odoo.comparator']
        result = Comparator.connect_to_odoo(
            self.url,
            self.database,
            self.username,
            self.password
        )

        if result.get('success'):
            result['password'] = self.password
            return result

        raise UserError(result.get('error', _('Error de conexión')))

    def action_view_models(self):
        """Ver modelos de la instancia remota"""
        self.ensure_one()

        if self.state != 'connected':
            raise UserError(_('Primero pruebe la conexión'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Modelos de %s') % self.name,
            'res_model': 'migration.odoo.remote.model',
            'view_mode': 'tree',
            'domain': [('connection_id', '=', self.id)],
            'context': {'default_connection_id': self.id},
        }


class OdooRemoteModel(models.TransientModel):
    """Modelo temporal para mostrar modelos remotos"""
    _name = 'migration.odoo.remote.model'
    _description = 'Modelo Remoto de Odoo'

    connection_id = fields.Many2one(
        'migration.odoo.connection',
        string='Conexión',
        required=True,
    )
    model_name = fields.Char(string='Nombre Técnico')
    model_description = fields.Char(string='Descripción')
    field_count = fields.Integer(string='Campos')


class OdooComparison(models.Model):
    """Comparación entre dos instancias Odoo"""
    _name = 'migration.odoo.comparison'
    _description = 'Comparación de Instancias Odoo'
    _order = 'create_date desc'

    name = fields.Char(
        string='Nombre',
        required=True,
        default=lambda self: _('Comparación %s') % fields.Datetime.now(),
    )

    source_connection_id = fields.Many2one(
        'migration.odoo.connection',
        string='Conexión Origen',
        required=True,
        domain=[('state', '=', 'connected')],
    )
    target_connection_id = fields.Many2one(
        'migration.odoo.connection',
        string='Conexión Destino',
        domain=[('state', '=', 'connected')],
        help='Dejar vacío para comparar con instancia local',
    )

    compare_with_local = fields.Boolean(
        string='Comparar con Instancia Local',
        default=True,
        help='Si está activo, compara con esta instancia de Odoo',
    )

    # Modelos a comparar
    model_filter = fields.Char(
        string='Filtro de Modelos',
        help='Filtrar por nombre (ej: "res." para modelos de recursos)',
    )
    model_ids = fields.Many2many(
        'migration.comparison.model',
        'comparison_model_rel',
        'comparison_id',
        'model_id',
        string='Modelos Seleccionados',
    )

    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('comparing', 'Comparando'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], string='Estado', default='draft')

    # Resultados
    result_ids = fields.One2many(
        'migration.comparison.result',
        'comparison_id',
        string='Resultados',
    )

    # Resumen
    total_models = fields.Integer(string='Total Modelos', compute='_compute_summary')
    compatible_models = fields.Integer(string='Modelos Compatibles', compute='_compute_summary')
    models_with_changes = fields.Integer(string='Modelos con Cambios', compute='_compute_summary')
    complexity_score = fields.Float(string='Score Complejidad', compute='_compute_summary')
    complexity_level = fields.Selection([
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
        ('critical', 'Crítica'),
    ], string='Complejidad', compute='_compute_summary')

    @api.depends('result_ids', 'result_ids.status')
    def _compute_summary(self):
        for record in self:
            results = record.result_ids
            record.total_models = len(results)
            record.compatible_models = len(results.filtered(lambda r: r.breaking_changes == 0))
            record.models_with_changes = len(results.filtered(lambda r: r.total_changes > 0))

            # Calcular complejidad
            if results:
                total_breaking = sum(r.breaking_changes for r in results)
                total_fields = sum(r.source_field_count for r in results) or 1
                score = (total_breaking / total_fields) * 100
                record.complexity_score = min(score, 100)

                if score < 20:
                    record.complexity_level = 'low'
                elif score < 50:
                    record.complexity_level = 'medium'
                elif score < 80:
                    record.complexity_level = 'high'
                else:
                    record.complexity_level = 'critical'
            else:
                record.complexity_score = 0
                record.complexity_level = 'low'

    def action_load_models(self):
        """Cargar modelos disponibles desde origen"""
        self.ensure_one()

        if not self.source_connection_id:
            raise UserError(_('Seleccione una conexión origen'))

        connection = self.source_connection_id.get_connection_data()
        Comparator = self.env['migration.odoo.comparator']

        models = Comparator.get_remote_models(connection, self.model_filter)

        # Crear registros de modelos
        ComparisonModel = self.env['migration.comparison.model']
        existing = ComparisonModel.search([]).mapped('model_name')

        for model in models:
            if model['model'] not in existing:
                ComparisonModel.create({
                    'model_name': model['model'],
                    'model_description': model['name'],
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Modelos Cargados'),
                'message': _('%d modelos encontrados') % len(models),
                'type': 'success',
            }
        }

    def action_run_comparison(self):
        """Ejecutar comparación de modelos"""
        self.ensure_one()

        if not self.model_ids:
            raise UserError(_('Seleccione al menos un modelo para comparar'))

        self.state = 'comparing'
        self.result_ids.unlink()

        try:
            source_conn = self.source_connection_id.get_connection_data()

            Comparator = self.env['migration.odoo.comparator']

            for model in self.model_ids:
                if self.compare_with_local:
                    result = Comparator.compare_with_local(source_conn, model.model_name)
                else:
                    target_conn = self.target_connection_id.get_connection_data()
                    result = Comparator.compare_models(source_conn, target_conn, model.model_name)

                # Crear resultado
                self.env['migration.comparison.result'].create({
                    'comparison_id': self.id,
                    'model_name': model.model_name,
                    'status': result.get('status', 'error'),
                    'source_field_count': result.get('summary', {}).get('total_source', 0),
                    'target_field_count': result.get('summary', {}).get('total_target', 0),
                    'compatible_fields': result.get('summary', {}).get('compatible', 0),
                    'modified_fields': result.get('summary', {}).get('modified', 0),
                    'added_fields': result.get('summary', {}).get('added', 0),
                    'removed_fields': result.get('summary', {}).get('removed', 0),
                    'breaking_changes': result.get('summary', {}).get('breaking_changes', 0),
                    'result_data': str(result),
                })

            self.state = 'done'

        except Exception as e:
            self.state = 'error'
            raise UserError(str(e))

        return True

    def action_generate_mappings(self):
        """Generar mapeos basados en comparación"""
        self.ensure_one()

        if self.state != 'done':
            raise UserError(_('Primero ejecute la comparación'))

        # TODO: Implementar generación de mapeos para el designer visual
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Mapeos Generados'),
                'message': _('Los mapeos han sido generados'),
                'type': 'success',
            }
        }


class ComparisonModel(models.Model):
    """Modelo para selección en comparaciones"""
    _name = 'migration.comparison.model'
    _description = 'Modelo para Comparación'
    _order = 'model_name'

    model_name = fields.Char(string='Nombre Técnico', required=True)
    model_description = fields.Char(string='Descripción')

    _sql_constraints = [
        ('unique_model', 'unique(model_name)', 'El modelo ya existe'),
    ]


class ComparisonResult(models.Model):
    """Resultado de comparación de un modelo"""
    _name = 'migration.comparison.result'
    _description = 'Resultado de Comparación'
    _order = 'breaking_changes desc, model_name'

    comparison_id = fields.Many2one(
        'migration.odoo.comparison',
        string='Comparación',
        required=True,
        ondelete='cascade',
    )
    model_name = fields.Char(string='Modelo', required=True)
    status = fields.Selection([
        ('compared', 'Comparado'),
        ('source_only', 'Solo en Origen'),
        ('target_only', 'Solo en Destino'),
        ('local_not_found', 'No encontrado Local'),
        ('remote_not_found', 'No encontrado Remoto'),
        ('error', 'Error'),
    ], string='Estado')

    source_field_count = fields.Integer(string='Campos Origen')
    target_field_count = fields.Integer(string='Campos Destino')
    compatible_fields = fields.Integer(string='Compatibles')
    modified_fields = fields.Integer(string='Modificados')
    added_fields = fields.Integer(string='Nuevos')
    removed_fields = fields.Integer(string='Eliminados')
    breaking_changes = fields.Integer(string='Cambios Breaking')

    total_changes = fields.Integer(
        string='Total Cambios',
        compute='_compute_total_changes',
        store=True,
    )

    result_data = fields.Text(string='Datos Completos')

    compatibility_percent = fields.Float(
        string='% Compatibilidad',
        compute='_compute_compatibility',
    )

    @api.depends('modified_fields', 'added_fields', 'removed_fields')
    def _compute_total_changes(self):
        for record in self:
            record.total_changes = (
                record.modified_fields +
                record.added_fields +
                record.removed_fields
            )

    @api.depends('compatible_fields', 'source_field_count')
    def _compute_compatibility(self):
        for record in self:
            if record.source_field_count > 0:
                record.compatibility_percent = (
                    record.compatible_fields / record.source_field_count * 100
                )
            else:
                record.compatibility_percent = 0
