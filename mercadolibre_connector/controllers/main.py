# -*- coding: utf-8 -*-

import json
import requests
import logging
from datetime import datetime, timedelta
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class MercadolibreController(http.Controller):
    """
    Controller central para MercadoLibre.

    Endpoints:
    - /mercadolibre/callback: OAuth callback
    - /mercadolibre/notifications: Webhook para notificaciones de ML

    Configuración de Notificaciones en ML:
    En tu aplicación de ML, configura la URL de callback:
    https://tu-dominio.com/mercadolibre/notifications

    Topics soportados:
    - orders_v2: Notificaciones de órdenes
    - shipments: Notificaciones de envíos
    - messages: Notificaciones de mensajes
    - items: Notificaciones de publicaciones
    - questions: Notificaciones de preguntas
    """

    # =========================================================================
    # WEBHOOK DE NOTIFICACIONES
    # =========================================================================

    @http.route('/mercadolibre/notifications', type='json', auth='public',
                methods=['POST'], csrf=False)
    def webhook_notifications(self, **kwargs):
        """
        Endpoint central para recibir notificaciones de MercadoLibre.

        MercadoLibre envía POST con estructura:
        {
            "resource": "/orders/123456789",
            "user_id": 123456789,
            "topic": "orders_v2",
            "application_id": 89745685555,
            "attempts": 1,
            "sent": "2024-01-15T10:30:00.000Z",
            "received": "2024-01-15T10:30:01.000Z"
        }

        Topics:
        - orders_v2: Cambios en órdenes
        - shipments: Cambios en envíos
        - messages: Mensajes de compradores
        - items: Cambios en publicaciones
        - questions: Preguntas de compradores

        IMPORTANTE: Responder HTTP 200 en menos de 500ms para evitar reintentos.
        """
        start_time = datetime.now()

        try:
            data = request.jsonrequest
            topic = data.get('topic', 'unknown')
            user_id = str(data.get('user_id', ''))
            resource = data.get('resource', '')
            attempts = data.get('attempts', 1)
            notification_id = data.get('_id', '')

            _logger.info("=" * 60)
            _logger.info(f"[WEBHOOK] Notificación recibida")
            _logger.info(f"[WEBHOOK] Topic: {topic}")
            _logger.info(f"[WEBHOOK] User ID: {user_id}")
            _logger.info(f"[WEBHOOK] Resource: {resource}")
            _logger.info(f"[WEBHOOK] Attempts: {attempts}")
            _logger.info(f"[WEBHOOK] Notification ID: {notification_id}")
            _logger.info(f"[WEBHOOK] Payload completo: {json.dumps(data, indent=2)}")

            # Buscar cuenta ML
            account = request.env['mercadolibre.account'].sudo().search([
                ('ml_user_id', '=', user_id),
                ('active', '=', True)
            ], limit=1)

            account_name = account.name if account else 'NO ENCONTRADA'

            if not account:
                _logger.warning(f"[WEBHOOK] Cuenta ML no encontrada para user_id: {user_id}")

                # Log a BD incluso si no hay cuenta
                request.env['mercadolibre.log'].sudo().create({
                    'log_type': 'notification',
                    'level': 'warning',
                    'message': f'[WEBHOOK] Cuenta no encontrada - Topic: {topic}, Resource: {resource}',
                    'request_url': resource,
                    'request_body': json.dumps(data, indent=2),
                })

                return {'status': 'ignored', 'reason': 'account_not_found'}

            # Log detallado de la notificación a BD
            log_record = request.env['mercadolibre.log'].sudo().create({
                'log_type': 'notification',
                'level': 'info',
                'account_id': account.id,
                'message': f'[WEBHOOK RECIBIDO] Topic: {topic} | Resource: {resource} | Intento: {attempts}',
                'request_url': resource,
                'request_method': 'POST',
                'request_body': json.dumps(data, indent=2),
            })

            _logger.info(f"[WEBHOOK] Cuenta encontrada: {account_name} (ID: {account.id})")
            _logger.info(f"[WEBHOOK] Log ID creado: {log_record.id}")

            # Rutear según topic
            handler_method = f'_handle_notification_{topic}'
            if hasattr(self, handler_method):
                _logger.info(f"[WEBHOOK] Usando handler interno: {handler_method}")
                result = getattr(self, handler_method)(account, data)
            else:
                # Topic no manejado localmente, intentar delegación a módulos
                _logger.info(f"[WEBHOOK] Delegando a módulo externo para topic: {topic}")
                result = self._delegate_notification(account, data)

            # Calcular duración
            duration = (datetime.now() - start_time).total_seconds()

            # Actualizar log con resultado
            result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
            log_record.sudo().write({
                'response_body': result_str,
                'duration': duration,
                'level': 'success' if result.get('status') == 'ok' else 'warning',
            })

            _logger.info(f"[WEBHOOK] Resultado: {result}")
            _logger.info(f"[WEBHOOK] Duración: {duration:.3f}s")
            _logger.info("=" * 60)

            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)

            _logger.error(f"[WEBHOOK] Error procesando notificación: {error_msg}", exc_info=True)

            # Log del error a BD
            try:
                request.env['mercadolibre.log'].sudo().create({
                    'log_type': 'notification',
                    'level': 'error',
                    'message': f'[WEBHOOK ERROR] {error_msg}',
                    'request_body': json.dumps(request.jsonrequest, indent=2) if hasattr(request, 'jsonrequest') else '',
                    'error_details': error_msg,
                    'duration': duration,
                })
            except:
                pass

            return {'status': 'error', 'message': error_msg}

    def _delegate_notification(self, account, data):
        """
        Delega la notificación al módulo correspondiente según el topic.

        Los módulos pueden registrar handlers implementando:
        mercadolibre.notification.handler con método process_notification(account, data)
        """
        topic = data.get('topic')
        resource = data.get('resource', '')

        # Mapeo de topics a modelos que pueden manejarlos
        topic_handlers = {
            'messages': 'mercadolibre.conversation',
            'orders_v2': 'mercadolibre.order',
            'shipments': 'mercadolibre.shipment',
            'questions': 'mercadolibre.question',
        }

        handler_model = topic_handlers.get(topic)

        _logger.info(f"[WEBHOOK] Topic: {topic} -> Handler: {handler_model or 'NO DEFINIDO'}")

        if handler_model and handler_model in request.env:
            model = request.env[handler_model].sudo()
            if hasattr(model, 'process_notification'):
                try:
                    _logger.info(f"[WEBHOOK] Ejecutando {handler_model}.process_notification()")
                    result = model.process_notification(account, data)
                    _logger.info(f"[WEBHOOK] Handler {handler_model} completado: {result}")
                    return result
                except Exception as e:
                    _logger.error(f"[WEBHOOK] Error en handler {handler_model}: {str(e)}", exc_info=True)
                    return {'status': 'error', 'handler': handler_model, 'message': str(e)}
            else:
                _logger.warning(f"[WEBHOOK] Modelo {handler_model} no tiene método process_notification")
        else:
            if handler_model:
                _logger.warning(f"[WEBHOOK] Modelo {handler_model} no está instalado")

        _logger.debug(f"[WEBHOOK] Topic '{topic}' sin handler registrado")
        return {'status': 'ignored', 'reason': f'no_handler_for_{topic}'}

    @http.route('/mercadolibre/notifications/test', type='http', auth='public',
                methods=['GET'], csrf=False)
    def webhook_test(self, **kwargs):
        """
        Endpoint de prueba para verificar que el webhook está activo.
        ML puede usar esto para verificar la URL.
        """
        _logger.info("[WEBHOOK] Test endpoint called - OK")
        return 'OK'

    @http.route('/mercadolibre/notifications/status', type='json', auth='user',
                methods=['POST'], csrf=False)
    def webhook_status(self, **kwargs):
        """
        Endpoint para verificar el estado del webhook y ver estadísticas.
        Requiere autenticación.
        """
        try:
            Log = request.env['mercadolibre.log'].sudo()

            # Estadísticas de las últimas 24 horas
            since = datetime.now() - timedelta(hours=24)

            notifications = Log.search([
                ('log_type', '=', 'notification'),
                ('create_date', '>=', since.strftime('%Y-%m-%d %H:%M:%S')),
            ])

            # Contar por topic (extraer del mensaje)
            topic_counts = {}
            status_counts = {'success': 0, 'warning': 0, 'error': 0, 'info': 0}

            for log in notifications:
                # Contar por nivel
                status_counts[log.level] = status_counts.get(log.level, 0) + 1

                # Extraer topic del mensaje
                if 'Topic:' in log.message:
                    try:
                        topic = log.message.split('Topic:')[1].split('|')[0].strip()
                        topic_counts[topic] = topic_counts.get(topic, 0) + 1
                    except:
                        pass

            return {
                'status': 'ok',
                'webhook_url': '/mercadolibre/notifications',
                'last_24h': {
                    'total': len(notifications),
                    'by_status': status_counts,
                    'by_topic': topic_counts,
                },
                'last_notifications': [
                    {
                        'id': log.id,
                        'date': log.create_date.strftime('%Y-%m-%d %H:%M:%S') if log.create_date else '',
                        'level': log.level,
                        'message': log.message[:100],
                        'account': log.account_id.name if log.account_id else 'N/A',
                    }
                    for log in notifications[:10]
                ],
            }

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    # =========================================================================
    # OAUTH CALLBACK
    # =========================================================================

    @http.route('/mercadolibre/callback', type='http', auth='public', website=True, csrf=False)
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
