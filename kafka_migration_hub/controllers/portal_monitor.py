# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class MigrationPortalMonitor(http.Controller):
    """Controller para el monitor de migración en tiempo real"""

    @http.route('/my/migration/<int:project_id>/monitor', type='http', auth='user', website=True)
    def portal_monitor(self, project_id, **kw):
        """Página de monitor en tiempo real"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        # Obtener estadísticas por tópico
        topic_stats = []
        topics = {}
        for mapping in project.table_mapping_ids.filtered(lambda m: m.state == 'mapped'):
            topic = mapping.topic_id
            if topic:
                if topic.id not in topics:
                    topics[topic.id] = {
                        'id': topic.id,
                        'name': topic.name,
                        'icon': topic.icon,
                        'total_records': 0,
                        'migrated_records': 0,
                        'error_records': 0,
                        'tables': [],
                    }
                topics[topic.id]['total_records'] += mapping.row_count
                topics[topic.id]['migrated_records'] += mapping.migrated_records
                topics[topic.id]['error_records'] += mapping.error_records
                topics[topic.id]['tables'].append({
                    'name': mapping.source_table,
                    'target': mapping.target_model,
                    'progress': mapping.progress_percentage,
                })

        topic_stats = list(topics.values())

        values = {
            'page_name': 'migration_monitor',
            'project': project,
            'topic_stats': topic_stats,
            'recent_logs': project.log_ids[:20],
            'pending_errors': project.error_ids.filtered(lambda e: e.state == 'pending')[:10],
        }

        return request.render('kafka_migration_hub.portal_monitor', values)

    # === API Endpoints para Monitor ===

    @http.route('/my/migration/api/monitor/<int:project_id>/live', type='json', auth='user')
    def api_live_status(self, project_id):
        """Obtener estado en vivo del proyecto"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        # Estadísticas generales
        stats = {
            'state': project.state,
            'progress': project.progress_percentage,
            'total_records': project.total_source_records,
            'migrated_records': project.total_migrated_records,
            'error_count': project.total_error_records,
            'started_at': project.started_at.isoformat() if project.started_at else None,
        }

        # Estadísticas por tabla
        tables = []
        for mapping in project.table_mapping_ids.filtered(lambda m: m.state == 'mapped'):
            tables.append({
                'id': mapping.id,
                'source_table': mapping.source_table,
                'target_model': mapping.target_model,
                'topic': mapping.topic_id.name if mapping.topic_id else None,
                'topic_icon': mapping.topic_id.icon if mapping.topic_id else None,
                'total': mapping.row_count,
                'migrated': mapping.migrated_records,
                'errors': mapping.error_records,
                'progress': mapping.progress_percentage,
                'state': mapping.migration_state,
            })

        # Últimos logs
        logs = []
        recent_logs = request.env['migration.log'].search([
            ('project_id', '=', project_id)
        ], limit=10, order='create_date desc')

        for log in recent_logs:
            logs.append({
                'level': log.level,
                'message': log.message,
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'source_table': log.source_table,
            })

        return {
            'stats': stats,
            'tables': tables,
            'logs': logs,
        }

    @http.route('/my/migration/api/monitor/<int:project_id>/table/<int:mapping_id>/details', type='json', auth='user')
    def api_table_details(self, project_id, mapping_id):
        """Obtener detalles de progreso de una tabla"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        mapping = request.env['migration.table.mapping'].browse(mapping_id)
        if mapping.project_id.id != project_id:
            return {'error': 'Mapeo no pertenece al proyecto'}

        # Obtener errores de esta tabla
        errors = request.env['migration.error'].search([
            ('table_mapping_id', '=', mapping_id),
            ('state', '=', 'pending'),
        ], limit=20)

        return {
            'table': mapping.get_portal_data(),
            'errors': [e.get_portal_data() for e in errors],
        }

    @http.route('/my/migration/api/monitor/<int:project_id>/error/<int:error_id>/retry', type='json', auth='user')
    def api_retry_error(self, project_id, error_id):
        """Reintentar un error específico"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        error = request.env['migration.error'].browse(error_id)
        if error.project_id.id != project_id:
            return {'error': 'Error no pertenece al proyecto'}

        try:
            result = error.action_retry()
            return {'success': result, 'state': error.state}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/my/migration/api/monitor/<int:project_id>/error/<int:error_id>/ignore', type='json', auth='user')
    def api_ignore_error(self, project_id, error_id):
        """Ignorar un error específico"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        error = request.env['migration.error'].browse(error_id)
        if error.project_id.id != project_id:
            return {'error': 'Error no pertenece al proyecto'}

        error.action_ignore()
        return {'success': True, 'state': error.state}

    @http.route('/my/migration/api/monitor/<int:project_id>/retry-all-errors', type='json', auth='user')
    def api_retry_all_errors(self, project_id):
        """Reintentar todos los errores pendientes"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        project.action_retry_errors()

        pending_count = request.env['migration.error'].get_pending_count(project_id)

        return {
            'success': True,
            'pending_count': pending_count,
        }

    @http.route('/my/migration/api/monitor/<int:project_id>/export-log', type='http', auth='user')
    def api_export_log(self, project_id, **kw):
        """Exportar log de migración"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        # Generar CSV de logs
        import io
        import csv

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'Level', 'Message', 'Table', 'Record ID'])

        for log in project.log_ids:
            writer.writerow([
                log.timestamp.isoformat() if log.timestamp else '',
                log.level,
                log.message,
                log.source_table or '',
                log.record_id or '',
            ])

        content = output.getvalue()
        output.close()

        headers = [
            ('Content-Type', 'text/csv'),
            ('Content-Disposition', f'attachment; filename="migration_log_{project_id}.csv"'),
        ]

        return request.make_response(content, headers)
