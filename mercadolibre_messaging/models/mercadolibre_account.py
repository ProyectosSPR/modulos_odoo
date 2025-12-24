# -*- coding: utf-8 -*-
"""
Extensión del modelo mercadolibre.account para añadir funcionalidades de API.

Añade el método _make_request() para realizar peticiones a la API de MercadoLibre
de forma simplificada.
"""

import requests
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

BASE_URL = 'https://api.mercadolibre.com'


class MercadolibreAccountMessaging(models.Model):
    _inherit = 'mercadolibre.account'

    def _make_request(self, method, endpoint, data=None, params=None):
        """
        Realiza una petición a la API de MercadoLibre.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: Endpoint de la API (ej: '/orders/123')
            data: Datos para POST/PUT (dict)
            params: Query parameters (dict)

        Returns:
            dict con la respuesta de la API o None si falla

        Raises:
            Exception con el mensaje de error si la API devuelve error
        """
        self.ensure_one()

        # Obtener token válido
        try:
            access_token = self.get_valid_token()
        except Exception as e:
            _logger.error(f"Error obteniendo token para cuenta {self.name}: {e}")
            raise

        # Construir URL
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
        url = f'{BASE_URL}{endpoint}'

        # Headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        try:
            _logger.info(f"=== ML API REQUEST ===")
            _logger.info(f"Method: {method.upper()}")
            _logger.info(f"URL: {url}")
            if data:
                _logger.info(f"Data: {data}")
            if params:
                _logger.info(f"Params: {params}")

            response = requests.request(
                method=method.upper(),
                url=url,
                json=data if method.upper() in ['POST', 'PUT'] else None,
                params=params,
                headers=headers,
                timeout=30
            )

            # Log respuesta
            _logger.info(f"=== ML API RESPONSE ===")
            _logger.info(f"Status Code: {response.status_code}")
            _logger.info(f"Response Body: {response.text[:1000] if response.text else 'Empty'}")

            # Manejar errores HTTP
            if response.status_code >= 400:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass

                error_msg = error_data.get('message', response.text)
                error_code = error_data.get('error', str(response.status_code))

                _logger.error(f"=== ML API ERROR ===")
                _logger.error(f"Error Code: {error_code}")
                _logger.error(f"Error Message: {error_msg}")
                _logger.error(f"Full Error Data: {error_data}")
                raise Exception(f"{error_code}: {error_msg}")

            # Retornar JSON si hay contenido
            if response.text:
                return response.json()
            return {}

        except requests.exceptions.Timeout:
            _logger.error(f"Timeout en API request: {url}")
            raise Exception("Timeout en la conexión con MercadoLibre")

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error de conexión con ML API: {e}")
            raise Exception(f"Error de conexión: {str(e)}")
