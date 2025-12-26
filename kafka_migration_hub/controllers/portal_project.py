# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class MigrationPortalProject(http.Controller):
    """Controller para gestión de proyectos en portal"""

    @http.route('/my/migration/<int:project_id>/start', type='http', auth='user', website=True, methods=['POST'])
    def portal_start_migration(self, project_id, **kw):
        """Iniciar migración de un proyecto"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        try:
            project.action_start_migration()
            return request.redirect(f'/my/migration/{project_id}/monitor')
        except Exception as e:
            return request.redirect(f'/my/migration/{project_id}?error={str(e)}')

    @http.route('/my/migration/<int:project_id>/pause', type='http', auth='user', website=True, methods=['POST'])
    def portal_pause_migration(self, project_id, **kw):
        """Pausar migración"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        project.action_pause_migration()
        return request.redirect(f'/my/migration/{project_id}/monitor')

    @http.route('/my/migration/<int:project_id>/resume', type='http', auth='user', website=True, methods=['POST'])
    def portal_resume_migration(self, project_id, **kw):
        """Reanudar migración"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        project.action_resume_migration()
        return request.redirect(f'/my/migration/{project_id}/monitor')

    @http.route('/my/migration/<int:project_id>/cancel', type='http', auth='user', website=True, methods=['POST'])
    def portal_cancel_migration(self, project_id, **kw):
        """Cancelar migración"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        project.action_cancel_migration()
        return request.redirect(f'/my/migration/{project_id}')

    @http.route('/my/migration/<int:project_id>/delete', type='http', auth='user', website=True, methods=['POST'])
    def portal_delete_project(self, project_id, **kw):
        """Eliminar proyecto"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return request.redirect('/my/migration')

        if project.state in ('draft', 'cancelled', 'completed', 'error'):
            project.unlink()

        return request.redirect('/my/migration')

    # === API Endpoints ===

    @http.route('/my/migration/api/project/<int:project_id>/table/<int:mapping_id>/accept', type='json', auth='user')
    def api_accept_table_mapping(self, project_id, mapping_id):
        """Aceptar sugerencia de mapeo de tabla"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        mapping = request.env['migration.table.mapping'].browse(mapping_id)
        if mapping.project_id.id != project_id:
            return {'error': 'Mapeo no pertenece al proyecto'}

        mapping.action_accept_suggestion()

        return {'success': True, 'state': mapping.state}

    @http.route('/my/migration/api/project/<int:project_id>/table/<int:mapping_id>/ignore', type='json', auth='user')
    def api_ignore_table_mapping(self, project_id, mapping_id):
        """Ignorar tabla"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        mapping = request.env['migration.table.mapping'].browse(mapping_id)
        if mapping.project_id.id != project_id:
            return {'error': 'Mapeo no pertenece al proyecto'}

        mapping.action_ignore()

        return {'success': True, 'state': mapping.state}

    @http.route('/my/migration/api/project/<int:project_id>/table/<int:mapping_id>/set-topic', type='json', auth='user')
    def api_set_table_topic(self, project_id, mapping_id, topic_id, model_id=None):
        """Asignar tópico a una tabla"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        mapping = request.env['migration.table.mapping'].browse(mapping_id)
        if mapping.project_id.id != project_id:
            return {'error': 'Mapeo no pertenece al proyecto'}

        values = {'topic_id': int(topic_id) if topic_id else False}

        if model_id:
            values['target_model_id'] = int(model_id)
            values['state'] = 'mapped'

        mapping.write(values)

        return {
            'success': True,
            'state': mapping.state,
            'topic_name': mapping.topic_id.name if mapping.topic_id else None,
        }

    @http.route('/my/migration/api/project/<int:project_id>/table/<int:mapping_id>/fields', type='json', auth='user')
    def api_get_field_mappings(self, project_id, mapping_id):
        """Obtener mapeos de campos para una tabla"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        mapping = request.env['migration.table.mapping'].browse(mapping_id)
        if mapping.project_id.id != project_id:
            return {'error': 'Mapeo no pertenece al proyecto'}

        return {
            'table': mapping.get_portal_data(),
            'fields': [f.get_portal_data() for f in mapping.field_mapping_ids],
        }

    @http.route('/my/migration/api/project/<int:project_id>/field/<int:field_id>/update', type='json', auth='user')
    def api_update_field_mapping(self, project_id, field_id, **post):
        """Actualizar mapeo de campo"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        field_mapping = request.env['migration.field.mapping'].browse(field_id)
        if field_mapping.project_id.id != project_id:
            return {'error': 'Mapeo no pertenece al proyecto'}

        values = {}
        if 'target_field_id' in post:
            values['target_field_id'] = int(post['target_field_id']) if post['target_field_id'] else False
        if 'mapping_type' in post:
            values['mapping_type'] = post['mapping_type']
        if 'transform_function' in post:
            values['transform_function'] = post['transform_function']
        if 'state' in post:
            values['state'] = post['state']

        if values:
            field_mapping.write(values)

        return {'success': True, 'field': field_mapping.get_portal_data()}

    @http.route('/my/migration/api/project/<int:project_id>/tables', type='json', auth='user')
    def api_get_table_mappings(self, project_id):
        """Obtener todos los mapeos de tablas"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        return {
            'tables': [m.get_portal_data() for m in project.table_mapping_ids],
            'topics': request.env['migration.topic'].get_topics_for_portal(
                request.env.user.company_id.id
            ),
        }

    @http.route('/my/migration/api/project/<int:project_id>/migration-order', type='json', auth='user')
    def api_get_migration_order(self, project_id):
        """Obtener orden de migración"""
        project = request.env['migration.project'].browse(project_id)

        if project.partner_id != request.env.user.partner_id:
            return {'error': 'Acceso denegado'}

        resolver = request.env['migration.dependency.resolver']
        order = resolver.get_migration_order(project)

        return {'migration_order': order}
