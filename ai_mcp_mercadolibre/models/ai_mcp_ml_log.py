# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api, _


class AiMcpMlLog(models.Model):
    _name = 'ai.mcp.ml.log'
    _description = 'Log de Peticiones MCP MercadoLibre'
    _order = 'timestamp desc'
    _rec_name = 'display_name'

    # Relaciones
    server_id = fields.Many2one(
        'ai.mcp.ml.server',
        string='Servidor',
        required=True,
        ondelete='cascade',
        index=True,
    )
    endpoint_id = fields.Many2one(
        'ai.mcp.ml.endpoint',
        string='Endpoint',
        ondelete='set null',
        index=True,
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        ondelete='set null',
        index=True,
    )

    # Datos de la peticion
    timestamp = fields.Datetime(
        string='Fecha/Hora',
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    tool_name = fields.Char(
        string='Herramienta',
        required=True,
        index=True,
    )
    request_data = fields.Text(
        string='Request (JSON)',
        help='Datos enviados en la peticion',
    )
    response_data = fields.Text(
        string='Response (JSON)',
        help='Datos recibidos en la respuesta',
    )

    # Estado
    status = fields.Selection([
        ('success', 'Exitoso'),
        ('error', 'Error'),
    ], string='Estado', required=True, default='success', index=True)
    error_message = fields.Text(
        string='Mensaje de Error',
    )

    # Metricas
    duration = fields.Float(
        string='Duracion (s)',
        digits=(10, 3),
        help='Tiempo de ejecucion en segundos',
    )

    # Campos computados
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=True,
    )
    request_preview = fields.Char(
        string='Preview Request',
        compute='_compute_previews',
    )
    response_preview = fields.Char(
        string='Preview Response',
        compute='_compute_previews',
    )
    response_size = fields.Integer(
        string='Tamano Respuesta',
        compute='_compute_response_size',
    )

    @api.depends('tool_name', 'timestamp', 'status')
    def _compute_display_name(self):
        for record in self:
            status_icon = '✓' if record.status == 'success' else '✗'
            timestamp = record.timestamp.strftime('%H:%M:%S') if record.timestamp else ''
            record.display_name = f"{status_icon} {record.tool_name} [{timestamp}]"

    @api.depends('request_data', 'response_data')
    def _compute_previews(self):
        for record in self:
            # Preview de request
            if record.request_data:
                preview = record.request_data[:100]
                record.request_preview = preview + '...' if len(record.request_data) > 100 else preview
            else:
                record.request_preview = '-'

            # Preview de response
            if record.response_data:
                preview = record.response_data[:100]
                record.response_preview = preview + '...' if len(record.response_data) > 100 else preview
            else:
                record.response_preview = '-'

    @api.depends('response_data')
    def _compute_response_size(self):
        for record in self:
            record.response_size = len(record.response_data) if record.response_data else 0

    def get_request_json(self):
        """Obtener request como dict."""
        self.ensure_one()
        if self.request_data:
            try:
                return json.loads(self.request_data)
            except json.JSONDecodeError:
                return {}
        return {}

    def get_response_json(self):
        """Obtener response como dict."""
        self.ensure_one()
        if self.response_data:
            try:
                return json.loads(self.response_data)
            except json.JSONDecodeError:
                return {}
        return {}

    def action_view_full_request(self):
        """Ver request completo en modal."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request Completo'),
            'res_model': 'ai.mcp.ml.log',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'show_request': True},
        }

    def action_view_full_response(self):
        """Ver response completo en modal."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Response Completo'),
            'res_model': 'ai.mcp.ml.log',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'show_response': True},
        }

    def action_retry(self):
        """Reintentar la peticion."""
        self.ensure_one()
        if not self.endpoint_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No se puede reintentar'),
                    'message': _('El endpoint no esta disponible'),
                    'type': 'warning',
                }
            }

        request_data = self.get_request_json()
        try:
            result = self.server_id.execute_tool(
                self.tool_name,
                request_data,
                self.account_id.id if self.account_id else None
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reintento Exitoso'),
                    'message': _('La peticion se ejecuto correctamente'),
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error en Reintento'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    @api.model
    def cleanup_old_logs(self, days=30):
        """Limpiar logs antiguos."""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        old_logs = self.search([('timestamp', '<', cutoff_date)])
        count = len(old_logs)
        old_logs.unlink()
        return count

    @api.model
    def get_stats(self, server_id=None, days=7):
        """Obtener estadisticas de los ultimos N dias."""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)

        domain = [('timestamp', '>=', cutoff_date)]
        if server_id:
            domain.append(('server_id', '=', server_id))

        logs = self.search(domain)

        total = len(logs)
        success = len(logs.filtered(lambda l: l.status == 'success'))
        errors = len(logs.filtered(lambda l: l.status == 'error'))

        # Agrupar por herramienta
        by_tool = {}
        for log in logs:
            if log.tool_name not in by_tool:
                by_tool[log.tool_name] = {'total': 0, 'success': 0, 'error': 0}
            by_tool[log.tool_name]['total'] += 1
            if log.status == 'success':
                by_tool[log.tool_name]['success'] += 1
            else:
                by_tool[log.tool_name]['error'] += 1

        # Duracion promedio
        durations = [l.duration for l in logs if l.duration]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            'total': total,
            'success': success,
            'errors': errors,
            'success_rate': (success / total * 100) if total else 0,
            'by_tool': by_tool,
            'avg_duration': avg_duration,
        }
