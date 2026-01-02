# -*- coding: utf-8 -*-
import json
import logging
from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class McpMlController(http.Controller):
    """
    Controlador MCP para MercadoLibre.

    Implementa el protocolo MCP (Model Context Protocol) para exponer
    herramientas de consulta a la API de MercadoLibre.

    Endpoints:
        - POST /ai/mcp/ml/data     : Servidor MCP de datos
        - POST /ai/mcp/ml/docs     : Servidor MCP de documentacion
        - GET  /ai/mcp/ml/tools    : Lista de herramientas disponibles
        - GET  /ai/mcp/ml/status   : Estado del servidor
        - POST /ai/mcp/ml/test     : Probar herramienta
    """

    def _json_response(self, data, status=200):
        """Generar respuesta JSON estandar."""
        return Response(
            json.dumps(data, ensure_ascii=False, indent=2),
            status=status,
            content_type='application/json',
        )

    def _mcp_response(self, result=None, error=None, request_id=1):
        """Generar respuesta en formato JSON-RPC 2.0 (MCP)."""
        response = {
            'jsonrpc': '2.0',
            'id': request_id,
        }
        if error:
            response['error'] = {
                'code': -32000,
                'message': str(error),
            }
        else:
            response['result'] = result
        return self._json_response(response)

    def _get_server(self, server_type):
        """Obtener servidor MCP por tipo."""
        Server = request.env['ai.mcp.ml.server'].sudo()
        server = Server.search([
            ('server_type', '=', server_type),
            ('active', '=', True),
        ], limit=1)
        return server

    # =========================================================================
    # ENDPOINT: Servidor MCP de Datos
    # =========================================================================

    @http.route('/ai/mcp/ml/data', type='json', auth='public', csrf=False, methods=['POST'])
    def mcp_data_handler(self, **kwargs):
        """
        Servidor MCP principal para datos de MercadoLibre.

        Maneja peticiones JSON-RPC 2.0 del protocolo MCP:
        - initialize: Inicializar conexion
        - tools/list: Listar herramientas disponibles
        - tools/call: Ejecutar herramienta
        """
        try:
            # Obtener datos del request
            json_data = request.jsonrequest
            method = json_data.get('method', '')
            params = json_data.get('params', {})
            request_id = json_data.get('id', 1)

            _logger.info(f"MCP Data Request: method={method}, params={params}")

            server = self._get_server('data')
            if not server:
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32001,
                        'message': 'No hay servidor MCP de datos configurado',
                    }
                }

            # Manejar metodos MCP
            if method == 'initialize':
                return self._handle_initialize(server, request_id)

            elif method == 'tools/list':
                return self._handle_tools_list(server, request_id)

            elif method == 'tools/call':
                tool_name = params.get('name', '')
                arguments = params.get('arguments', {})
                return self._handle_tools_call(server, tool_name, arguments, request_id)

            elif method == 'resources/list':
                # MCP resources (no implementado por ahora)
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': {'resources': []}
                }

            elif method == 'prompts/list':
                # MCP prompts (no implementado por ahora)
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': {'prompts': []}
                }

            else:
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32601,
                        'message': f'Metodo no soportado: {method}',
                    }
                }

        except Exception as e:
            _logger.error(f"Error en MCP Data: {e}", exc_info=True)
            return {
                'jsonrpc': '2.0',
                'id': request_id if 'request_id' in dir() else 1,
                'error': {
                    'code': -32000,
                    'message': str(e),
                }
            }

    # =========================================================================
    # ENDPOINT: Servidor MCP de Documentacion
    # =========================================================================

    @http.route('/ai/mcp/ml/docs', type='json', auth='public', csrf=False, methods=['POST'])
    def mcp_docs_handler(self, **kwargs):
        """
        Servidor MCP para documentacion de MercadoLibre.
        Actua como proxy al servidor MCP oficial.
        """
        try:
            json_data = request.jsonrequest
            method = json_data.get('method', '')
            params = json_data.get('params', {})
            request_id = json_data.get('id', 1)

            _logger.info(f"MCP Docs Request: method={method}")

            server = self._get_server('docs')
            if not server:
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32001,
                        'message': 'No hay servidor MCP de documentacion configurado',
                    }
                }

            if method == 'initialize':
                return self._handle_initialize(server, request_id, is_docs=True)

            elif method == 'tools/list':
                return self._handle_tools_list(server, request_id)

            elif method == 'tools/call':
                tool_name = params.get('name', '')
                arguments = params.get('arguments', {})
                return self._handle_tools_call(server, tool_name, arguments, request_id)

            else:
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32601,
                        'message': f'Metodo no soportado: {method}',
                    }
                }

        except Exception as e:
            _logger.error(f"Error en MCP Docs: {e}", exc_info=True)
            return {
                'jsonrpc': '2.0',
                'id': 1,
                'error': {
                    'code': -32000,
                    'message': str(e),
                }
            }

    # =========================================================================
    # HANDLERS MCP
    # =========================================================================

    def _handle_initialize(self, server, request_id, is_docs=False):
        """Manejar inicializacion MCP."""
        server_type = 'documentacion' if is_docs else 'datos'
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'protocolVersion': '2024-11-05',
                'serverInfo': {
                    'name': f'mercadolibre-{server_type}',
                    'version': '1.0.0',
                },
                'capabilities': {
                    'tools': {},
                    'resources': {},
                    'prompts': {},
                }
            }
        }

    def _handle_tools_list(self, server, request_id):
        """Manejar listado de herramientas."""
        tools = server.get_tools_list()
        return {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'tools': tools
            }
        }

    def _handle_tools_call(self, server, tool_name, arguments, request_id):
        """Manejar ejecucion de herramienta."""
        try:
            result = server.execute_tool(tool_name, arguments)
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'content': [
                        {
                            'type': 'text',
                            'text': json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }
        except Exception as e:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32000,
                    'message': str(e),
                }
            }

    # =========================================================================
    # ENDPOINTS AUXILIARES (para testing y debug)
    # =========================================================================

    @http.route('/ai/mcp/ml/tools', type='http', auth='public', csrf=False, methods=['GET'])
    def get_tools_list(self, server_type='data', **kwargs):
        """
        Listar herramientas disponibles (para debug).

        Query params:
            - server_type: 'data' o 'docs'
        """
        try:
            server = self._get_server(server_type)
            if not server:
                return self._json_response({
                    'error': f'No hay servidor MCP de tipo {server_type} configurado'
                }, 404)

            tools = server.get_tools_list()
            return self._json_response({
                'server': server.name,
                'type': server_type,
                'tools_count': len(tools),
                'tools': tools,
            })

        except Exception as e:
            return self._json_response({'error': str(e)}, 500)

    @http.route('/ai/mcp/ml/status', type='http', auth='public', csrf=False, methods=['GET'])
    def get_status(self, **kwargs):
        """Obtener estado de los servidores MCP."""
        try:
            Server = request.env['ai.mcp.ml.server'].sudo()
            servers = Server.search([('active', '=', True)])

            status = {
                'status': 'ok',
                'servers': [],
            }

            for server in servers:
                server_info = {
                    'id': server.id,
                    'name': server.name,
                    'type': server.server_type,
                    'active': server.active,
                    'endpoints_count': server.endpoint_count if server.server_type == 'data' else 2,
                    'total_requests': server.total_requests,
                    'success_requests': server.success_requests,
                    'error_requests': server.error_requests,
                    'last_request': server.last_request_date.isoformat() if server.last_request_date else None,
                }

                # Info de cuenta
                if server.default_account_id:
                    server_info['default_account'] = {
                        'id': server.default_account_id.id,
                        'name': server.default_account_id.name,
                        'ml_nickname': server.default_account_id.ml_nickname,
                    }

                status['servers'].append(server_info)

            return self._json_response(status)

        except Exception as e:
            return self._json_response({
                'status': 'error',
                'error': str(e)
            }, 500)

    @http.route('/ai/mcp/ml/test', type='json', auth='public', csrf=False, methods=['POST'])
    def test_tool(self, **kwargs):
        """
        Probar una herramienta directamente.

        Body:
            {
                "server_type": "data",
                "tool_name": "get_orders",
                "arguments": {"status": "paid", "limit": 5}
            }
        """
        try:
            json_data = request.jsonrequest
            server_type = json_data.get('server_type', 'data')
            tool_name = json_data.get('tool_name', '')
            arguments = json_data.get('arguments', {})
            account_id = json_data.get('account_id')

            if not tool_name:
                return {'error': 'tool_name es requerido'}

            server = self._get_server(server_type)
            if not server:
                return {'error': f'No hay servidor MCP de tipo {server_type} configurado'}

            result = server.execute_tool(tool_name, arguments, account_id)
            return {
                'success': True,
                'tool_name': tool_name,
                'result': result,
            }

        except Exception as e:
            _logger.error(f"Error en test tool: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai/mcp/ml/accounts', type='http', auth='public', csrf=False, methods=['GET'])
    def get_accounts(self, **kwargs):
        """Listar cuentas de MercadoLibre disponibles."""
        try:
            Account = request.env['mercadolibre.account'].sudo()
            accounts = Account.search([
                ('state', '=', 'connected'),
                ('active', '=', True),
            ])

            return self._json_response({
                'accounts': [{
                    'id': acc.id,
                    'name': acc.name,
                    'ml_user_id': acc.ml_user_id,
                    'ml_nickname': acc.ml_nickname,
                    'ml_email': acc.ml_email,
                } for acc in accounts]
            })

        except Exception as e:
            return self._json_response({'error': str(e)}, 500)

    @http.route('/ai/mcp/ml/logs', type='http', auth='public', csrf=False, methods=['GET'])
    def get_logs(self, server_type='data', limit=50, **kwargs):
        """
        Obtener logs recientes.

        Query params:
            - server_type: 'data' o 'docs'
            - limit: cantidad de logs (default 50)
        """
        try:
            server = self._get_server(server_type)
            if not server:
                return self._json_response({
                    'error': f'No hay servidor MCP de tipo {server_type}'
                }, 404)

            logs = request.env['ai.mcp.ml.log'].sudo().search([
                ('server_id', '=', server.id)
            ], limit=int(limit), order='timestamp desc')

            return self._json_response({
                'server': server.name,
                'logs_count': len(logs),
                'logs': [{
                    'id': log.id,
                    'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                    'tool_name': log.tool_name,
                    'status': log.status,
                    'duration': log.duration,
                    'error_message': log.error_message,
                    'account': log.account_id.name if log.account_id else None,
                } for log in logs]
            })

        except Exception as e:
            return self._json_response({'error': str(e)}, 500)
