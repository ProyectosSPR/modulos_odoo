# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import json
import logging

_logger = logging.getLogger(__name__)


class MigrationPortal(CustomerPortal):
    """Controller principal del portal de migración"""

    def _prepare_home_portal_values(self, counters):
        """Agregar contadores al portal home"""
        values = super()._prepare_home_portal_values(counters)

        if 'migration_count' in counters:
            partner = request.env.user.partner_id
            values['migration_count'] = request.env['migration.project'].search_count([
                ('partner_id', '=', partner.id)
            ])

        return values

    @http.route(['/my/migration'], type='http', auth='user', website=True)
    def portal_migration_dashboard(self, **kw):
        """Dashboard principal de migración"""
        partner = request.env.user.partner_id

        # Obtener proyectos del usuario
        projects = request.env['migration.project'].search([
            ('partner_id', '=', partner.id)
        ], order='create_date desc')

        # Estadísticas
        stats = {
            'total_projects': len(projects),
            'running': len(projects.filtered(lambda p: p.state == 'running')),
            'completed': len(projects.filtered(lambda p: p.state == 'completed')),
            'total_records_migrated': sum(projects.mapped('total_migrated_records')),
        }

        values = {
            'page_name': 'migration_dashboard',
            'projects': projects,
            'stats': stats,
        }

        return request.render('kafka_migration_hub.portal_dashboard', values)

    @http.route(['/my/migration/new'], type='http', auth='user', website=True)
    def portal_new_project(self, **kw):
        """Crear nuevo proyecto de migración"""
        # Obtener conexiones del usuario
        partner = request.env.user.partner_id
        connections = request.env['migration.source.connection'].search([
            ('partner_id', '=', partner.id)
        ])

        values = {
            'page_name': 'migration_new',
            'connections': connections,
            'db_types': [
                ('postgresql', 'PostgreSQL'),
                ('mysql', 'MySQL / MariaDB'),
                ('mssql', 'Microsoft SQL Server'),
                ('oracle', 'Oracle'),
                ('odoo', 'Odoo (otra instancia)'),
                ('csv', 'Archivos CSV'),
                ('excel', 'Archivos Excel'),
            ],
        }

        return request.render('kafka_migration_hub.portal_new_project', values)

    @http.route(['/my/migration/create'], type='http', auth='user', website=True, methods=['POST'])
    def portal_create_project(self, **post):
        """Procesar creación de proyecto"""
        partner = request.env.user.partner_id

        # Crear conexión si es nueva
        connection_id = post.get('connection_id')
        if not connection_id or connection_id == 'new':
            connection = request.env['migration.source.connection'].create({
                'name': post.get('connection_name', 'Nueva Conexión'),
                'db_type': post.get('db_type', 'postgresql'),
                'host': post.get('host'),
                'port': int(post.get('port', 5432)),
                'database': post.get('database'),
                'username': post.get('username'),
                'password': post.get('password'),
                'partner_id': partner.id,
            })
            connection_id = connection.id

        # Crear proyecto
        project = request.env['migration.project'].create({
            'name': post.get('project_name', 'Nuevo Proyecto'),
            'description': post.get('description'),
            'source_connection_id': int(connection_id),
            'partner_id': partner.id,
            'user_id': request.env.user.id,
        })

        return request.redirect(f'/my/migration/{project.id}/wizard')

    @http.route([
        '/my/migration/<int:project_id>',
    ], type='http', auth='user', website=True)
    def portal_project_detail(self, project_id, **kw):
        """Detalle de un proyecto"""
        project = request.env['migration.project'].browse(project_id)

        # Verificar acceso
        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        values = {
            'page_name': 'migration_detail',
            'project': project,
            'table_mappings': project.table_mapping_ids,
            'logs': project.log_ids[:50],  # Ultimos 50 logs
            'errors': project.error_ids.filtered(lambda e: e.state == 'pending')[:20],
        }

        return request.render('kafka_migration_hub.portal_project_detail', values)

    @http.route([
        '/my/migration/<int:project_id>/mapper',
    ], type='http', auth='user', website=True)
    def portal_visual_mapper(self, project_id, **kw):
        """Visual Mapper para mapeo de campos"""
        project = request.env['migration.project'].browse(project_id)

        # Verificar acceso
        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        values = {
            'page_name': 'migration_mapper',
            'project': project,
        }

        return request.render('kafka_migration_hub.portal_visual_mapper', values)


