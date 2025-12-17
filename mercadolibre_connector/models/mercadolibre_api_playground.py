# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class MercadoLibreAPIPlayground(models.Model):
    _name = 'mercadolibre.api.playground'
    _description = 'API Playground de Mercado Libre'
    _order = 'last_executed_at desc, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de este test'
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta',
        required=True,
        ondelete='cascade'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # Request configuration
    endpoint = fields.Char(
        string='Endpoint',
        required=True,
        help='Endpoint relativo (ej: /users/me, /orders/search)'
    )
    full_url = fields.Char(
        string='URL Completa',
        compute='_compute_full_url'
    )
    http_method = fields.Selection(
        selection=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('DELETE', 'DELETE'),
            ('PATCH', 'PATCH'),
        ],
        string='Método HTTP',
        required=True,
        default='GET'
    )
    headers = fields.Text(
        string='Headers',
        help='Headers adicionales en formato JSON. Ejemplo: {"X-Custom-Header": "value"}',
        default='{}'
    )
    body = fields.Text(
        string='Body',
        help='Body del request en formato JSON'
    )
    query_params = fields.Text(
        string='Query Parameters',
        help='Query params en formato JSON. Ejemplo: {"status": "active", "limit": 50}',
        default='{}'
    )
    auto_auth = fields.Boolean(
        string='Autorización Automática',
        default=True,
        help='Si está activo, agregará automáticamente el header Authorization con el token de la cuenta'
    )

    # Response data
    last_response = fields.Text(
        string='Última Respuesta',
        readonly=True
    )
    last_status_code = fields.Integer(
        string='Código HTTP',
        readonly=True
    )
    last_executed_at = fields.Datetime(
        string='Última Ejecución',
        readonly=True
    )
    execution_time = fields.Float(
        string='Tiempo de Ejecución (s)',
        digits=(10, 3),
        readonly=True,
        help='Tiempo de respuesta en segundos'
    )

    # Organization
    is_favorite = fields.Boolean(
        string='Favorito',
        default=False
    )
    category = fields.Selection(
        selection=[
            ('users', 'Usuarios'),
            ('items', 'Productos'),
            ('orders', 'Órdenes'),
            ('questions', 'Preguntas'),
            ('oauth', 'OAuth'),
            ('notifications', 'Notificaciones'),
            ('shipping', 'Envíos'),
            ('payments', 'Pagos'),
            ('custom', 'Personalizado'),
        ],
        string='Categoría',
        default='custom'
    )
    notes = fields.Text(
        string='Notas'
    )

    # Computed fields for UI
    response_preview = fields.Char(
        string='Vista Previa',
        compute='_compute_response_preview'
    )
    status_badge = fields.Char(
        string='Estado Badge',
        compute='_compute_status_badge'
    )

    # Timestamps
    created_at = fields.Datetime(
        string='Creado el',
        default=fields.Datetime.now,
        readonly=True
    )
    updated_at = fields.Datetime(
        string='Actualizado el',
        default=fields.Datetime.now,
        readonly=True
    )

    @api.depends('endpoint')
    def _compute_full_url(self):
        base_url = 'https://api.mercadolibre.com'
        for record in self:
            if record.endpoint:
                endpoint = record.endpoint if record.endpoint.startswith('/') else f'/{record.endpoint}'
                record.full_url = f"{base_url}{endpoint}"
            else:
                record.full_url = base_url

    @api.depends('last_response')
    def _compute_response_preview(self):
        for record in self:
            if record.last_response:
                preview = record.last_response[:100]
                record.response_preview = preview + '...' if len(record.last_response) > 100 else preview
            else:
                record.response_preview = 'Sin respuesta'

    @api.depends('last_status_code')
    def _compute_status_badge(self):
        for record in self:
            if not record.last_status_code:
                record.status_badge = 'Nunca ejecutado'
            elif 200 <= record.last_status_code < 300:
                record.status_badge = f'✓ {record.last_status_code}'
            elif 400 <= record.last_status_code < 500:
                record.status_badge = f'⚠ {record.last_status_code}'
            elif 500 <= record.last_status_code < 600:
                record.status_badge = f'✗ {record.last_status_code}'
            else:
                record.status_badge = f'{record.last_status_code}'

    def write(self, vals):
        result = super(MercadoLibreAPIPlayground, self).write(vals)
        self.updated_at = fields.Datetime.now()
        return result

    @api.constrains('headers', 'body', 'query_params')
    def _check_json_fields(self):
        """Validar que los campos JSON sean válidos"""
        for record in self:
            for field_name, field_value in [
                ('headers', record.headers),
                ('body', record.body),
                ('query_params', record.query_params)
            ]:
                if field_value:
                    try:
                        json.loads(field_value)
                    except json.JSONDecodeError as e:
                        raise ValidationError(_(f'El campo {field_name} no es un JSON válido: {str(e)}'))

    def action_execute(self):
        """Ejecutar el request"""
        self.ensure_one()

        # Preparar datos
        try:
            headers = json.loads(self.headers) if self.headers else {}
        except json.JSONDecodeError:
            raise ValidationError(_('Headers no es un JSON válido'))

        try:
            body = json.loads(self.body) if self.body else None
        except json.JSONDecodeError:
            raise ValidationError(_('Body no es un JSON válido'))

        try:
            params = json.loads(self.query_params) if self.query_params else {}
        except json.JSONDecodeError:
            raise ValidationError(_('Query params no es un JSON válido'))

        # Ejecutar request usando el HTTP wrapper
        http = self.env['mercadolibre.http']

        result = http._request(
            account_id=self.account_id.id,
            endpoint=self.endpoint,
            method=self.http_method,
            body=body,
            headers=headers if not self.auto_auth else None,  # Si auto_auth, no pasar headers custom de Authorization
            params=params,
            retry_on_401=True,
            log_request=True
        )

        # Guardar resultado
        self.write({
            'last_response': json.dumps(result['data'], indent=2) if result['data'] else result['error'],
            'last_status_code': result['status_code'],
            'execution_time': result['response_time'],
            'last_executed_at': fields.Datetime.now(),
        })

        # Retornar acción para mostrar resultado
        if result['success']:
            message = _('Request ejecutado exitosamente')
            notification_type = 'success'
        else:
            message = _('Error: %s') % result['error']
            notification_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Resultado'),
                'message': message,
                'type': notification_type,
                'sticky': False,
            }
        }

    def action_toggle_favorite(self):
        """Marcar/desmarcar como favorito"""
        self.ensure_one()
        self.is_favorite = not self.is_favorite

    def action_duplicate(self):
        """Duplicar este test"""
        self.ensure_one()
        new_record = self.copy({
            'name': f"{self.name} (Copia)",
            'last_response': False,
            'last_status_code': False,
            'last_executed_at': False,
            'execution_time': False,
        })

        return {
            'name': _('Test Duplicado'),
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.api.playground',
            'res_id': new_record.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def create_template(self, template_name):
        """Crear templates predefinidos"""
        templates = {
            'get_user_me': {
                'name': 'Obtener Info Usuario',
                'endpoint': '/users/me',
                'http_method': 'GET',
                'category': 'users',
                'notes': 'Obtiene información del usuario autenticado',
            },
            'search_orders': {
                'name': 'Buscar Órdenes',
                'endpoint': '/orders/search',
                'http_method': 'GET',
                'category': 'orders',
                'query_params': json.dumps({
                    'seller': 'USER_ID',
                    'sort': 'date_desc',
                    'limit': 50
                }, indent=2),
                'notes': 'Buscar órdenes del vendedor. Reemplazar USER_ID.',
            },
            'get_item': {
                'name': 'Obtener Producto',
                'endpoint': '/items/ITEM_ID',
                'http_method': 'GET',
                'category': 'items',
                'notes': 'Obtener información de un producto. Reemplazar ITEM_ID.',
            },
            'search_questions': {
                'name': 'Buscar Preguntas',
                'endpoint': '/questions/search',
                'http_method': 'GET',
                'category': 'questions',
                'query_params': json.dumps({
                    'seller_id': 'USER_ID',
                    'status': 'UNANSWERED'
                }, indent=2),
                'notes': 'Buscar preguntas sin responder. Reemplazar USER_ID.',
            },
        }

        if template_name in templates:
            return templates[template_name]
        return None
