# -*- coding: utf-8 -*-
import json
import logging
import requests
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AiMcpMlServer(models.Model):
    _name = 'ai.mcp.ml.server'
    _description = 'Servidor MCP de MercadoLibre'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )
    server_type = fields.Selection([
        ('data', 'Datos (API MercadoLibre)'),
        ('docs', 'Documentacion (MCP Oficial)'),
    ], string='Tipo de Servidor', required=True, default='data')

    # Configuracion de cuenta
    default_account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta por Defecto',
        domain="[('state', '=', 'connected'), ('active', '=', True)]",
        help='Cuenta de MercadoLibre a usar por defecto para las peticiones',
    )
    allow_account_selection = fields.Boolean(
        string='Permitir Seleccion de Cuenta',
        default=True,
        help='Si esta activo, la IA puede elegir que cuenta usar en cada peticion',
    )

    # Configuracion MCP Docs
    docs_mcp_url = fields.Char(
        string='URL MCP Oficial',
        default='https://mcp.mercadolibre.com/mcp',
        help='URL del servidor MCP oficial de MercadoLibre para documentacion',
    )

    # Endpoints configurados (solo para tipo data)
    endpoint_ids = fields.One2many(
        'ai.mcp.ml.endpoint',
        'server_id',
        string='Endpoints',
    )
    endpoint_count = fields.Integer(
        string='Endpoints',
        compute='_compute_endpoint_count',
    )

    # Logs
    log_requests = fields.Boolean(
        string='Registrar Peticiones',
        default=True,
        help='Registrar todas las peticiones y respuestas en el log',
    )
    log_ids = fields.One2many(
        'ai.mcp.ml.log',
        'server_id',
        string='Logs',
    )
    log_count = fields.Integer(
        string='Logs',
        compute='_compute_log_count',
    )

    # Estadisticas
    total_requests = fields.Integer(
        string='Total Peticiones',
        compute='_compute_stats',
    )
    success_requests = fields.Integer(
        string='Peticiones Exitosas',
        compute='_compute_stats',
    )
    error_requests = fields.Integer(
        string='Peticiones con Error',
        compute='_compute_stats',
    )
    last_request_date = fields.Datetime(
        string='Ultima Peticion',
        compute='_compute_stats',
    )

    # Campos computados para UI
    available_accounts_count = fields.Integer(
        string='Cuentas Disponibles',
        compute='_compute_available_accounts',
    )

    @api.depends('endpoint_ids')
    def _compute_endpoint_count(self):
        for record in self:
            record.endpoint_count = len(record.endpoint_ids)

    @api.depends('log_ids')
    def _compute_log_count(self):
        for record in self:
            record.log_count = len(record.log_ids)

    @api.depends('log_ids', 'log_ids.status')
    def _compute_stats(self):
        for record in self:
            logs = record.log_ids
            record.total_requests = len(logs)
            record.success_requests = len(logs.filtered(lambda l: l.status == 'success'))
            record.error_requests = len(logs.filtered(lambda l: l.status == 'error'))
            last_log = logs.sorted('timestamp', reverse=True)[:1]
            record.last_request_date = last_log.timestamp if last_log else False

    def _compute_available_accounts(self):
        Account = self.env['mercadolibre.account']
        count = Account.search_count([
            ('state', '=', 'connected'),
            ('active', '=', True)
        ])
        for record in self:
            record.available_accounts_count = count

    def get_available_accounts(self):
        """Obtener lista de cuentas disponibles para seleccion."""
        self.ensure_one()
        Account = self.env['mercadolibre.account']
        accounts = Account.search([
            ('state', '=', 'connected'),
            ('active', '=', True)
        ])
        return [{
            'id': acc.id,
            'name': acc.name,
            'ml_user_id': acc.ml_user_id,
            'ml_nickname': acc.ml_nickname,
        } for acc in accounts]

    def get_account(self, account_id=None):
        """
        Obtener cuenta a usar para la peticion.

        Args:
            account_id: ID de cuenta especifica (opcional)

        Returns:
            mercadolibre.account record

        Raises:
            ValidationError si no hay cuenta disponible
        """
        self.ensure_one()
        Account = self.env['mercadolibre.account']

        if account_id:
            account = Account.browse(account_id)
            if not account.exists() or account.state != 'connected':
                raise ValidationError(_('La cuenta seleccionada no esta disponible'))
            return account

        if self.default_account_id and self.default_account_id.state == 'connected':
            return self.default_account_id

        # Buscar primera cuenta disponible
        account = Account.search([
            ('state', '=', 'connected'),
            ('active', '=', True)
        ], limit=1)

        if not account:
            raise ValidationError(_('No hay cuentas de MercadoLibre conectadas'))

        return account

    def get_valid_token(self, account_id=None):
        """
        Obtener token valido para hacer peticiones a la API.

        Args:
            account_id: ID de cuenta especifica (opcional)

        Returns:
            dict con access_token y datos de la cuenta
        """
        self.ensure_one()
        account = self.get_account(account_id)

        # Usar metodo del mercadolibre_connector
        token = account.get_valid_token()

        return {
            'access_token': token,
            'account_id': account.id,
            'account_name': account.name,
            'ml_user_id': account.ml_user_id,
            'ml_nickname': account.ml_nickname,
        }

    def get_tools_list(self):
        """
        Obtener lista de herramientas MCP disponibles.
        Formato compatible con MCP protocol.
        """
        self.ensure_one()
        tools = []

        if self.server_type == 'data':
            for endpoint in self.endpoint_ids.filtered('active'):
                tool = endpoint._to_mcp_tool()
                tools.append(tool)

        elif self.server_type == 'docs':
            # Herramientas del MCP oficial
            tools = [
                {
                    'name': 'search_documentation',
                    'description': 'Buscar en la documentacion oficial de MercadoLibre API. Retorna endpoints y guias relevantes.',
                    'inputSchema': {
                        'type': 'object',
                        'properties': {
                            'query': {
                                'type': 'string',
                                'description': 'Termino de busqueda (ej: orders, shipments, items)'
                            }
                        },
                        'required': ['query']
                    }
                },
                {
                    'name': 'get_documentation_page',
                    'description': 'Obtener contenido completo de una pagina de documentacion de MercadoLibre.',
                    'inputSchema': {
                        'type': 'object',
                        'properties': {
                            'path': {
                                'type': 'string',
                                'description': 'Ruta de la pagina de documentacion'
                            }
                        },
                        'required': ['path']
                    }
                }
            ]

        # Agregar herramienta de seleccion de cuenta si esta habilitado
        if self.allow_account_selection:
            tools.insert(0, {
                'name': 'list_accounts',
                'description': 'Listar las cuentas de MercadoLibre disponibles para consultar.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {}
                }
            })

        return tools

    def execute_tool(self, tool_name, arguments, account_id=None):
        """
        Ejecutar una herramienta MCP.

        Args:
            tool_name: Nombre de la herramienta
            arguments: Diccionario de argumentos
            account_id: ID de cuenta (opcional)

        Returns:
            dict con resultado de la ejecucion
        """
        self.ensure_one()
        start_time = datetime.now()
        result = None
        status = 'success'
        error_message = None

        try:
            # Herramienta especial: listar cuentas
            if tool_name == 'list_accounts':
                result = {
                    'accounts': self.get_available_accounts(),
                    'default_account_id': self.default_account_id.id if self.default_account_id else None,
                }
                return result

            if self.server_type == 'data':
                result = self._execute_data_tool(tool_name, arguments, account_id)
            elif self.server_type == 'docs':
                result = self._execute_docs_tool(tool_name, arguments, account_id)

        except Exception as e:
            status = 'error'
            error_message = str(e)
            _logger.error(f"Error ejecutando tool {tool_name}: {e}")
            result = {'error': str(e)}

        finally:
            # Registrar en log
            if self.log_requests:
                duration = (datetime.now() - start_time).total_seconds()
                self._create_log(
                    tool_name=tool_name,
                    request_data=arguments,
                    response_data=result,
                    status=status,
                    error_message=error_message,
                    duration=duration,
                    account_id=account_id,
                )

        return result

    def _execute_data_tool(self, tool_name, arguments, account_id=None):
        """Ejecutar herramienta de datos (API MercadoLibre)."""
        # Buscar endpoint configurado
        endpoint = self.endpoint_ids.filtered(
            lambda e: e.code == tool_name and e.active
        )
        if not endpoint:
            raise ValidationError(_(f'Endpoint "{tool_name}" no encontrado'))

        endpoint = endpoint[0]
        return endpoint.execute(arguments, account_id)

    def _execute_docs_tool(self, tool_name, arguments, account_id=None):
        """Ejecutar herramienta de documentacion (MCP oficial)."""
        token_info = self.get_valid_token(account_id)

        headers = {
            'Authorization': f'Bearer {token_info["access_token"]}',
            'Content-Type': 'application/json',
        }

        # Llamar al MCP oficial de MercadoLibre
        payload = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': tool_name,
                'arguments': arguments
            },
            'id': 1
        }

        try:
            response = requests.post(
                self.docs_mcp_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                raise ValidationError(data['error'].get('message', 'Error desconocido'))

            return data.get('result', data)

        except requests.RequestException as e:
            _logger.error(f"Error llamando MCP docs: {e}")
            raise ValidationError(_(f'Error conectando con MCP oficial: {str(e)}'))

    def _create_log(self, tool_name, request_data, response_data, status,
                    error_message=None, duration=0, account_id=None, endpoint_id=None):
        """Crear registro de log."""
        self.env['ai.mcp.ml.log'].sudo().create({
            'server_id': self.id,
            'endpoint_id': endpoint_id,
            'account_id': account_id,
            'tool_name': tool_name,
            'request_data': json.dumps(request_data, ensure_ascii=False, indent=2) if request_data else '{}',
            'response_data': json.dumps(response_data, ensure_ascii=False, indent=2) if response_data else '{}',
            'status': status,
            'error_message': error_message,
            'duration': duration,
        })

    # === ACCIONES DE UI ===

    def action_view_endpoints(self):
        """Abrir vista de endpoints."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Endpoints'),
            'res_model': 'ai.mcp.ml.endpoint',
            'view_mode': 'tree,form',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id},
        }

    def action_view_logs(self):
        """Abrir vista de logs."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Logs MCP'),
            'res_model': 'ai.mcp.ml.log',
            'view_mode': 'tree,form',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id},
        }

    def action_test_connection(self):
        """Probar conexion con el servidor."""
        self.ensure_one()
        try:
            if self.server_type == 'data':
                # Probar obteniendo token
                token_info = self.get_valid_token()
                message = _(
                    'Conexion exitosa!\n\n'
                    'Cuenta: %(name)s\n'
                    'Usuario ML: %(nickname)s\n'
                    'Endpoints activos: %(count)d'
                ) % {
                    'name': token_info['account_name'],
                    'nickname': token_info['ml_nickname'],
                    'count': len(self.endpoint_ids.filtered('active')),
                }
            else:
                # Probar MCP oficial
                token_info = self.get_valid_token()
                result = self._execute_docs_tool('search_documentation', {'query': 'orders'})
                message = _(
                    'Conexion con MCP oficial exitosa!\n\n'
                    'Cuenta: %(name)s\n'
                    'URL: %(url)s'
                ) % {
                    'name': token_info['account_name'],
                    'url': self.docs_mcp_url,
                }

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Test de Conexion'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error de Conexion'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_clear_logs(self):
        """Limpiar todos los logs del servidor."""
        self.ensure_one()
        self.log_ids.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Logs Limpiados'),
                'message': _('Se han eliminado todos los logs del servidor.'),
                'type': 'success',
                'sticky': False,
            }
        }
