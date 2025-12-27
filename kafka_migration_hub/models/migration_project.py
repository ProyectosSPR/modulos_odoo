# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MigrationProject(models.Model):
    _name = 'migration.project'
    _description = 'Proyecto de Migración'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Nombre del Proyecto',
        required=True,
        tracking=True,
    )
    description = fields.Text(string='Descripción')

    # Usuario portal propietario
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        default=lambda self: self.env.user.partner_id,
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario Responsable',
        default=lambda self: self.env.user,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )

    # Conexión origen
    source_connection_id = fields.Many2one(
        'migration.source.connection',
        string='Conexión Origen',
        ondelete='restrict',
    )
    source_type = fields.Selection(
        related='source_connection_id.db_type',
        string='Tipo de Origen',
        store=True,
    )

    # Estado del proyecto
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('connecting', 'Conectando'),
        ('analyzing', 'Analizando Esquema'),
        ('mapping', 'Configurando Mapeo'),
        ('ready', 'Listo para Migrar'),
        ('running', 'En Ejecución'),
        ('paused', 'Pausado'),
        ('completed', 'Completado'),
        ('error', 'Error'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True)

    # Paso actual del wizard
    wizard_step = fields.Selection([
        ('1_connection', '1. Conexión'),
        ('2_schema', '2. Análisis de Esquema'),
        ('3_topics', '3. Asignación de Tópicos'),
        ('4_fields', '4. Mapeo de Campos'),
        ('5_review', '5. Revisión y Ejecución'),
    ], string='Paso del Wizard', default='1_connection')

    # Mapeos
    table_mapping_ids = fields.One2many(
        'migration.table.mapping',
        'project_id',
        string='Mapeo de Tablas',
    )

    # Logs y errores
    log_ids = fields.One2many(
        'migration.log',
        'project_id',
        string='Logs',
    )
    error_ids = fields.One2many(
        'migration.error',
        'project_id',
        string='Errores',
    )

    # Estadísticas
    total_source_tables = fields.Integer(
        string='Tablas Origen',
        compute='_compute_statistics',
        store=True,
    )
    total_mapped_tables = fields.Integer(
        string='Tablas Mapeadas',
        compute='_compute_statistics',
        store=True,
    )
    total_source_records = fields.Integer(
        string='Registros Origen',
        default=0,
    )
    total_migrated_records = fields.Integer(
        string='Registros Migrados',
        default=0,
    )
    total_error_records = fields.Integer(
        string='Registros con Error',
        compute='_compute_error_count',
    )
    progress_percentage = fields.Float(
        string='Progreso %',
        compute='_compute_progress',
    )

    # Configuración Kafka
    kafka_topic_prefix = fields.Char(
        string='Prefijo Topics Kafka',
        compute='_compute_kafka_prefix',
        store=True,
    )
    use_kafka = fields.Boolean(
        string='Usar Kafka (Tiempo Real)',
        default=True,
    )

    # Fechas
    started_at = fields.Datetime(string='Iniciado')
    completed_at = fields.Datetime(string='Completado')

    # IA
    ai_suggestions_enabled = fields.Boolean(
        string='Sugerencias IA Habilitadas',
        default=True,
    )
    ai_confidence_threshold = fields.Integer(
        string='Umbral de Confianza IA (%)',
        default=80,
        help='Solo mostrar sugerencias con confianza mayor a este porcentaje',
    )

    # Configuracion de procesamiento
    batch_size = fields.Integer(
        string='Tamano de Lote',
        default=100,
        help='Cantidad de registros a procesar por lote',
    )
    max_retries = fields.Integer(
        string='Reintentos Maximos',
        default=3,
        help='Numero maximo de reintentos para registros con error',
    )
    retry_delay = fields.Integer(
        string='Delay entre Reintentos (seg)',
        default=30,
    )
    parallel_workers = fields.Integer(
        string='Workers Paralelos',
        default=4,
        help='Numero de procesos paralelos para la migracion',
    )

    @api.depends('name', 'partner_id')
    def _compute_kafka_prefix(self):
        for record in self:
            if record.name and record.partner_id:
                # Crear prefijo único para topics de Kafka
                safe_name = ''.join(c if c.isalnum() else '_' for c in record.name.lower())
                record.kafka_topic_prefix = f"mig_{record.partner_id.id}_{safe_name}"
            else:
                record.kafka_topic_prefix = False

    @api.depends('table_mapping_ids', 'table_mapping_ids.state')
    def _compute_statistics(self):
        for record in self:
            mappings = record.table_mapping_ids
            record.total_source_tables = len(mappings)
            record.total_mapped_tables = len(mappings.filtered(lambda m: m.state == 'mapped'))

    @api.depends('error_ids')
    def _compute_error_count(self):
        for record in self:
            record.total_error_records = len(record.error_ids.filtered(lambda e: e.state == 'pending'))

    @api.depends('total_source_records', 'total_migrated_records')
    def _compute_progress(self):
        for record in self:
            if record.total_source_records > 0:
                record.progress_percentage = (record.total_migrated_records / record.total_source_records) * 100
            else:
                record.progress_percentage = 0

    # === ACCIONES DEL WIZARD ===

    def action_next_step(self):
        """Avanzar al siguiente paso del wizard"""
        self.ensure_one()
        steps = ['1_connection', '2_schema', '3_topics', '4_fields', '5_review']
        current_index = steps.index(self.wizard_step)
        if current_index < len(steps) - 1:
            self.wizard_step = steps[current_index + 1]
        return True

    def action_previous_step(self):
        """Retroceder al paso anterior del wizard"""
        self.ensure_one()
        steps = ['1_connection', '2_schema', '3_topics', '4_fields', '5_review']
        current_index = steps.index(self.wizard_step)
        if current_index > 0:
            self.wizard_step = steps[current_index - 1]
        return True

    def action_test_connection(self):
        """Probar conexión con la base de datos origen"""
        self.ensure_one()
        if not self.source_connection_id:
            raise UserError(_('Debe configurar una conexión origen primero.'))

        result = self.source_connection_id.test_connection()
        if result.get('success'):
            self.state = 'connecting'
            self._log_info('Conexión establecida exitosamente')
        return result

    def action_analyze_schema(self):
        """Analizar el esquema de la base de datos origen"""
        self.ensure_one()
        self.state = 'analyzing'

        try:
            # Usar el servicio de lectura de esquemas
            schema_reader = self.env['migration.schema.reader']
            tables = schema_reader.read_schema(self.source_connection_id)

            # Crear mapeos de tablas
            for table_info in tables:
                self.env['migration.table.mapping'].create({
                    'project_id': self.id,
                    'source_table': table_info['name'],
                    'source_schema': table_info.get('schema', 'public'),
                    'row_count': table_info.get('row_count', 0),
                    'column_info': table_info.get('columns', []),
                })

            self.total_source_records = sum(t.get('row_count', 0) for t in tables)
            self._log_info(f'Esquema analizado: {len(tables)} tablas encontradas')

            # Si IA está habilitada, solicitar sugerencias
            if self.ai_suggestions_enabled:
                self.action_request_ai_suggestions()

            self.wizard_step = '2_schema'

        except Exception as e:
            self.state = 'error'
            self._log_error(f'Error analizando esquema: {str(e)}')
            raise UserError(_('Error analizando esquema: %s') % str(e))

    def action_request_ai_suggestions(self):
        """Solicitar sugerencias de mapeo a la IA"""
        self.ensure_one()
        try:
            ai_analyzer = self.env['migration.ai.analyzer']
            suggestions = ai_analyzer.analyze_and_suggest(self)

            # Aplicar sugerencias a los mapeos
            for suggestion in suggestions:
                mapping = self.table_mapping_ids.filtered(
                    lambda m: m.source_table == suggestion['source_table']
                )
                if mapping:
                    mapping.write({
                        'suggested_topic_id': suggestion.get('topic_id'),
                        'suggested_model': suggestion.get('odoo_model'),
                        'ai_confidence': suggestion.get('confidence', 0),
                        'ai_reason': suggestion.get('reason'),
                    })

            self._log_info('Sugerencias de IA aplicadas')

        except Exception as e:
            self._log_warning(f'Error obteniendo sugerencias IA: {str(e)}')

    def action_start_migration(self):
        """Iniciar la migración"""
        self.ensure_one()

        # Validar que hay mapeos configurados
        if not self.table_mapping_ids.filtered(lambda m: m.state == 'mapped'):
            raise UserError(_('Debe configurar al menos un mapeo de tabla antes de migrar.'))

        self.state = 'running'
        self.started_at = fields.Datetime.now()
        self._log_info('Migración iniciada')

        if self.use_kafka:
            # Iniciar migración con Kafka
            kafka_service = self.env['migration.kafka.service']
            kafka_service.start_migration(self)
        else:
            # Migración directa (sin Kafka)
            self._run_direct_migration()

    def action_pause_migration(self):
        """Pausar la migración"""
        self.ensure_one()
        if self.state == 'running':
            self.state = 'paused'
            self._log_info('Migración pausada')

            if self.use_kafka:
                kafka_service = self.env['migration.kafka.service']
                kafka_service.pause_migration(self)

    def action_resume_migration(self):
        """Reanudar la migración"""
        self.ensure_one()
        if self.state == 'paused':
            self.state = 'running'
            self._log_info('Migración reanudada')

            if self.use_kafka:
                kafka_service = self.env['migration.kafka.service']
                kafka_service.resume_migration(self)

    def action_cancel_migration(self):
        """Cancelar la migración"""
        self.ensure_one()
        if self.state in ('running', 'paused'):
            self.state = 'cancelled'
            self._log_warning('Migración cancelada por el usuario')

            if self.use_kafka:
                kafka_service = self.env['migration.kafka.service']
                kafka_service.stop_migration(self)

    def action_retry_errors(self):
        """Reintentar registros con error"""
        self.ensure_one()
        pending_errors = self.error_ids.filtered(lambda e: e.state == 'pending')

        for error in pending_errors:
            try:
                error.action_retry()
            except Exception as e:
                _logger.error(f'Error reintentando: {str(e)}')

        return True

    # === MÉTODOS DE LOGGING ===

    def _log_info(self, message):
        """Crear log de información"""
        self.env['migration.log'].create({
            'project_id': self.id,
            'level': 'info',
            'message': message,
        })

    def _log_warning(self, message):
        """Crear log de advertencia"""
        self.env['migration.log'].create({
            'project_id': self.id,
            'level': 'warning',
            'message': message,
        })

    def _log_error(self, message):
        """Crear log de error"""
        self.env['migration.log'].create({
            'project_id': self.id,
            'level': 'error',
            'message': message,
        })

    # === MÉTODOS PORTAL ===

    def _get_portal_url(self):
        """Obtener URL del portal para este proyecto"""
        return f'/my/migration/{self.id}'

    def get_progress_data(self):
        """Obtener datos de progreso para el portal"""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state,
            'progress': self.progress_percentage,
            'total_records': self.total_source_records,
            'migrated_records': self.total_migrated_records,
            'error_count': self.total_error_records,
            'tables_total': self.total_source_tables,
            'tables_mapped': self.total_mapped_tables,
        }

    # === ACCIONES VISUAL MAPPER ===

    def action_open_visual_mapper(self):
        """Abrir el Visual Mapper para mapeo de campos"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/my/migration/{self.id}/mapper',
            'target': 'new',
        }

    def action_view_table_mappings(self):
        """Ver mapeos de tablas del proyecto"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mapeos de %s') % self.name,
            'res_model': 'migration.table.mapping',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_auto_map_all(self):
        """Auto-mapear todos los campos usando similitud de nombres"""
        self.ensure_one()
        Analyzer = self.env['migration.odoo.model.analyzer']
        mapped_count = 0

        for mapping in self.table_mapping_ids:
            if not mapping.target_model:
                continue

            model_info = Analyzer.get_model_info(mapping.target_model)
            if not model_info:
                continue

            # Obtener campos del modelo destino
            target_fields = {f['name'].lower(): f['name'] for f in model_info['fields']['all']}

            # Obtener columnas origen
            columns = mapping.get_columns() if hasattr(mapping, 'get_columns') else []

            for col in columns:
                col_name = col.get('name', '').lower()

                # Buscar coincidencia exacta
                if col_name in target_fields:
                    self._create_or_update_field_mapping(
                        mapping, col.get('name'), target_fields[col_name], 100
                    )
                    mapped_count += 1

        self._log_info(f'Auto-mapeo completado: {mapped_count} campos mapeados')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Auto-Mapeo Completado'),
                'message': _('%d campos mapeados automaticamente') % mapped_count,
                'type': 'success',
            }
        }

    def _create_or_update_field_mapping(self, table_mapping, source_col, target_field, confidence):
        """Crear o actualizar mapeo de campo"""
        FieldMapping = self.env['migration.field.mapping']

        existing = FieldMapping.search([
            ('table_mapping_id', '=', table_mapping.id),
            ('source_column', '=', source_col)
        ], limit=1)

        values = {
            'target_field_name': target_field,
            'mapping_type': 'direct',
            'ai_confidence': confidence,
        }

        if existing:
            existing.write(values)
        else:
            values.update({
                'table_mapping_id': table_mapping.id,
                'source_column': source_col,
            })
            FieldMapping.create(values)

    def _run_direct_migration(self):
        """Ejecutar migracion directa (sin Kafka)"""
        # Implementacion basica para migracion sin streaming
        for mapping in self.table_mapping_ids.filtered(lambda m: m.state == 'mapped'):
            try:
                mapping.action_migrate_table()
            except Exception as e:
                self._log_error(f'Error migrando {mapping.source_table}: {str(e)}')

        self.state = 'completed'
        self.completed_at = fields.Datetime.now()
        self._log_info('Migracion completada')
