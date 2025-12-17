# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import ValidationError
import requests
import json
import time
import traceback
import logging

_logger = logging.getLogger(__name__)


class MercadoLibreHTTP(models.AbstractModel):
    _name = 'mercadolibre.http'
    _description = 'HTTP Wrapper para Mercado Libre API'

    @api.model
    def _request(self, account_id, endpoint, method='GET', body=None, headers=None,
                 params=None, retry_on_401=True, log_request=True):
        """
        Hace request a ML API con manejo automático de tokens.

        Args:
            account_id (int): ID de mercadolibre.account
            endpoint (str): /users/me, /orders/search, etc.
            method (str): GET, POST, PUT, DELETE
            body (dict|str): Dict o String del body
            headers (dict): Dict de headers adicionales
            params (dict): Dict de query params
            retry_on_401 (bool): Si True, refresca token y reintenta en 401
            log_request (bool): Si True, guarda en mercadolibre.log

        Returns:
            dict: {
                'success': True/False,
                'status_code': 200,
                'data': {...},
                'error': None,
                'response_time': 0.5
            }
        """
        account = self.env['mercadolibre.account'].browse(account_id)
        if not account.exists():
            return {
                'success': False,
                'status_code': 0,
                'error': 'Cuenta no encontrada',
                'data': None,
                'response_time': 0
            }

        # Verificar que tenga token
        if not account.token_id:
            return {
                'success': False,
                'status_code': 0,
                'error': 'La cuenta no tiene un token configurado',
                'data': None,
                'response_time': 0
            }

        token = account.token_id[0] if isinstance(account.token_id, list) else account.token_id

        # Construir URL
        base_url = 'https://api.mercadolibre.com'
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
        url = f"{base_url}{endpoint}"

        # Headers
        req_headers = {
            'Authorization': f'Bearer {token.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if headers:
            req_headers.update(headers)

        # Log inicial
        log_vals = {
            'account_id': account.id,
            'log_type': 'api_request',
            'level': 'debug',
            'operation': f'{method.upper()} {endpoint}',
            'endpoint': url,
            'http_method': method.lower(),
            'company_id': account.company_id.id,
            'user_id': self.env.user.id,
        }

        # Log headers sin token
        safe_headers = {k: v for k, v in req_headers.items() if k.lower() != 'authorization'}
        log_vals['request_headers'] = json.dumps(safe_headers, indent=2)

        # Log body
        if body:
            if isinstance(body, dict):
                log_vals['request_body'] = json.dumps(body, indent=2)
            else:
                log_vals['request_body'] = str(body)

        start_time = time.time()

        try:
            # Preparar body
            request_kwargs = {
                'method': method.upper(),
                'url': url,
                'headers': req_headers,
                'timeout': 30
            }

            if body:
                if isinstance(body, dict):
                    request_kwargs['json'] = body
                else:
                    request_kwargs['data'] = body

            if params:
                request_kwargs['params'] = params

            # Hacer request
            response = requests.request(**request_kwargs)
            response_time = time.time() - start_time

            # Log response básico
            log_vals.update({
                'log_type': 'api_response',
                'status_code': response.status_code,
                'response_time': response_time,
            })

            # Limitar response body a 5000 caracteres para no llenar la BD
            response_text = response.text[:5000] if response.text else ''
            if len(response.text) > 5000:
                response_text += '\n... (truncado)'
            log_vals['response_body'] = response_text

            # Caso especial: 401 = Token expirado
            if response.status_code == 401 and retry_on_401:
                log_vals.update({
                    'level': 'warning',
                    'message': 'Token expirado (401), refrescando y reintentando...',
                })
                if log_request:
                    self.env['mercadolibre.log'].create(log_vals)

                # Refrescar token
                try:
                    _logger.info(f"Token expirado para cuenta {account.nickname}, refrescando...")
                    token._refresh_token()

                    # Reintentar request (solo una vez)
                    _logger.info(f"Token refrescado, reintentando request...")
                    return self._request(
                        account_id=account_id,
                        endpoint=endpoint,
                        method=method,
                        body=body,
                        headers=headers,
                        params=params,
                        retry_on_401=False,  # No reintentar de nuevo
                        log_request=True
                    )
                except Exception as refresh_error:
                    error_msg = f'No se pudo refrescar token: {str(refresh_error)}'
                    _logger.error(f"Error refrescando token: {error_msg}")

                    return {
                        'success': False,
                        'status_code': 401,
                        'error': error_msg,
                        'data': None,
                        'response_time': response_time,
                    }

            # Parsear response
            response_data = None
            if response.text:
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    response_data = {'raw': response.text}

            # Success (2xx)
            if 200 <= response.status_code < 300:
                log_vals.update({
                    'level': 'info',
                    'message': f'Request exitoso: {response.status_code}',
                })

                result = {
                    'success': True,
                    'status_code': response.status_code,
                    'data': response_data,
                    'error': None,
                    'response_time': response_time,
                }

            # Error (4xx, 5xx)
            else:
                error_msg = 'Unknown error'
                error_code = None

                if isinstance(response_data, dict):
                    error_msg = response_data.get('message', error_msg)
                    error_code = response_data.get('error', None)

                log_vals.update({
                    'level': 'error',
                    'message': f'Error {response.status_code}: {error_msg}',
                    'error_code': error_code,
                    'error_message': error_msg,
                })

                result = {
                    'success': False,
                    'status_code': response.status_code,
                    'error': error_msg,
                    'data': response_data,
                    'response_time': response_time,
                }

            # Guardar log
            if log_request:
                self.env['mercadolibre.log'].create(log_vals)

            return result

        except requests.exceptions.Timeout:
            response_time = time.time() - start_time
            error_msg = f'Timeout después de 30 segundos'

            log_vals.update({
                'log_type': 'error',
                'level': 'error',
                'message': error_msg,
                'error_message': error_msg,
                'response_time': response_time,
            })

            if log_request:
                self.env['mercadolibre.log'].create(log_vals)

            _logger.error(f"Timeout en request a {url}")

            return {
                'success': False,
                'status_code': 0,
                'error': error_msg,
                'data': None,
                'response_time': response_time,
            }

        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            error_msg = str(e)

            # Intentar obtener detalles del error
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('message', error_msg)
                    status_code = e.response.status_code
                except:
                    status_code = e.response.status_code if hasattr(e.response, 'status_code') else 0
            else:
                status_code = 0

            log_vals.update({
                'log_type': 'error',
                'level': 'error',
                'message': f'Error de conexión: {error_msg}',
                'error_message': error_msg,
                'status_code': status_code,
                'response_time': response_time,
            })

            if log_request:
                self.env['mercadolibre.log'].create(log_vals)

            _logger.error(f"RequestException en {url}: {error_msg}")

            return {
                'success': False,
                'status_code': status_code,
                'error': error_msg,
                'data': None,
                'response_time': response_time,
            }

        except Exception as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            stack = traceback.format_exc()

            log_vals.update({
                'log_type': 'error',
                'level': 'critical',
                'message': f'Excepción no controlada: {error_msg}',
                'error_message': error_msg,
                'stack_trace': stack,
                'response_time': response_time,
            })

            if log_request:
                self.env['mercadolibre.log'].create(log_vals)

            _logger.error(f"Excepción en request a {url}: {error_msg}\n{stack}")

            return {
                'success': False,
                'status_code': 0,
                'error': error_msg,
                'data': None,
                'response_time': response_time,
            }

    @api.model
    def get(self, account_id, endpoint, params=None, **kwargs):
        """Helper para GET requests"""
        return self._request(account_id, endpoint, method='GET', params=params, **kwargs)

    @api.model
    def post(self, account_id, endpoint, body=None, **kwargs):
        """Helper para POST requests"""
        return self._request(account_id, endpoint, method='POST', body=body, **kwargs)

    @api.model
    def put(self, account_id, endpoint, body=None, **kwargs):
        """Helper para PUT requests"""
        return self._request(account_id, endpoint, method='PUT', body=body, **kwargs)

    @api.model
    def delete(self, account_id, endpoint, **kwargs):
        """Helper para DELETE requests"""
        return self._request(account_id, endpoint, method='DELETE', **kwargs)
