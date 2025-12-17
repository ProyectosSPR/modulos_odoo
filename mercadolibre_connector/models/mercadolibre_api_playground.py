# -*- coding: utf-8 -*-

import json
import time
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MercadolibreApiPlayground(models.Model):
    _name = 'mercadolibre.api.playground'
    _description = 'API Playground MercadoLibre'
    _order = 'create_date desc'

    name = fields.Char(
        string='Nombre',
        required=True,
        default=lambda self: _('Nueva Request')
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='account_id.company_id',
        store=True,
        readonly=True
    )
    endpoint = fields.Char(
        string='Endpoint',
        required=True,
        default='/users/me',
        help='Ejemplo: /users/me, /items/search, etc.'
    )
    method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
    ], string='Método HTTP', required=True, default='GET')

    request_params = fields.Text(
        string='Query Parameters (JSON)',
        help='Parámetros de la URL en formato JSON. Ejemplo: {"q": "iphone", "limit": 10}'
    )
    request_body = fields.Text(
        string='Request Body (JSON)',
        help='Cuerpo del request en formato JSON (solo para POST/PUT)'
    )
    custom_headers = fields.Text(
        string='Headers Personalizados (JSON)',
        help='Headers adicionales en formato JSON (el token se agrega automáticamente)'
    )

    # Response fields
    response_code = fields.Integer(
        string='Código Response',
        readonly=True
    )
    response_body = fields.Text(
        string='Response Body',
        readonly=True
    )
    response_body_raw = fields.Text(
        string='Response Body Raw',
        readonly=True,
        help='Response sin formatear'
    )
    response_headers = fields.Text(
        string='Response Headers',
        readonly=True
    )
    response_size = fields.Char(
        string='Tamaño Response',
        readonly=True
    )
    error_message = fields.Text(
        string='Error',
        readonly=True
    )
    execution_time = fields.Float(
        string='Tiempo de Ejecución (s)',
        readonly=True,
        digits=(10, 3)
    )
    execution_time_display = fields.Char(
        string='Tiempo',
        compute='_compute_execution_time_display'
    )
    executed_at = fields.Datetime(
        string='Ejecutado el',
        readonly=True
    )
    full_url = fields.Char(
        string='URL Completa',
        readonly=True
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('success', 'Exitoso'),
        ('error', 'Error'),
    ], string='Estado', default='draft', readonly=True)

    notes = fields.Text(
        string='Notas'
    )

    @api.depends('execution_time')
    def _compute_execution_time_display(self):
        for record in self:
            if record.execution_time:
                if record.execution_time < 1:
                    record.execution_time_display = f'{int(record.execution_time * 1000)} ms'
                else:
                    record.execution_time_display = f'{record.execution_time:.2f} s'
            else:
                record.execution_time_display = ''

    def _get_status_color(self, code):
        """Retorna el color según el código HTTP"""
        if 200 <= code < 300:
            return 'green'
        elif 300 <= code < 400:
            return 'blue'
        elif 400 <= code < 500:
            return 'orange'
        else:
            return 'red'

    def _format_size(self, size_bytes):
        """Formatea el tamaño en bytes a formato legible"""
        if size_bytes < 1024:
            return f'{size_bytes} B'
        elif size_bytes < 1024 * 1024:
            return f'{size_bytes / 1024:.2f} KB'
        else:
            return f'{size_bytes / (1024 * 1024):.2f} MB'

    def action_execute(self):
        """Ejecuta el request API"""
        self.ensure_one()

        _logger.info('=' * 60)
        _logger.info('MERCADOLIBRE PLAYGROUND - INICIANDO REQUEST')
        _logger.info('=' * 60)

        if not self.account_id:
            raise ValidationError(_('Debe seleccionar una cuenta de MercadoLibre.'))

        if not self.account_id.has_valid_token:
            _logger.error('La cuenta %s no tiene un token válido', self.account_id.name)
            raise ValidationError(_('La cuenta no tiene un token válido.'))

        # Parse parámetros
        params = None
        if self.request_params:
            try:
                params = json.loads(self.request_params)
                _logger.info('Query Params: %s', json.dumps(params, indent=2))
            except json.JSONDecodeError as e:
                _logger.error('Error parseando query params: %s', str(e))
                raise ValidationError(_('Los parámetros no son un JSON válido.'))

        # Parse body
        body = None
        if self.request_body and self.method in ['POST', 'PUT']:
            try:
                body = json.loads(self.request_body)
                _logger.info('Request Body: %s', json.dumps(body, indent=2))
            except json.JSONDecodeError as e:
                _logger.error('Error parseando body: %s', str(e))
                raise ValidationError(_('El body no es un JSON válido.'))

        # Parse headers personalizados
        custom_headers = None
        if self.custom_headers:
            try:
                custom_headers = json.loads(self.custom_headers)
                _logger.info('Custom Headers: %s', json.dumps(custom_headers, indent=2))
            except json.JSONDecodeError as e:
                _logger.error('Error parseando headers: %s', str(e))
                raise ValidationError(_('Los headers no son un JSON válido.'))

        # Obtiene el token
        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            _logger.error('Error obteniendo token: %s', str(e))
            raise ValidationError(_(f'Error al obtener token: {str(e)}'))

        # Construye la URL
        base_url = 'https://api.mercadolibre.com'
        endpoint = self.endpoint if self.endpoint.startswith('/') else f'/{self.endpoint}'
        full_url = f'{base_url}{endpoint}'

        # Prepara headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if custom_headers:
            headers.update(custom_headers)

        _logger.info('-' * 60)
        _logger.info('REQUEST DETAILS:')
        _logger.info('-' * 60)
        _logger.info('Method: %s', self.method)
        _logger.info('URL: %s', full_url)
        _logger.info('Headers: %s', json.dumps({k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()}, indent=2))
        if params:
            _logger.info('Params: %s', json.dumps(params, indent=2))
        if body:
            _logger.info('Body: %s', json.dumps(body, indent=2))

        try:
            start_time = time.time()

            # Ejecuta el request directamente (sin wrapper para más control)
            response = requests.request(
                method=self.method,
                url=full_url,
                json=body if self.method in ['POST', 'PUT'] else None,
                params=params,
                headers=headers,
                timeout=30
            )

            execution_time = time.time() - start_time

            _logger.info('-' * 60)
            _logger.info('RESPONSE DETAILS:')
            _logger.info('-' * 60)
            _logger.info('Status Code: %s', response.status_code)
            _logger.info('Time: %.3f seconds', execution_time)
            _logger.info('Size: %s', self._format_size(len(response.content)))
            _logger.info('Headers: %s', json.dumps(dict(response.headers), indent=2))

            # Intenta parsear JSON
            response_raw_formatted = response.text
            try:
                response_data = response.json()
                response_body_formatted = json.dumps(response_data, indent=2, ensure_ascii=False)
                # También formatea el raw para mejor visualización
                response_raw_formatted = json.dumps(response_data, indent=2, ensure_ascii=False)
                _logger.info('Response Body (JSON):')
                _logger.info(response_body_formatted[:2000])  # Primeros 2000 chars
                if len(response_body_formatted) > 2000:
                    _logger.info('... (truncado, total: %d chars)', len(response_body_formatted))
            except json.JSONDecodeError:
                response_body_formatted = response.text
                response_raw_formatted = response.text
                _logger.info('Response Body (Text): %s', response.text[:500])

            # Guarda en el log del sistema
            self.env['mercadolibre.log'].sudo().create({
                'log_type': 'api_request',
                'level': 'success' if 200 <= response.status_code < 300 else 'error',
                'account_id': self.account_id.id,
                'message': f'Playground: {self.method} {endpoint} - {response.status_code}',
                'request_url': full_url,
                'request_method': self.method,
                'request_headers': json.dumps({k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()}),
                'request_body': json.dumps(body) if body else '',
                'response_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response_body_formatted[:10000],  # Limita a 10k chars
                'duration': execution_time,
            })

            # Actualiza el registro
            is_success = 200 <= response.status_code < 300
            self.write({
                'state': 'success' if is_success else 'error',
                'response_code': response.status_code,
                'response_body': response_body_formatted,
                'response_body_raw': response_raw_formatted,
                'response_headers': json.dumps(dict(response.headers), indent=2),
                'response_size': self._format_size(len(response.content)),
                'error_message': False if is_success else f'HTTP {response.status_code}',
                'execution_time': execution_time,
                'executed_at': fields.Datetime.now(),
                'full_url': response.url,
            })

            _logger.info('=' * 60)
            _logger.info('REQUEST COMPLETADO - Status: %s', response.status_code)
            _logger.info('=' * 60)

            # Recargar la vista para mostrar los resultados
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mercadolibre.api.playground',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except requests.exceptions.Timeout:
            _logger.error('TIMEOUT: El request excedió el tiempo límite')
            self.write({
                'state': 'error',
                'error_message': 'Timeout: El request excedió el tiempo límite de 30 segundos',
                'executed_at': fields.Datetime.now(),
                'full_url': full_url,
            })
            raise ValidationError(_('Timeout: El request excedió el tiempo límite.'))

        except requests.exceptions.ConnectionError as e:
            _logger.error('CONNECTION ERROR: %s', str(e))
            self.write({
                'state': 'error',
                'error_message': f'Error de conexión: {str(e)}',
                'executed_at': fields.Datetime.now(),
                'full_url': full_url,
            })
            raise ValidationError(_(f'Error de conexión: {str(e)}'))

        except Exception as e:
            _logger.exception('ERROR INESPERADO en playground')
            self.write({
                'state': 'error',
                'error_message': str(e),
                'executed_at': fields.Datetime.now(),
                'full_url': full_url,
            })
            raise ValidationError(_(f'Error: {str(e)}'))

    def action_reset(self):
        """Resetea los resultados"""
        self.write({
            'state': 'draft',
            'response_code': False,
            'response_body': False,
            'response_body_raw': False,
            'response_headers': False,
            'response_size': False,
            'error_message': False,
            'execution_time': False,
            'executed_at': False,
            'full_url': False,
        })
        # Recargar la vista
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.api.playground',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_duplicate(self):
        """Duplica el request"""
        self.ensure_one()
        new_record = self.copy({
            'name': f'{self.name} (Copia)',
            'state': 'draft',
            'response_code': False,
            'response_body': False,
            'response_body_raw': False,
            'response_headers': False,
            'response_size': False,
            'error_message': False,
            'execution_time': False,
            'executed_at': False,
            'full_url': False,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.api.playground',
            'res_id': new_record.id,
            'view_mode': 'form',
            'target': 'current',
        }
