# -*- coding: utf-8 -*-
import json
import re
import logging
import requests
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

ML_API_BASE = 'https://api.mercadolibre.com'


class AiMcpMlEndpoint(models.Model):
    _name = 'ai.mcp.ml.endpoint'
    _description = 'Endpoint MCP de MercadoLibre'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo del endpoint',
    )
    code = fields.Char(
        string='Codigo',
        required=True,
        help='Codigo unico para identificar el endpoint (ej: get_orders)',
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )
    server_id = fields.Many2one(
        'ai.mcp.ml.server',
        string='Servidor',
        required=True,
        ondelete='cascade',
    )

    # Configuracion del endpoint
    description = fields.Text(
        string='Descripcion para IA',
        required=True,
        help='Descripcion clara de que hace este endpoint. La IA usara esto para decidir cuando usarlo.',
    )
    ml_endpoint = fields.Char(
        string='Endpoint ML API',
        required=True,
        help='Ruta del endpoint en la API de MercadoLibre (ej: /orders/search, /orders/{order_id})',
    )
    method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
    ], string='Metodo HTTP', required=True, default='GET')

    # Parametros
    parameter_ids = fields.One2many(
        'ai.mcp.ml.endpoint.parameter',
        'endpoint_id',
        string='Parametros',
    )
    requires_seller_id = fields.Boolean(
        string='Requiere Seller ID',
        default=False,
        help='Agregar automaticamente el seller_id del usuario autenticado',
    )

    # Sistema de dependencias
    depends_on_id = fields.Many2one(
        'ai.mcp.ml.endpoint',
        string='Depende de',
        domain="[('server_id', '=', server_id), ('id', '!=', id)]",
        help='Endpoint que debe consultarse primero para obtener datos necesarios',
    )
    depends_on_field = fields.Char(
        string='Campo Necesario',
        help='Campo de la respuesta del endpoint dependencia que se necesita (ej: shipping.id, results[].id)',
    )
    dependency_type = fields.Selection([
        ('required', 'Requerido'),
        ('optional', 'Opcional'),
    ], string='Tipo de Dependencia', default='optional')
    ai_hint = fields.Text(
        string='Instrucciones para IA',
        help='Instrucciones adicionales para la IA sobre como usar este endpoint',
    )

    # Ejemplo de respuesta
    response_example = fields.Text(
        string='Ejemplo de Respuesta',
        help='JSON de ejemplo de la respuesta para referencia de la IA',
    )
    response_fields = fields.Text(
        string='Campos Importantes',
        help='JSON describiendo los campos mas importantes de la respuesta',
    )

    # Estadisticas
    use_count = fields.Integer(
        string='Veces Usado',
        default=0,
    )
    last_used = fields.Datetime(
        string='Ultimo Uso',
    )
    avg_duration = fields.Float(
        string='Duracion Promedio (s)',
        digits=(10, 3),
    )

    _sql_constraints = [
        ('code_server_unique', 'UNIQUE(code, server_id)',
         'El codigo del endpoint debe ser unico por servidor'),
    ]

    @api.constrains('code')
    def _check_code(self):
        """Validar que el codigo sea un identificador valido."""
        for record in self:
            if not re.match(r'^[a-z][a-z0-9_]*$', record.code):
                raise ValidationError(_(
                    'El codigo debe comenzar con letra minuscula y '
                    'contener solo letras minusculas, numeros y guiones bajos'
                ))

    def _to_mcp_tool(self):
        """
        Convertir endpoint a formato de herramienta MCP.

        Returns:
            dict con formato MCP tool
        """
        self.ensure_one()

        # Construir descripcion con dependencias
        description = self.description or ''
        if self.depends_on_id:
            dep_info = f"\n\nDEPENDENCIA: "
            if self.dependency_type == 'required':
                dep_info += f"Requiere primero usar '{self.depends_on_id.code}' para obtener '{self.depends_on_field}'."
            else:
                dep_info += f"Si no tienes '{self.depends_on_field}', puedes obtenerlo de '{self.depends_on_id.code}'."
            description += dep_info

        if self.ai_hint:
            description += f"\n\nNOTA: {self.ai_hint}"

        # Construir schema de parametros
        properties = {}
        required = []

        # Agregar account_id si el servidor permite seleccion
        if self.server_id.allow_account_selection:
            properties['account_id'] = {
                'type': 'integer',
                'description': 'ID de la cuenta de MercadoLibre a usar (opcional, usa la predeterminada si no se especifica)',
            }

        # Agregar parametros configurados
        for param in self.parameter_ids:
            prop = {
                'type': param.param_type,
                'description': param.description or param.name,
            }
            if param.default_value:
                prop['default'] = param.default_value
            if param.enum_values:
                try:
                    prop['enum'] = json.loads(param.enum_values)
                except json.JSONDecodeError:
                    pass

            # Agregar info de dependencia
            if param.from_dependency and param.dependency_path:
                prop['description'] += f" (Obtener de: {self.depends_on_id.code} -> {param.dependency_path})"

            properties[param.name] = prop
            if param.required and not param.from_dependency:
                required.append(param.name)

        tool = {
            'name': self.code,
            'description': description,
            'inputSchema': {
                'type': 'object',
                'properties': properties,
            }
        }

        if required:
            tool['inputSchema']['required'] = required

        # Agregar metadata adicional
        tool['_metadata'] = {
            'endpoint': self.ml_endpoint,
            'method': self.method,
            'requires_seller_id': self.requires_seller_id,
        }

        if self.depends_on_id:
            tool['_metadata']['depends_on'] = {
                'endpoint': self.depends_on_id.code,
                'field': self.depends_on_field,
                'type': self.dependency_type,
            }

        return tool

    def execute(self, arguments, account_id=None):
        """
        Ejecutar el endpoint con los argumentos dados.

        Args:
            arguments: dict con los argumentos
            account_id: ID de cuenta especifica (opcional)

        Returns:
            dict con la respuesta de la API
        """
        self.ensure_one()
        start_time = datetime.now()

        # Obtener account_id de argumentos si no se especifica
        if not account_id and 'account_id' in arguments:
            account_id = arguments.pop('account_id')

        # Obtener token
        token_info = self.server_id.get_valid_token(account_id)

        # Construir URL
        url = self._build_url(arguments, token_info)

        # Construir headers
        headers = {
            'Authorization': f'Bearer {token_info["access_token"]}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # Construir parametros/body
        params = None
        body = None

        if self.method == 'GET':
            params = self._build_params(arguments, token_info)
        else:
            body = self._build_body(arguments)

        # Ejecutar request
        try:
            _logger.info(f"MCP ML Request: {self.method} {url}")
            response = requests.request(
                method=self.method,
                url=url,
                headers=headers,
                params=params,
                json=body,
                timeout=30
            )

            # Log de respuesta
            _logger.info(f"MCP ML Response: {response.status_code}")

            # Parsear respuesta
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise ValidationError(_(
                    'Error %(code)s de MercadoLibre: %(message)s'
                ) % {
                    'code': response.status_code,
                    'message': error_data.get('message', response.text),
                })

            result = response.json() if response.content else {}

            # Actualizar estadisticas
            duration = (datetime.now() - start_time).total_seconds()
            self._update_stats(duration)

            return result

        except requests.RequestException as e:
            _logger.error(f"Error en request MCP ML: {e}")
            raise ValidationError(_(f'Error de conexion: {str(e)}'))

    def _build_url(self, arguments, token_info):
        """Construir URL del endpoint reemplazando variables."""
        url = f"{ML_API_BASE}{self.ml_endpoint}"

        # Reemplazar variables en la URL (ej: {order_id})
        for param in self.parameter_ids.filtered(lambda p: p.is_path_param):
            placeholder = '{' + param.name + '}'
            if placeholder in url:
                value = arguments.get(param.name, '')
                url = url.replace(placeholder, str(value))
                # Remover de arguments para no enviarlo como query param
                arguments.pop(param.name, None)

        return url

    def _build_params(self, arguments, token_info):
        """Construir query parameters."""
        params = {}

        # Agregar seller_id si es requerido
        if self.requires_seller_id:
            params['seller'] = token_info['ml_user_id']

        # Agregar parametros del request
        for param in self.parameter_ids.filtered(lambda p: not p.is_path_param):
            if param.name in arguments:
                params[param.name] = arguments[param.name]
            elif param.default_value:
                params[param.name] = param.default_value

        return params if params else None

    def _build_body(self, arguments):
        """Construir body para POST/PUT."""
        body = {}
        for param in self.parameter_ids:
            if param.name in arguments:
                body[param.name] = arguments[param.name]
        return body if body else None

    def _update_stats(self, duration):
        """Actualizar estadisticas del endpoint."""
        # Calcular nuevo promedio
        total = self.use_count * self.avg_duration + duration
        new_count = self.use_count + 1
        new_avg = total / new_count

        self.write({
            'use_count': new_count,
            'last_used': fields.Datetime.now(),
            'avg_duration': new_avg,
        })

    # === ACCIONES DE UI ===

    def action_test_endpoint(self):
        """Probar el endpoint con valores de ejemplo."""
        self.ensure_one()
        # Construir argumentos de ejemplo
        test_args = {}
        for param in self.parameter_ids:
            if param.default_value:
                test_args[param.name] = param.default_value
            elif param.required:
                # Valor de ejemplo segun tipo
                if param.param_type == 'string':
                    test_args[param.name] = 'test'
                elif param.param_type == 'integer':
                    test_args[param.name] = 1
                elif param.param_type == 'boolean':
                    test_args[param.name] = True

        try:
            result = self.execute(test_args)
            # Mostrar resultado en notificacion
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Test Exitoso'),
                    'message': _('El endpoint funciona correctamente. Revisa los logs para ver la respuesta.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error en Test'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_view_logs(self):
        """Ver logs de este endpoint."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Logs del Endpoint'),
            'res_model': 'ai.mcp.ml.log',
            'view_mode': 'tree,form',
            'domain': [('endpoint_id', '=', self.id)],
        }

    def action_copy_as_json(self):
        """Copiar configuracion como JSON para referencia."""
        self.ensure_one()
        tool = self._to_mcp_tool()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('JSON del Tool'),
                'message': json.dumps(tool, indent=2, ensure_ascii=False),
                'type': 'info',
                'sticky': True,
            }
        }
