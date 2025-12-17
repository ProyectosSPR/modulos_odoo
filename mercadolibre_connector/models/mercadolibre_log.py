# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadoLibreLog(models.Model):
    _name = 'mercadolibre.log'
    _description = 'Log de Mercado Libre'
    _order = 'created_at desc'
    _rec_name = 'operation'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta',
        ondelete='cascade',
        index=True
    )
    log_type = fields.Selection(
        selection=[
            ('auth', 'Autenticación'),
            ('token_refresh', 'Refresh Token'),
            ('api_request', 'API Request'),
            ('api_response', 'API Response'),
            ('error', 'Error'),
            ('email', 'Email'),
            ('cron', 'Cron'),
            ('system', 'Sistema'),
        ],
        string='Tipo',
        required=True,
        index=True
    )
    level = fields.Selection(
        selection=[
            ('debug', 'Debug'),
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error'),
            ('critical', 'Critical'),
        ],
        string='Nivel',
        required=True,
        default='info',
        index=True
    )
    operation = fields.Char(
        string='Operación',
        index=True,
        help='Nombre de la operación (ej: refresh_token, GET /users/me)'
    )
    message = fields.Text(
        string='Mensaje',
        required=True
    )

    # HTTP Details
    endpoint = fields.Char(
        string='Endpoint',
        help='URL del endpoint de ML'
    )
    http_method = fields.Selection(
        selection=[
            ('get', 'GET'),
            ('post', 'POST'),
            ('put', 'PUT'),
            ('delete', 'DELETE'),
            ('patch', 'PATCH'),
        ],
        string='Método HTTP'
    )
    status_code = fields.Integer(
        string='Código HTTP',
        index=True
    )
    request_headers = fields.Text(
        string='Headers de Request'
    )
    request_body = fields.Text(
        string='Body de Request'
    )
    response_body = fields.Text(
        string='Body de Response'
    )
    response_time = fields.Float(
        string='Tiempo de Respuesta (s)',
        digits=(10, 3),
        help='Tiempo de respuesta en segundos'
    )

    # Error Details
    error_code = fields.Char(
        string='Código de Error',
        help='Código de error de ML'
    )
    error_message = fields.Text(
        string='Mensaje de Error'
    )
    stack_trace = fields.Text(
        string='Stack Trace'
    )

    # Context
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        ondelete='set null'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        ondelete='set null',
        index=True
    )
    ip_address = fields.Char(
        string='IP Address'
    )

    # Timestamp
    created_at = fields.Datetime(
        string='Fecha',
        default=fields.Datetime.now,
        required=True,
        index=True
    )

    # Computed fields for better UX
    level_color = fields.Integer(
        string='Color',
        compute='_compute_level_color'
    )
    short_message = fields.Char(
        string='Mensaje Corto',
        compute='_compute_short_message'
    )

    @api.depends('level')
    def _compute_level_color(self):
        color_map = {
            'debug': 4,      # Azul
            'info': 10,      # Verde
            'warning': 2,    # Naranja
            'error': 1,      # Rojo
            'critical': 9,   # Rojo oscuro
        }
        for record in self:
            record.level_color = color_map.get(record.level, 0)

    @api.depends('message')
    def _compute_short_message(self):
        for record in self:
            if record.message:
                record.short_message = record.message[:100] + '...' if len(record.message) > 100 else record.message
            else:
                record.short_message = ''

    @api.model
    def _cron_clean_old_logs(self):
        """Limpiar logs antiguos (más de 90 días)"""
        from datetime import timedelta

        cutoff_date = fields.Datetime.now() - timedelta(days=90)
        old_logs = self.search([('created_at', '<', cutoff_date)])
        count = len(old_logs)

        if count > 0:
            old_logs.unlink()
            self.env['mercadolibre.log'].create({
                'log_type': 'system',
                'level': 'info',
                'operation': 'clean_old_logs',
                'message': f'Limpiados {count} logs con más de 90 días',
            })

        return True

    def action_view_details(self):
        """Acción para ver detalles completos del log"""
        self.ensure_one()
        return {
            'name': _('Detalles del Log'),
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.log',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def log_api_call(self, account_id, endpoint, method, request_data=None, response_data=None,
                     status_code=None, response_time=None, error=None):
        """
        Helper method para crear logs de API calls fácilmente

        Example:
            self.env['mercadolibre.log'].log_api_call(
                account_id=account.id,
                endpoint='/users/me',
                method='GET',
                response_data={'id': 123, 'nickname': 'test'},
                status_code=200,
                response_time=0.5
            )
        """
        import json

        level = 'info' if not error and status_code and 200 <= status_code < 300 else 'error'
        log_type = 'api_response' if response_data else 'api_request'

        vals = {
            'account_id': account_id,
            'log_type': log_type,
            'level': level,
            'operation': f'{method.upper()} {endpoint}',
            'endpoint': endpoint,
            'http_method': method.lower(),
            'status_code': status_code,
            'response_time': response_time,
        }

        if request_data:
            vals['request_body'] = json.dumps(request_data, indent=2) if isinstance(request_data, dict) else str(request_data)

        if response_data:
            vals['response_body'] = json.dumps(response_data, indent=2)[:5000]  # Limitar a 5000 chars

        if error:
            vals.update({
                'error_message': str(error),
                'message': f'Error en {method.upper()} {endpoint}: {str(error)}'
            })
        else:
            vals['message'] = f'{method.upper()} {endpoint} - Status {status_code}'

        return self.create(vals)
