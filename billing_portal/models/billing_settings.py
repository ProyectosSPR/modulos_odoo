# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # API Keys
    billing_portal_gemini_api_key = fields.Char(
        string='API Key Google Gemini',
        config_parameter='billing_portal.gemini_api_key'
    )

    billing_portal_gemini_model = fields.Selection([
        ('gemini-2.0-flash', 'Gemini 2.0 Flash (Rápido)'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro (Preciso)'),
        ('gemini-1.5-flash', 'Gemini 1.5 Flash'),
    ], string='Modelo Gemini',
        default='gemini-2.0-flash',
        config_parameter='billing_portal.gemini_model'
    )

    # Configuración de validación
    billing_portal_use_ai_fallback = fields.Boolean(
        string='Usar IA como Fallback',
        default=True,
        config_parameter='billing_portal.use_ai_fallback',
        help='Si la extracción local falla, intentar con IA'
    )

    billing_portal_ai_only = fields.Boolean(
        string='Solo usar IA',
        default=False,
        config_parameter='billing_portal.ai_only',
        help='Siempre usar IA para extraer datos (más costoso pero más preciso)'
    )

    # Configuración del portal
    billing_portal_require_delivery = fields.Boolean(
        string='Requerir Entrega para Facturar',
        default=True,
        config_parameter='billing_portal.require_delivery',
        help='Solo permitir facturar órdenes con envío entregado'
    )

    billing_portal_allow_multiple_orders = fields.Boolean(
        string='Permitir Facturar Múltiples Órdenes',
        default=True,
        config_parameter='billing_portal.allow_multiple_orders'
    )

    billing_portal_max_orders_per_invoice = fields.Integer(
        string='Máximo de Órdenes por Factura',
        default=10,
        config_parameter='billing_portal.max_orders_per_invoice'
    )

    # Configuración de autenticación
    billing_portal_auth_method = fields.Selection([
        ('receiver_id', 'Solo Receiver ID'),
        ('email', 'Solo Email'),
        ('both', 'Receiver ID o Email'),
    ], string='Método de Autenticación',
        default='both',
        config_parameter='billing_portal.auth_method'
    )

    billing_portal_session_duration = fields.Integer(
        string='Duración de Sesión (horas)',
        default=24,
        config_parameter='billing_portal.session_duration'
    )

    # Notificaciones
    billing_portal_notify_on_request = fields.Boolean(
        string='Notificar al Recibir Solicitud',
        default=True,
        config_parameter='billing_portal.notify_on_request'
    )

    billing_portal_notify_emails = fields.Char(
        string='Emails de Notificación',
        config_parameter='billing_portal.notify_emails',
        help='Emails separados por coma para notificaciones'
    )

    # Base de datos externa (PostgreSQL mercadoLibre)
    billing_portal_external_db_host = fields.Char(
        string='Host BD Externa',
        config_parameter='billing_portal.external_db_host'
    )

    billing_portal_external_db_port = fields.Char(
        string='Puerto BD Externa',
        config_parameter='billing_portal.external_db_port'
    )

    billing_portal_external_db_name = fields.Char(
        string='Nombre BD Externa',
        config_parameter='billing_portal.external_db_name'
    )

    billing_portal_external_db_user = fields.Char(
        string='Usuario BD Externa',
        config_parameter='billing_portal.external_db_user'
    )

    billing_portal_external_db_password = fields.Char(
        string='Contraseña BD Externa',
        config_parameter='billing_portal.external_db_password'
    )

    def action_test_gemini_connection(self):
        """Prueba la conexión con la API de Gemini"""
        import requests

        api_key = self.billing_portal_gemini_api_key
        if not api_key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'No hay API Key configurada',
                    'type': 'danger',
                }
            }

        try:
            response = requests.get(
                f'https://generativelanguage.googleapis.com/v1/models',
                params={'key': api_key},
                timeout=10
            )

            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Conexión Exitosa',
                        'message': 'La API de Gemini está funcionando correctamente',
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'Error de API: {response.status_code}',
                        'type': 'danger',
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def action_test_external_db(self):
        """Prueba la conexión con la BD externa"""
        try:
            import psycopg2

            conn = psycopg2.connect(
                host=self.billing_portal_external_db_host,
                port=self.billing_portal_external_db_port or 5432,
                database=self.billing_portal_external_db_name,
                user=self.billing_portal_external_db_user,
                password=self.billing_portal_external_db_password,
            )
            conn.close()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Conexión Exitosa',
                    'message': 'Conexión a BD externa establecida',
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error de Conexión',
                    'message': str(e),
                    'type': 'danger',
                }
            }
