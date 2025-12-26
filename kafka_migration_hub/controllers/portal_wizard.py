# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class MigrationPortalWizard(http.Controller):
    """Controller para el wizard de configuración paso a paso"""

    @http.route('/my/migration/<int:project_id>/wizard', type='http', auth='user', website=True)
    def portal_wizard(self, project_id, step=None, **kw):
        """Wizard de configuración de migración"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        # Determinar paso actual
        current_step = step or project.wizard_step or '1_connection'

        # Obtener datos según el paso
        step_data = self._get_step_data(project, current_step)

        values = {
            'page_name': 'migration_wizard',
            'project': project,
            'current_step': current_step,
            'steps': [
                ('1_connection', 'Conexión', 'Configurar fuente de datos'),
                ('2_schema', 'Esquema', 'Analizar estructura'),
                ('3_topics', 'Tópicos', 'Asignar categorías'),
                ('4_fields', 'Campos', 'Mapear campos'),
                ('5_review', 'Revisar', 'Confirmar y ejecutar'),
            ],
            **step_data,
        }

        return request.render('kafka_migration_hub.portal_wizard', values)

    def _get_step_data(self, project, step):
        """Obtener datos específicos para cada paso"""
        data = {}

        if step == '1_connection':
            data['connection'] = project.source_connection_id
            data['db_types'] = [
                ('postgresql', 'PostgreSQL'),
                ('mysql', 'MySQL / MariaDB'),
                ('mssql', 'Microsoft SQL Server'),
                ('oracle', 'Oracle'),
                ('odoo', 'Odoo (otra instancia)'),
            ]

        elif step == '2_schema':
            data['table_mappings'] = project.table_mapping_ids
            data['total_tables'] = len(project.table_mapping_ids)
            data['total_records'] = sum(project.table_mapping_ids.mapped('row_count'))

        elif step == '3_topics':
            data['table_mappings'] = project.table_mapping_ids
            data['topics'] = request.env['migration.topic'].search([])
            data['unmapped_tables'] = project.table_mapping_ids.filtered(
                lambda m: m.state == 'pending'
            )

        elif step == '4_fields':
            data['mapped_tables'] = project.table_mapping_ids.filtered(
                lambda m: m.state == 'mapped'
            )

        elif step == '5_review':
            resolver = request.env['migration.dependency.resolver']
            data['migration_order'] = resolver.get_migration_order(project)
            data['issues'] = resolver.validate_dependencies(project)
            data['stats'] = {
                'tables_mapped': len(project.table_mapping_ids.filtered(lambda m: m.state == 'mapped')),
                'tables_ignored': len(project.table_mapping_ids.filtered(lambda m: m.state == 'ignored')),
                'total_records': project.total_source_records,
            }

        return data

    @http.route('/my/migration/<int:project_id>/wizard/step/<string:step>', type='http', auth='user', website=True, methods=['POST'])
    def portal_wizard_process_step(self, project_id, step, **post):
        """Procesar un paso del wizard"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        next_step = None

        if step == '1_connection':
            next_step = self._process_step_connection(project, post)

        elif step == '2_schema':
            next_step = self._process_step_schema(project, post)

        elif step == '3_topics':
            next_step = self._process_step_topics(project, post)

        elif step == '4_fields':
            next_step = self._process_step_fields(project, post)

        elif step == '5_review':
            # Iniciar migración
            return request.redirect(f'/my/migration/{project_id}/start')

        if next_step:
            project.wizard_step = next_step
            return request.redirect(f'/my/migration/{project_id}/wizard?step={next_step}')

        return request.redirect(f'/my/migration/{project_id}/wizard')

    def _process_step_connection(self, project, post):
        """Procesar paso de conexión"""
        connection = project.source_connection_id

        if connection:
            # Actualizar conexión existente
            connection.write({
                'host': post.get('host'),
                'port': int(post.get('port', 5432)),
                'database': post.get('database'),
                'username': post.get('username'),
                'password': post.get('password') if post.get('password') else connection.password,
            })
        else:
            # Crear nueva conexión
            connection = request.env['migration.source.connection'].create({
                'name': f'Conexión {project.name}',
                'db_type': post.get('db_type', 'postgresql'),
                'host': post.get('host'),
                'port': int(post.get('port', 5432)),
                'database': post.get('database'),
                'username': post.get('username'),
                'password': post.get('password'),
                'partner_id': project.partner_id.id,
            })
            project.source_connection_id = connection

        # Probar conexión
        result = connection.test_connection()
        if result.get('success'):
            project.state = 'connecting'
            return '2_schema'

        return '1_connection'

    def _process_step_schema(self, project, post):
        """Procesar paso de análisis de esquema"""
        if post.get('action') == 'analyze':
            try:
                project.action_analyze_schema()
                return '3_topics'
            except Exception as e:
                _logger.error(f'Error analizando esquema: {e}')
                return '2_schema'

        return '2_schema'

    def _process_step_topics(self, project, post):
        """Procesar paso de asignación de tópicos"""
        # Procesar asignaciones de tópicos
        for key, value in post.items():
            if key.startswith('topic_'):
                mapping_id = int(key.replace('topic_', ''))
                mapping = request.env['migration.table.mapping'].browse(mapping_id)
                if mapping.project_id.id == project.id and value:
                    mapping.write({
                        'topic_id': int(value),
                        'state': 'suggested' if mapping.state == 'pending' else mapping.state,
                    })

        # Aceptar todas las sugerencias si se solicita
        if post.get('accept_all'):
            for mapping in project.table_mapping_ids.filtered(lambda m: m.suggested_topic_id):
                mapping.action_accept_suggestion()

        project.state = 'mapping'
        return '4_fields'

    def _process_step_fields(self, project, post):
        """Procesar paso de mapeo de campos"""
        project.state = 'ready'
        return '5_review'

    # === API Endpoints para Wizard ===

    @http.route('/my/migration/api/wizard/<int:project_id>/analyze', type='json', auth='user')
    def api_analyze_schema(self, project_id):
        """Analizar esquema de la BD origen"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        try:
            project.action_analyze_schema()
            return {
                'success': True,
                'tables': len(project.table_mapping_ids),
                'total_records': project.total_source_records,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/my/migration/api/wizard/<int:project_id>/ai-suggest', type='json', auth='user')
    def api_ai_suggest(self, project_id):
        """Solicitar sugerencias de IA"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        try:
            project.action_request_ai_suggestions()
            return {
                'success': True,
                'tables': [m.get_portal_data() for m in project.table_mapping_ids],
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/my/migration/api/wizard/<int:project_id>/accept-all', type='json', auth='user')
    def api_accept_all_suggestions(self, project_id):
        """Aceptar todas las sugerencias de IA"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        count = 0
        for mapping in project.table_mapping_ids.filtered(lambda m: m.suggested_topic_id):
            mapping.action_accept_suggestion()
            count += 1

        return {'success': True, 'accepted_count': count}

    @http.route('/my/migration/api/wizard/<int:project_id>/generate-field-mappings', type='json', auth='user')
    def api_generate_field_mappings(self, project_id, mapping_id):
        """Generar mapeos de campos para una tabla"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        mapping = request.env['migration.table.mapping'].browse(int(mapping_id))
        if mapping.project_id.id != project_id:
            return {'error': 'Mapeo no pertenece al proyecto'}

        mapping._generate_field_mappings()

        return {
            'success': True,
            'fields': [f.get_portal_data() for f in mapping.field_mapping_ids],
        }
