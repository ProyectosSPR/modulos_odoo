# -*- coding: utf-8 -*-

import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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
    response_code = fields.Integer(
        string='Código Response',
        readonly=True
    )
    response_body = fields.Text(
        string='Response Body',
        readonly=True
    )
    response_headers = fields.Text(
        string='Response Headers',
        readonly=True
    )
    error_message = fields.Text(
        string='Error',
        readonly=True
    )
    execution_time = fields.Float(
        string='Tiempo de Ejecución (s)',
        readonly=True
    )
    executed_at = fields.Datetime(
        string='Ejecutado el',
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

    def action_execute(self):
        """Ejecuta el request API"""
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise ValidationError(_('La cuenta no tiene un token válido.'))

        # Parse parámetros
        params = None
        if self.request_params:
            try:
                params = json.loads(self.request_params)
            except json.JSONDecodeError:
                raise ValidationError(_('Los parámetros no son un JSON válido.'))

        # Parse body
        body = None
        if self.request_body and self.method in ['POST', 'PUT']:
            try:
                body = json.loads(self.request_body)
            except json.JSONDecodeError:
                raise ValidationError(_('El body no es un JSON válido.'))

        # Parse headers personalizados
        custom_headers = None
        if self.custom_headers:
            try:
                custom_headers = json.loads(self.custom_headers)
            except json.JSONDecodeError:
                raise ValidationError(_('Los headers no son un JSON válido.'))

        # Ejecuta el request usando el wrapper HTTP
        http_wrapper = self.env['mercadolibre.http']

        try:
            import time
            start_time = time.time()

            response = http_wrapper._request(
                account_id=self.account_id.id,
                endpoint=self.endpoint,
                method=self.method,
                body=body,
                params=params,
                headers=custom_headers,
                log_request=True
            )

            execution_time = time.time() - start_time

            # Actualiza el registro con la respuesta exitosa
            self.write({
                'state': 'success',
                'response_code': response.get('status_code'),
                'response_body': json.dumps(response.get('data'), indent=2, ensure_ascii=False),
                'response_headers': json.dumps(dict(response.get('headers', {})), indent=2),
                'error_message': False,
                'execution_time': execution_time,
                'executed_at': fields.Datetime.now(),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Request Exitoso'),
                    'message': _('El request se ejecutó correctamente.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            # Actualiza el registro con el error
            self.write({
                'state': 'error',
                'error_message': str(e),
                'executed_at': fields.Datetime.now(),
            })

            raise ValidationError(_(f'Error al ejecutar el request: {str(e)}'))

    def action_reset(self):
        """Resetea los resultados"""
        self.write({
            'state': 'draft',
            'response_code': False,
            'response_body': False,
            'response_headers': False,
            'error_message': False,
            'execution_time': False,
            'executed_at': False,
        })

    def action_duplicate(self):
        """Duplica el request"""
        self.ensure_one()
        new_record = self.copy({
            'name': f'{self.name} (Copia)',
            'state': 'draft',
            'response_code': False,
            'response_body': False,
            'response_headers': False,
            'error_message': False,
            'execution_time': False,
            'executed_at': False,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.api.playground',
            'res_id': new_record.id,
            'view_mode': 'form',
            'target': 'current',
        }
