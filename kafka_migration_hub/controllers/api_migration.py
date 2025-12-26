# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class MigrationAPI(http.Controller):
    """API REST para integración externa"""

    @http.route('/api/migration/v1/projects', type='json', auth='api_key', methods=['GET'])
    def api_list_projects(self, **kw):
        """Listar proyectos (requiere API key)"""
        partner = request.env.user.partner_id

        projects = request.env['migration.project'].search([
            ('partner_id', '=', partner.id)
        ])

        return {
            'success': True,
            'data': [{
                'id': p.id,
                'name': p.name,
                'state': p.state,
                'progress': p.progress_percentage,
                'created': p.create_date.isoformat() if p.create_date else None,
            } for p in projects]
        }

    @http.route('/api/migration/v1/projects/<int:project_id>', type='json', auth='api_key', methods=['GET'])
    def api_get_project(self, project_id, **kw):
        """Obtener detalle de un proyecto"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'success': False, 'error': 'Acceso denegado'}

        return {
            'success': True,
            'data': project.get_progress_data(),
        }

    @http.route('/api/migration/v1/projects/<int:project_id>/start', type='json', auth='api_key', methods=['POST'])
    def api_start_project(self, project_id, **kw):
        """Iniciar migración vía API"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'success': False, 'error': 'Acceso denegado'}

        try:
            project.action_start_migration()
            return {'success': True, 'state': project.state}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/api/migration/v1/projects/<int:project_id>/pause', type='json', auth='api_key', methods=['POST'])
    def api_pause_project(self, project_id, **kw):
        """Pausar migración vía API"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'success': False, 'error': 'Acceso denegado'}

        project.action_pause_migration()
        return {'success': True, 'state': project.state}

    @http.route('/api/migration/v1/projects/<int:project_id>/resume', type='json', auth='api_key', methods=['POST'])
    def api_resume_project(self, project_id, **kw):
        """Reanudar migración vía API"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'success': False, 'error': 'Acceso denegado'}

        project.action_resume_migration()
        return {'success': True, 'state': project.state}

    @http.route('/api/migration/v1/webhook/kafka', type='json', auth='public', methods=['POST'], csrf=False)
    def api_kafka_webhook(self, **post):
        """
        Webhook para recibir eventos de Kafka.
        Puede ser usado con Kafka Connect HTTP Sink.
        """
        # Verificar token de autenticación
        token = request.httprequest.headers.get('X-Webhook-Token')
        expected_token = request.env['ir.config_parameter'].sudo().get_param(
            'migration_hub.webhook_token'
        )

        if not token or token != expected_token:
            return {'success': False, 'error': 'Token inválido'}

        # Procesar evento
        try:
            event_type = post.get('event_type')
            project_id = post.get('project_id')
            data = post.get('data', {})

            if event_type == 'record_migrated':
                # Actualizar contador de registros migrados
                mapping_id = data.get('mapping_id')
                if mapping_id:
                    mapping = request.env['migration.table.mapping'].sudo().browse(mapping_id)
                    mapping.migrated_records += 1

            elif event_type == 'record_error':
                # Registrar error
                request.env['migration.error'].sudo().create({
                    'project_id': project_id,
                    'table_mapping_id': data.get('mapping_id'),
                    'source_table': data.get('source_table'),
                    'source_record_id': data.get('source_id'),
                    'source_data': json.dumps(data.get('source_data', {})),
                    'error_type': data.get('error_type', 'unknown'),
                    'error_message': data.get('error_message'),
                })

            elif event_type == 'migration_completed':
                project = request.env['migration.project'].sudo().browse(project_id)
                project.state = 'completed'
                project.completed_at = request.env.fields.Datetime.now()

            return {'success': True}

        except Exception as e:
            _logger.error(f'Error procesando webhook: {e}')
            return {'success': False, 'error': str(e)}

    @http.route('/api/migration/v1/health', type='json', auth='public', methods=['GET'])
    def api_health_check(self, **kw):
        """Health check endpoint"""
        # Verificar conexión a Kafka si está configurado
        kafka_status = 'not_configured'
        try:
            kafka_service = request.env['migration.kafka.service'].sudo()
            result = kafka_service.test_connection()
            kafka_status = 'connected' if result.get('success') else 'error'
        except Exception:
            kafka_status = 'error'

        return {
            'status': 'ok',
            'kafka': kafka_status,
            'version': '1.0.0',
        }
