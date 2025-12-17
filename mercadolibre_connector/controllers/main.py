# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import requests
import logging

_logger = logging.getLogger(__name__)


class MercadoLibreController(http.Controller):

    @http.route('/mercadolibre/callback', type='http', auth='user', website=True, csrf=False)
    def oauth_callback(self, code=None, state=None, error=None, **kwargs):
        """
        Callback de OAuth después de que el usuario autoriza en Mercado Libre.

        Params:
            code: Authorization code de ML
            state: Token de seguridad (puede ser state o invitation_token)
            error: Si hubo error en la autorización
        """
        if error:
            _logger.error(f"Error en OAuth callback: {error}")
            return request.render('mercadolibre_connector.oauth_error', {
                'error': error,
                'error_description': kwargs.get('error_description', 'Error desconocido')
            })

        if not code or not state:
            _logger.error("OAuth callback sin code o state")
            return request.render('mercadolibre_connector.oauth_error', {
                'error': 'invalid_request',
                'error_description': 'Faltan parámetros requeridos'
            })

        try:
            # Verificar si es una invitación
            invitation = request.env['mercadolibre.invitation'].sudo().search([
                ('invitation_token', '=', state),
                ('state', 'in', ['sent', 'opened'])
            ], limit=1)

            if invitation:
                # Flujo de invitación
                return self._process_invitation_callback(invitation, code)
            else:
                # Flujo normal (state desde sesión)
                return self._process_normal_callback(state, code)

        except Exception as e:
            _logger.error(f"Excepción en OAuth callback: {str(e)}", exc_info=True)
            return request.render('mercadolibre_connector.oauth_error', {
                'error': 'server_error',
                'error_description': str(e)
            })

    def _process_invitation_callback(self, invitation, code):
        """Procesar callback de invitación"""
        try:
            # Marcar como abierta
            invitation.mark_as_opened()

            # Intercambiar code por tokens
            tokens = self._exchange_code_for_token(invitation.config_id, code)
            if not tokens.get('success'):
                raise Exception(tokens.get('error', 'Error obteniendo token'))

            token_data = tokens['data']

            # Obtener info del usuario
            user_info = self._get_user_info(token_data['access_token'])
            if not user_info.get('success'):
                raise Exception(user_info.get('error', 'Error obteniendo info de usuario'))

            user_data = user_info['data']

            # Crear o actualizar cuenta
            account = request.env['mercadolibre.account'].sudo().search([
                ('company_id', '=', invitation.company_id.id),
                ('ml_user_id', '=', str(user_data['id']))
            ], limit=1)

            if account:
                # Actualizar cuenta existente
                account.write({
                    'config_id': invitation.config_id.id,
                    'nickname': user_data.get('nickname'),
                    'email': user_data.get('email'),
                    'site_id': user_data.get('site_id'),
                    'points': user_data.get('points', 0),
                    'permalink': user_data.get('permalink'),
                    'thumbnail': user_data.get('thumbnail', {}).get('picture_url') if isinstance(user_data.get('thumbnail'), dict) else user_data.get('thumbnail'),
                    'authorization_date': http.request.env['ir.fields'].datetime.now(),
                    'active': True,
                })
            else:
                # Crear nueva cuenta
                account = request.env['mercadolibre.account'].sudo().create({
                    'config_id': invitation.config_id.id,
                    'ml_user_id': str(user_data['id']),
                    'nickname': user_data.get('nickname'),
                    'email': user_data.get('email'),
                    'site_id': user_data.get('site_id'),
                    'account_type': 'personal',  # TODO: Detectar tipo
                    'points': user_data.get('points', 0),
                    'permalink': user_data.get('permalink'),
                    'thumbnail': user_data.get('thumbnail', {}).get('picture_url') if isinstance(user_data.get('thumbnail'), dict) else user_data.get('thumbnail'),
                    'authorization_date': http.request.env['ir.fields'].datetime.now(),
                })

            # Crear o actualizar token
            token = request.env['mercadolibre.token'].sudo().search([
                ('account_id', '=', account.id)
            ], limit=1)

            token_vals = {
                'account_id': account.id,
                'access_token': token_data['access_token'],
                'token_type': token_data.get('token_type', 'Bearer'),
                'refresh_token': token_data['refresh_token'],
                'scope': token_data.get('scope'),
                'expires_in': token_data.get('expires_in', 21600),
            }

            if token:
                token.write(token_vals)
            else:
                request.env['mercadolibre.token'].sudo().create(token_vals)

            # Marcar invitación como completada
            invitation.mark_as_completed(account.id)

            # Log
            request.env['mercadolibre.log'].sudo().create({
                'account_id': account.id,
                'log_type': 'auth',
                'level': 'info',
                'operation': 'oauth_success_invitation',
                'message': f'Cuenta conectada via invitación: {account.nickname}',
                'company_id': account.company_id.id,
            })

            return request.render('mercadolibre_connector.oauth_success', {
                'account': account,
                'invitation': invitation,
            })

        except Exception as e:
            _logger.error(f"Error procesando invitación: {str(e)}", exc_info=True)
            return request.render('mercadolibre_connector.oauth_error', {
                'error': 'invitation_error',
                'error_description': str(e)
            })

    def _process_normal_callback(self, state, code):
        """Procesar callback normal (sin invitación)"""
        # TODO: Implementar flujo normal si se necesita
        # Por ahora, solo soportamos invitaciones
        _logger.warning("Callback normal no implementado aún")
        return request.render('mercadolibre_connector.oauth_error', {
            'error': 'not_implemented',
            'error_description': 'Por favor use el sistema de invitaciones para conectar cuentas'
        })

    def _exchange_code_for_token(self, config, code):
        """Intercambiar authorization code por access token"""
        url = 'https://api.mercadolibre.com/oauth/token'
        payload = {
            'grant_type': 'authorization_code',
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'code': code,
            'redirect_uri': config.redirect_uri,
        }

        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()

            return {
                'success': True,
                'data': response.json()
            }

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            try:
                error_data = e.response.json() if hasattr(e, 'response') and e.response else {}
                error_msg = error_data.get('message', error_msg)
            except:
                pass

            _logger.error(f"Error intercambiando code por token: {error_msg}")

            return {
                'success': False,
                'error': error_msg
            }

    def _get_user_info(self, access_token):
        """Obtener información del usuario desde ML"""
        url = 'https://api.mercadolibre.com/users/me'
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            return {
                'success': True,
                'data': response.json()
            }

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            _logger.error(f"Error obteniendo info de usuario: {error_msg}")

            return {
                'success': False,
                'error': error_msg
            }

    @http.route('/mercadolibre/invite/<string:token>', type='http', auth='public', website=True)
    def invitation_redirect(self, token, **kwargs):
        """
        Procesar link de invitación.
        Redirige al usuario a la URL de autorización de ML.
        """
        invitation = request.env['mercadolibre.invitation'].sudo().search([
            ('invitation_token', '=', token)
        ], limit=1)

        if not invitation:
            return request.render('mercadolibre_connector.invitation_not_found')

        if invitation.state == 'completed':
            return request.render('mercadolibre_connector.invitation_already_used', {
                'invitation': invitation
            })

        if invitation.state == 'cancelled':
            return request.render('mercadolibre_connector.invitation_cancelled')

        if invitation.state == 'expired' or invitation.expires_at < http.request.env['ir.fields'].datetime.now():
            invitation.write({'state': 'expired'})
            return request.render('mercadolibre_connector.invitation_expired', {
                'invitation': invitation
            })

        # Marcar como abierta
        invitation.mark_as_opened()

        # Redirigir a ML
        return request.redirect(invitation.authorization_url)

    @http.route('/mercadolibre/test', type='http', auth='user')
    def test_endpoint(self, **kwargs):
        """Endpoint de prueba para verificar que el módulo está instalado"""
        return "Mercado Libre Connector está activo ✓"
