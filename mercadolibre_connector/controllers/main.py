# -*- coding: utf-8 -*-

import requests
import logging
from datetime import datetime, timedelta
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class MercadolibreController(http.Controller):

    @http.route('/mercadolibre/callback', type='http', auth='user', website=True, csrf=False)
    def oauth_callback(self, code=None, state=None, error=None, **kwargs):
        """
        Callback de OAuth de MercadoLibre.

        Parámetros:
            code: Código de autorización
            state: Token de la invitación (opcional)
            error: Error de OAuth (si aplica)
        """
        if error:
            _logger.error(f'Error en OAuth de MercadoLibre: {error}')
            return request.render('mercadolibre_connector.oauth_error', {
                'error': error,
                'error_description': kwargs.get('error_description', 'Error desconocido')
            })

        if not code:
            return request.render('mercadolibre_connector.oauth_error', {
                'error': 'missing_code',
                'error_description': 'No se recibió el código de autorización'
            })

        try:
            # Si hay state, busca la invitación
            invitation = None
            config = None

            if state:
                invitation = request.env['mercadolibre.invitation'].sudo().search([
                    ('token', '=', state),
                    ('state', '=', 'sent')
                ], limit=1)

                if invitation:
                    config = invitation.config_id
                else:
                    _logger.warning(f'No se encontró invitación con token {state}')

            # Si no hay invitación o config, busca la primera configuración activa
            if not config:
                config = request.env['mercadolibre.config'].sudo().search([
                    ('active', '=', True)
                ], limit=1)

            if not config:
                return request.render('mercadolibre_connector.oauth_error', {
                    'error': 'no_config',
                    'error_description': 'No se encontró una configuración activa de MercadoLibre'
                })

            # Intercambia el código por tokens
            token_url = 'https://api.mercadolibre.com/oauth/token'

            payload = {
                'grant_type': 'authorization_code',
                'client_id': config.client_id,
                'client_secret': config.client_secret,
                'code': code,
                'redirect_uri': config.redirect_uri,
            }

            _logger.info(f'Intercambiando código por token para config {config.name}')

            response = requests.post(token_url, data=payload, timeout=30)
            response.raise_for_status()

            token_data = response.json()

            # Calcula la fecha de expiración
            expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])

            # Obtiene información del usuario
            ml_user_id = str(token_data.get('user_id'))

            user_info = {}
            try:
                user_url = f"https://api.mercadolibre.com/users/{ml_user_id}"
                user_response = requests.get(
                    user_url,
                    headers={'Authorization': f"Bearer {token_data['access_token']}"},
                    timeout=30
                )
                user_response.raise_for_status()
                user_info = user_response.json()
            except Exception as e:
                _logger.warning(f'No se pudo obtener información del usuario: {str(e)}')

            # Busca o crea la cuenta
            account = request.env['mercadolibre.account'].sudo().search([
                ('ml_user_id', '=', ml_user_id),
                ('config_id', '=', config.id)
            ], limit=1)

            if account:
                _logger.info(f'Actualizando cuenta existente {account.name}')
            else:
                _logger.info(f'Creando nueva cuenta para usuario ML {ml_user_id}')
                account = request.env['mercadolibre.account'].sudo().create({
                    'config_id': config.id,
                    'ml_user_id': ml_user_id,
                    'ml_nickname': user_info.get('nickname'),
                    'ml_email': user_info.get('email'),
                    'ml_first_name': user_info.get('first_name'),
                    'ml_last_name': user_info.get('last_name'),
                    'state': 'connected',
                })

            # Actualiza información del usuario si existe
            if user_info:
                account.sudo().write({
                    'ml_nickname': user_info.get('nickname', account.ml_nickname),
                    'ml_email': user_info.get('email', account.ml_email),
                    'ml_first_name': user_info.get('first_name', account.ml_first_name),
                    'ml_last_name': user_info.get('last_name', account.ml_last_name),
                    'state': 'connected',
                })

            # Crea el token
            request.env['mercadolibre.token'].sudo().create({
                'account_id': account.id,
                'access_token': token_data['access_token'],
                'refresh_token': token_data['refresh_token'],
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_in': token_data['expires_in'],
                'expires_at': expires_at,
                'scope': token_data.get('scope', ''),
                'ml_user_id': ml_user_id,
            })

            # Si había invitación, marca como aceptada
            if invitation:
                invitation.sudo().mark_as_accepted(account.id)

            # Log del éxito
            request.env['mercadolibre.log'].sudo().create({
                'log_type': 'oauth',
                'level': 'success',
                'account_id': account.id,
                'message': f'Cuenta conectada exitosamente: {account.name}',
            })

            # Envía email de confirmación
            template = request.env.ref('mercadolibre_connector.mail_template_mercadolibre_connected', raise_if_not_found=False)
            if template:
                template.sudo().send_mail(account.id, force_send=True)

            _logger.info(f'OAuth completado exitosamente para cuenta {account.name}')

            # Renderiza la página de éxito
            return request.render('mercadolibre_connector.oauth_success', {
                'account': account,
                'config': config,
            })

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            _logger.error(f'Error en OAuth callback: {error_msg}')

            # Log del error
            request.env['mercadolibre.log'].sudo().create({
                'log_type': 'oauth',
                'level': 'error',
                'message': f'Error en OAuth: {error_msg}',
                'error_details': str(e),
            })

            return request.render('mercadolibre_connector.oauth_error', {
                'error': 'request_error',
                'error_description': error_msg
            })

        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Error inesperado en OAuth callback: {error_msg}')

            return request.render('mercadolibre_connector.oauth_error', {
                'error': 'unexpected_error',
                'error_description': error_msg
            })
