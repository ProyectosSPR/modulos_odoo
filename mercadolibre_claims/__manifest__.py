# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Claims',
    'version': '16.0.2.0.0',
    'category': 'Sales',
    'summary': 'Gestion de Reclamos, Mediaciones y Devoluciones de MercadoLibre',
    'description': '''
        Modulo para gestionar reclamos (claims), mediaciones y devoluciones de MercadoLibre.

        Funcionalidades:
        - Sincronizacion de reclamos desde la API de MercadoLibre
        - Gestion de mensajes y adjuntos
        - Gestion de evidencias de envio
        - Seguimiento de resoluciones esperadas
        - Acciones automaticas sobre pagos en mediacion
        - Notificaciones y actividades
        - Historial de acciones
        - Gestion automatica de devoluciones de inventario
        - Soporte para Fulfillment (Full) con validacion automatica
        - Integracion con stock.picking para cuadre de inventario
    ''',
    'author': 'DML',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'mercadolibre_connector',
        'mercadolibre_payments',
        'mercadolibre_sales',
        'mail',
        'account',
        'stock',
        'sale_stock',
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
        'views/mercadolibre_return_views.xml',
        'views/sale_order_views.xml',
        'views/menus.xml',
        # Wizards
        'wizard/mercadolibre_claim_sync_views.xml',
        'wizard/mercadolibre_claim_send_message_views.xml',
        'wizard/mercadolibre_return_review_views.xml',
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
