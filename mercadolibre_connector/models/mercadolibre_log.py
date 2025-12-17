# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreLog(models.Model):
    _name = 'mercadolibre.log'
    _description = 'Log MercadoLibre'
    _order = 'create_date desc'
    _rec_name = 'message'

    log_type = fields.Selection([
        ('oauth', 'OAuth'),
        ('token_refresh', 'Refresco Token'),
        ('api_request', 'Request API'),
        ('api_response', 'Response API'),
        ('error', 'Error'),
        ('info', 'Info'),
        ('warning', 'Warning'),
    ], string='Tipo', required=True, index=True)

    level = fields.Selection([
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('success', 'Success'),
    ], string='Nivel', required=True, default='info', index=True)

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        ondelete='set null',
        index=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='account_id.company_id',
        store=True,
        readonly=True
    )
    message = fields.Text(
        string='Mensaje',
        required=True
    )
    request_url = fields.Char(
        string='URL Request'
    )
    request_method = fields.Char(
        string='Método HTTP'
    )
    request_headers = fields.Text(
        string='Request Headers'
    )
    request_body = fields.Text(
        string='Request Body'
    )
    response_code = fields.Integer(
        string='Código Response'
    )
    response_headers = fields.Text(
        string='Response Headers'
    )
    response_body = fields.Text(
        string='Response Body'
    )
    error_details = fields.Text(
        string='Detalles del Error'
    )
    duration = fields.Float(
        string='Duración (s)',
        help='Duración de la operación en segundos'
    )

    @api.model
    def log_api_request(self, account_id, method, url, headers=None, body=None):
        """Helper para registrar un request API"""
        return self.create({
            'log_type': 'api_request',
            'level': 'info',
            'account_id': account_id,
            'message': f'{method} {url}',
            'request_url': url,
            'request_method': method,
            'request_headers': str(headers) if headers else '',
            'request_body': str(body) if body else '',
        })

    @api.model
    def log_api_response(self, log_id, response_code, headers=None, body=None, duration=None):
        """Helper para actualizar el log con la respuesta"""
        log = self.browse(log_id)
        if log.exists():
            log.write({
                'response_code': response_code,
                'response_headers': str(headers) if headers else '',
                'response_body': str(body) if body else '',
                'duration': duration,
                'level': 'success' if 200 <= response_code < 300 else 'error',
            })

    @api.model
    def cron_cleanup_old_logs(self):
        """Cron: Limpia logs antiguos (más de 90 días)"""
        days_to_keep = int(self.env['ir.config_parameter'].sudo().get_param(
            'mercadolibre_connector.log_retention_days', default=90
        ))

        cutoff_date = fields.Datetime.subtract(fields.Datetime.now(), days=days_to_keep)

        old_logs = self.search([('create_date', '<', cutoff_date)])

        if old_logs:
            count = len(old_logs)
            old_logs.unlink()

            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f'Eliminados {count} logs antiguos')
