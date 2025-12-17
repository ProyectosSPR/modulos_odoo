# -*- coding: utf-8 -*-

import requests
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreHttp(models.AbstractModel):
    _name = 'mercadolibre.http'
    _description = 'HTTP Wrapper para MercadoLibre API'

    @api.model
    def _request(self, account_id, endpoint, method='GET', body=None,
                 headers=None, params=None, retry_on_401=True, log_request=True):
        """
        Realiza un request a la API de MercadoLibre.

        Args:
            account_id: ID de la cuenta MercadoLibre
            endpoint: Endpoint de la API (ej: '/users/me')
            method: Método HTTP (GET, POST, PUT, DELETE)
            body: Cuerpo del request (dict)
            headers: Headers adicionales (dict)
            params: Parámetros de query (dict)
            retry_on_401: Si True, intenta refrescar token en caso de 401
            log_request: Si True, registra el request en los logs

        Returns:
            dict: Respuesta de la API con keys: data, status_code, headers
        """
        account = self.env['mercadolibre.account'].browse(account_id)

        if not account.exists():
            raise UserError(_('Cuenta no encontrada.'))

        # Obtiene el token válido
        try:
            access_token = account.get_valid_token()
        except Exception as e:
            raise UserError(_(f'Error al obtener token: {str(e)}'))

        # Prepara la URL
        base_url = 'https://api.mercadolibre.com'
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
        url = f'{base_url}{endpoint}'

        # Prepara los headers
        request_headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if headers:
            request_headers.update(headers)

        # Log del request
        log_id = None
        if log_request:
            log = self.env['mercadolibre.log'].log_api_request(
                account_id=account_id,
                method=method,
                url=url,
                headers=request_headers,
                body=body
            )
            log_id = log.id

        try:
            import time
            start_time = time.time()

            # Realiza el request
            response = requests.request(
                method=method,
                url=url,
                json=body if method in ['POST', 'PUT'] else None,
                params=params,
                headers=request_headers,
                timeout=30
            )

            duration = time.time() - start_time

            # Si es 401 y se permite retry, intenta refrescar el token
            if response.status_code == 401 and retry_on_401:
                _logger.warning(f'Recibido 401, intentando refrescar token para cuenta {account.name}')

                # Refresca el token
                token = account.current_token_id
                if token:
                    token._refresh_token()

                    # Reintenta el request (sin permitir más retries)
                    return self._request(
                        account_id=account_id,
                        endpoint=endpoint,
                        method=method,
                        body=body,
                        headers=headers,
                        params=params,
                        retry_on_401=False,  # No reintentar más
                        log_request=False    # Ya se registró el primer intento
                    )

            # Log de la respuesta
            if log_request and log_id:
                self.env['mercadolibre.log'].log_api_response(
                    log_id=log_id,
                    response_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.text,
                    duration=duration
                )

            # Verifica errores HTTP
            response.raise_for_status()

            # Retorna la respuesta
            return {
                'data': response.json() if response.text else {},
                'status_code': response.status_code,
                'headers': dict(response.headers),
            }

        except requests.exceptions.HTTPError as e:
            error_msg = f'HTTP Error {response.status_code}: {response.text}'
            _logger.error(f'Error en request a ML API: {error_msg}')

            # Log del error
            if log_request:
                self.env['mercadolibre.log'].create({
                    'log_type': 'api_response',
                    'level': 'error',
                    'account_id': account_id,
                    'message': error_msg,
                    'request_url': url,
                    'request_method': method,
                    'response_code': response.status_code,
                    'error_details': str(e),
                })

            raise UserError(_(f'Error en la API de MercadoLibre: {error_msg}'))

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            _logger.error(f'Error en request a ML API: {error_msg}')

            # Log del error
            if log_request:
                self.env['mercadolibre.log'].create({
                    'log_type': 'error',
                    'level': 'error',
                    'account_id': account_id,
                    'message': f'Error de conexión: {error_msg}',
                    'request_url': url,
                    'request_method': method,
                    'error_details': str(e),
                })

            raise UserError(_(f'Error de conexión con MercadoLibre: {error_msg}'))