class MigrationPortalAPI(http.Controller):
    """API endpoints para el portal (AJAX)"""

    @http.route('/my/migration/api/stats', type='json', auth='user')
    def api_get_stats(self):
        """Obtener estadísticas del usuario"""
        partner = request.env.user.partner_id
        projects = request.env['migration.project'].search([
            ('partner_id', '=', partner.id)
        ])

        return {
            'total_projects': len(projects),
            'running': len(projects.filtered(lambda p: p.state == 'running')),
            'completed': len(projects.filtered(lambda p: p.state == 'completed')),
            'paused': len(projects.filtered(lambda p: p.state == 'paused')),
            'total_records': sum(projects.mapped('total_source_records')),
            'migrated_records': sum(projects.mapped('total_migrated_records')),
        }

    @http.route('/my/migration/api/project/<int:project_id>/progress', type='json', auth='user')
    def api_get_progress(self, project_id):
        """Obtener progreso de un proyecto"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        return project.get_progress_data()

    @http.route('/my/migration/api/topics', type='json', auth='user')
    def api_get_topics(self):
        """Obtener lista de tópicos disponibles"""
        company_id = request.env.user.company_id.id
        topics = request.env['migration.topic'].get_topics_for_portal(company_id)
        return {'topics': topics}

    @http.route('/my/migration/api/test-connection', type='json', auth='user')
    def api_test_connection(self, **post):
        """Probar conexión a base de datos"""
        # Crear conexión temporal para probar
        connection = request.env['migration.source.connection'].create({
            'name': 'Test Connection',
            'db_type': post.get('db_type'),
            'host': post.get('host'),
            'port': int(post.get('port', 5432)),
            'database': post.get('database'),
            'username': post.get('username'),
            'password': post.get('password'),
            'partner_id': request.env.user.partner_id.id,
        })

        result = connection.test_connection()

        # Si la prueba falla, eliminar la conexión temporal
        if not result.get('success'):
            connection.unlink()

        return result

    @http.route('/my/migration/api/project/<int:project_id>/logs', type='json', auth='user')
    def api_get_logs(self, project_id, limit=50, offset=0):
        """Obtener logs de un proyecto"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        logs = request.env['migration.log'].search([
            ('project_id', '=', project_id)
        ], limit=limit, offset=offset, order='create_date desc')

        return {
            'logs': [{
                'id': log.id,
                'level': log.level,
                'message': log.message,
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'source_table': log.source_table,
            } for log in logs]
        }

    @http.route('/my/migration/api/project/<int:project_id>/errors', type='json', auth='user')
    def api_get_errors(self, project_id, state='pending'):
        """Obtener errores de un proyecto"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        domain = [('project_id', '=', project_id)]
        if state:
            domain.append(('state', '=', state))

        errors = request.env['migration.error'].search(domain, limit=100)

        return {
            'errors': [e.get_portal_data() for e in errors],
            'total_pending': request.env['migration.error'].get_pending_count(project_id),
        }

    @http.route('/my/migration/api/project/<int:project_id>/schema', type='json', auth='user')
    def api_get_schema(self, project_id):
        """Obtener esquema completo del proyecto con relaciones"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'success': False, 'error': 'Acceso denegado'}

        try:
            # Obtener tablas del proyecto
            tables = []
            mappings = {}

            for mapping in project.table_mapping_ids:
                table_data = {
                    'name': mapping.source_table,
                    'schema': mapping.source_schema,
                    'row_count': mapping.row_count,
                    'columns': mapping.get_columns(),
                    'pk_columns': [],
                }
                tables.append(table_data)

                mappings[mapping.source_table] = {
                    'id': mapping.id,
                    'topic_id': mapping.topic_id.id if mapping.topic_id else None,
                    'suggested_topic_id': mapping.suggested_topic_id.id if mapping.suggested_topic_id else None,
                    'target_model': mapping.target_model,
                    'suggested_model': mapping.suggested_model,
                    'ai_confidence': mapping.ai_confidence,
                    'ai_reason': mapping.ai_reason,
                    'state': mapping.state,
                }

            # Analizar relaciones entre tablas
            SchemaReader = request.env['migration.schema.reader']
            relationships = SchemaReader.analyze_relationships(tables)

            # Generar datos de visualización
            visualization = SchemaReader.generate_schema_visualization(tables, relationships)

            # Obtener orden de migración
            migration_order = SchemaReader.get_migration_order(tables, relationships)

            # Obtener tópicos disponibles
            topics = request.env['migration.topic'].search([])
            topics_data = [{
                'id': t.id,
                'name': t.name,
                'icon': t.icon,
                'description': t.description,
            } for t in topics]

            return {
                'success': True,
                'schema': {
                    'tables': tables,
                    'relationships': relationships,
                    'visualization': visualization,
                    'migration_order': migration_order,
                },
                'mappings': mappings,
                'topics': topics_data,
            }

        except Exception as e:
            _logger.exception("Error obteniendo esquema")
            return {'success': False, 'error': str(e)}

    @http.route('/my/migration/api/project/<int:project_id>/table/<string:table_name>', type='json', auth='user')
    def api_get_table_details(self, project_id, table_name):
        """Obtener detalles de una tabla específica"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'success': False, 'error': 'Acceso denegado'}

        mapping = request.env['migration.table.mapping'].search([
            ('project_id', '=', project_id),
            ('source_table', '=', table_name)
        ], limit=1)

        if not mapping:
            return {'success': False, 'error': 'Tabla no encontrada'}

        # Obtener columnas
        columns = mapping.get_columns()

        # Obtener sugerencias de campos si existen
        suggestions = []
        for field_mapping in mapping.field_mapping_ids:
            if field_mapping.target_field_id:
                suggestions.append({
                    'source_column': field_mapping.source_column,
                    'target_field': field_mapping.target_field_name,
                    'confidence': field_mapping.ai_confidence / 100,
                    'mapping_type': field_mapping.mapping_type,
                })

        return {
            'success': True,
            'table': {
                'name': mapping.source_table,
                'schema': mapping.source_schema,
                'row_count': mapping.row_count,
            },
            'columns': columns,
            'mapping': {
                'id': mapping.id,
                'topic_id': mapping.topic_id.id if mapping.topic_id else None,
                'suggested_topic_id': mapping.suggested_topic_id.id if mapping.suggested_topic_id else None,
                'target_model': mapping.target_model,
                'target_model_id': mapping.target_model_id.id if mapping.target_model_id else None,
                'ai_confidence': mapping.ai_confidence,
                'ai_reason': mapping.ai_reason,
                'state': mapping.state,
            },
            'suggestions': suggestions,
        }

    @http.route('/my/migration/api/project/<int:project_id>/mapping/update', type='json', auth='user')
    def api_update_mapping(self, project_id, **post):
        """Actualizar mapeo de una tabla"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'success': False, 'error': 'Acceso denegado'}

        table_name = post.get('table_name')
        topic_id = post.get('topic_id')

        mapping = request.env['migration.table.mapping'].search([
            ('project_id', '=', project_id),
            ('source_table', '=', table_name)
        ], limit=1)

        if not mapping:
            return {'success': False, 'error': 'Tabla no encontrada'}

        try:
            values = {}
            if topic_id:
                values['topic_id'] = int(topic_id) if topic_id != 'ignore' else False
                if topic_id == 'ignore':
                    values['state'] = 'ignored'
                else:
                    values['state'] = 'mapped'

            mapping.write(values)
            return {'success': True}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/my/migration/api/project/<int:project_id>/ai/suggest', type='json', auth='user')
    def api_request_ai_suggestions(self, project_id, **post):
        """Solicitar sugerencias de IA para mapeo"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'success': False, 'error': 'Acceso denegado'}

        try:
            table_name = post.get('table_name')

            if table_name:
                # Sugerencias para una tabla específica
                mapping = request.env['migration.table.mapping'].search([
                    ('project_id', '=', project_id),
                    ('source_table', '=', table_name)
                ], limit=1)

                if mapping:
                    AIAnalyzer = request.env['migration.ai.analyzer']
                    suggestions = AIAnalyzer.suggest_field_mappings(mapping)

                    return {
                        'success': True,
                        'suggestions': suggestions,
                        'message': f'{len(suggestions)} sugerencias generadas'
                    }
            else:
                # Sugerencias para todo el proyecto
                project.action_request_ai_suggestions()
                return {
                    'success': True,
                    'message': 'Análisis de IA iniciado'
                }

        except Exception as e:
            _logger.exception("Error en sugerencias de IA")
            return {'success': False, 'error': str(e)}

    @http.route('/my/migration/api/ai/test', type='json', auth='user')
    def api_test_ai_connection(self, **post):
        """Probar conexión con el servicio de IA"""
        try:
            AIAnalyzer = request.env['migration.ai.analyzer']
            config = AIAnalyzer.get_ai_config()

            if config.get('provider') == 'claude' and config.get('claude_api_key'):
                result = AIAnalyzer.test_claude_connection()
                return result
            elif config.get('provider') == 'openai' and config.get('openai_api_key'):
                return {'success': True, 'message': 'OpenAI configurado (test no implementado)'}
            else:
                return {'success': True, 'message': 'Usando heurísticas locales'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==========================================
    # API para Visual Mapper
    # ==========================================

    @http.route('/migration/api/project/<int:project_id>/schema', type='json', auth='user')
    def api_visual_mapper_schema(self, project_id):
        """Obtener esquema para el Visual Mapper"""
        project = request.env['migration.project'].browse(project_id)

        if not project.exists():
            return {'success': False, 'error': 'Proyecto no encontrado'}

        # Verificar acceso (portal o backend)
        if not request.env.user.has_group('kafka_migration_hub.group_migration_user'):
            if project.partner_id != request.env.user.partner_id:
                return {'success': False, 'error': 'Acceso denegado'}

        try:
            # Obtener tablas origen con sus columnas
            source_tables = []
            for mapping in project.table_mapping_ids:
                columns = mapping.get_columns() if hasattr(mapping, 'get_columns') else []
                source_tables.append({
                    'name': mapping.source_table,
                    'schema': mapping.source_schema or 'public',
                    'row_count': mapping.row_count,
                    'columns': columns,
                })

            # Obtener modelos Odoo de destino
            target_models = []
            Analyzer = request.env['migration.odoo.model.analyzer']

            # Si hay tópico seleccionado, obtener sus modelos
            for mapping in project.table_mapping_ids:
                if mapping.topic_id:
                    for model in mapping.topic_id.model_ids:
                        model_info = Analyzer.get_model_info(model.model)
                        if model_info:
                            # Simplificar campos para el frontend
                            fields = []
                            for f in model_info['fields']['all'][:30]:  # Limitar
                                fields.append({
                                    'name': f['name'],
                                    'type': f['type'],
                                    'required': f['required'],
                                    'relation': f.get('relation'),
                                })
                            target_models.append({
                                'model': model.model,
                                'name': model.name,
                                'fields': fields,
                            })

            # Si no hay modelos de tópicos, cargar modelos comunes
            if not target_models:
                common_models = ['res.partner', 'product.template', 'sale.order', 'account.move']
                for model_name in common_models:
                    model_info = Analyzer.get_model_info(model_name)
                    if model_info:
                        fields = []
                        for f in model_info['fields']['all'][:30]:
                            fields.append({
                                'name': f['name'],
                                'type': f['type'],
                                'required': f['required'],
                                'relation': f.get('relation'),
                            })
                        target_models.append({
                            'model': model_name,
                            'name': model_info['name'],
                            'fields': fields,
                        })

            # Obtener mapeos existentes
            existing_mappings = []
            for mapping in project.table_mapping_ids:
                for field_map in mapping.field_mapping_ids:
                    if field_map.target_field_name:
                        existing_mappings.append({
                            'source_table': mapping.source_table,
                            'source_field': field_map.source_column,
                            'target_model': mapping.target_model or '',
                            'target_field': field_map.target_field_name,
                        })

            return {
                'success': True,
                'source_tables': source_tables,
                'target_models': target_models,
                'mappings': existing_mappings,
            }

        except Exception as e:
            _logger.exception("Error obteniendo esquema para visual mapper")
            return {'success': False, 'error': str(e)}

    @http.route('/migration/api/project/<int:project_id>/auto-map', type='json', auth='user')
    def api_auto_map(self, project_id):
        """Auto-mapear campos por similitud de nombres"""
        project = request.env['migration.project'].browse(project_id)

        if not project.exists():
            return {'success': False, 'error': 'Proyecto no encontrado'}

        try:
            suggested_mappings = []
            Analyzer = request.env['migration.odoo.model.analyzer']

            for mapping in project.table_mapping_ids:
                if not mapping.target_model:
                    continue

                # Obtener info del modelo destino
                model_info = Analyzer.get_model_info(mapping.target_model)
                if not model_info:
                    continue

                target_fields = {f['name'].lower(): f['name'] for f in model_info['fields']['all']}
                columns = mapping.get_columns() if hasattr(mapping, 'get_columns') else []

                for col in columns:
                    col_name = col.get('name', '').lower()

                    # Buscar coincidencia exacta
                    if col_name in target_fields:
                        suggested_mappings.append({
                            'source_table': mapping.source_table,
                            'source_field': col.get('name'),
                            'target_model': mapping.target_model,
                            'target_field': target_fields[col_name],
                            'confidence': 100,
                        })
                        continue

                    # Buscar similares
                    best_match = None
                    best_score = 0
                    for tf_lower, tf_orig in target_fields.items():
                        score = _calculate_similarity(col_name, tf_lower)
                        if score > best_score and score > 0.6:
                            best_score = score
                            best_match = tf_orig

                    if best_match:
                        suggested_mappings.append({
                            'source_table': mapping.source_table,
                            'source_field': col.get('name'),
                            'target_model': mapping.target_model,
                            'target_field': best_match,
                            'confidence': int(best_score * 100),
                        })

            return {
                'success': True,
                'suggested_mappings': suggested_mappings,
            }

        except Exception as e:
            _logger.exception("Error en auto-mapeo")
            return {'success': False, 'error': str(e)}

    @http.route('/migration/api/project/<int:project_id>/mappings/save', type='json', auth='user')
    def api_save_mappings(self, project_id, mappings=None):
        """Guardar mapeos del Visual Mapper"""
        project = request.env['migration.project'].browse(project_id)

        if not project.exists():
            return {'success': False, 'error': 'Proyecto no encontrado'}

        if not mappings:
            return {'success': False, 'error': 'No hay mapeos para guardar'}

        try:
            FieldMapping = request.env['migration.field.mapping']

            # Agrupar por tabla
            mappings_by_table = {}
            for m in mappings:
                table = m.get('source_table')
                if table not in mappings_by_table:
                    mappings_by_table[table] = []
                mappings_by_table[table].append(m)

            saved_count = 0

            for table_name, table_mappings in mappings_by_table.items():
                # Buscar el table mapping
                table_mapping = request.env['migration.table.mapping'].search([
                    ('project_id', '=', project_id),
                    ('source_table', '=', table_name)
                ], limit=1)

                if not table_mapping:
                    continue

                for m in table_mappings:
                    # Buscar o crear field mapping
                    field_map = FieldMapping.search([
                        ('table_mapping_id', '=', table_mapping.id),
                        ('source_column', '=', m.get('source_field'))
                    ], limit=1)

                    values = {
                        'target_field_name': m.get('target_field'),
                        'mapping_type': 'direct',
                    }

                    if field_map:
                        field_map.write(values)
                    else:
                        values.update({
                            'table_mapping_id': table_mapping.id,
                            'source_column': m.get('source_field'),
                        })
                        FieldMapping.create(values)

                    saved_count += 1

            return {
                'success': True,
                'message': f'{saved_count} mapeos guardados',
            }

        except Exception as e:
            _logger.exception("Error guardando mapeos")
            return {'success': False, 'error': str(e)}

    @http.route('/migration/api/models/search', type='json', auth='user')
    def api_search_models(self, query='', limit=20):
        """Buscar modelos de Odoo"""
        try:
            domain = [('transient', '=', False)]
            if query:
                domain.append('|')
                domain.append(('model', 'ilike', query))
                domain.append(('name', 'ilike', query))

            models = request.env['ir.model'].search(domain, limit=limit)
            Analyzer = request.env['migration.odoo.model.analyzer']

            results = []
            for model in models:
                model_info = Analyzer.get_model_info(model.model)
                field_count = model_info['field_count'] if model_info else 0
                results.append({
                    'id': model.id,
                    'model': model.model,
                    'name': model.name,
                    'field_count': field_count,
                })

            return {'success': True, 'models': results}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/migration/api/model/<string:model_name>/fields', type='json', auth='user')
    def api_get_model_fields(self, model_name):
        """Obtener campos de un modelo Odoo"""
        try:
            Analyzer = request.env['migration.odoo.model.analyzer']
            model_info = Analyzer.get_model_info(model_name)

            if not model_info:
                return {'success': False, 'error': 'Modelo no encontrado'}

            fields = []
            for f in model_info['fields']['all']:
                fields.append({
                    'name': f['name'],
                    'type': f['type'],
                    'string': f['string'],
                    'required': f['required'],
                    'relation': f.get('relation'),
                })

            return {
                'success': True,
                'model': model_name,
                'name': model_info['name'],
                'fields': fields,
                'dependencies': model_info['dependencies'],
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}


def _calculate_similarity(str1, str2):
    """Calcular similitud entre dos strings"""
    if not str1 or not str2:
        return 0

    # Normalizar
    s1 = str1.lower().replace('_', '').replace('-', '')
    s2 = str2.lower().replace('_', '').replace('-', '')

    # Si uno contiene al otro
    if s1 in s2 or s2 in s1:
        return 0.8

    # Similitud por caracteres comunes
    common = set(s1) & set(s2)
    total = set(s1) | set(s2)

    if not total:
        return 0

    return len(common) / len(total)
