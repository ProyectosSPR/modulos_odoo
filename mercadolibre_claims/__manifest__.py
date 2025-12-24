# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Claims',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'summary': 'Gestion de Reclamos y Mediaciones de MercadoLibre',
    'description': '''
        Modulo para gestionar reclamos (claims) y mediaciones de MercadoLibre.

        Funcionalidades:
        - Sincronizacion de reclamos desde la API de MercadoLibre
        - Gestion de mensajes y adjuntos
        - Gestion de evidencias de envio
        - Seguimiento de resoluciones esperadas
        - Acciones automaticas sobre pagos en mediacion
        - Notificaciones y actividades
        - Historial de acciones
    ''',
    'author': 'DML',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'mercadolibre_connector',
        'mercadolibre_payments',
        'mail',
        'account',
    ],
    'data': [
        # Security
        'security/mercadolibre_claims_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/ir_cron.xml',
        # Views
        'views/mercadolibre_claim_views.xml',
        'views/mercadolibre_claim_message_views.xml',
        'views/mercadolibre_claim_config_views.xml',
        'views/mercadolibre_payment_views.xml',
        'views/mercadolibre_payment_sync_config_views.xml',
        'views/menus.xml',
        # Wizards
        'wizard/mercadolibre_claim_sync_views.xml',
        'wizard/mercadolibre_claim_send_message_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mercadolibre_claims/static/src/css/claim_chat.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
