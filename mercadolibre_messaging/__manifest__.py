# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Messaging',
    'version': '16.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Gestión de mensajería post-venta de MercadoLibre',
    'description': '''
MercadoLibre Messaging
======================

Módulo para gestionar la mensajería post-venta de MercadoLibre integrado con Odoo.

Características:
----------------
* Sincronización de conversaciones y mensajes
* Envío de mensajes manuales y automáticos
* Plantillas personalizables con validación de 350 caracteres
* Reglas de automatización basadas en estados de orden/envío (API ML)
* Configuración de horarios de atención
* Cola de mensajes para respeto de horarios
* Integración con chatter de sale.order
* Vista de conversaciones tipo chat
* Sistema de logging dual (consola + BD)

Integración:
------------
* Smart buttons en órdenes de venta y órdenes ML
* Tab de mensajes en formulario de orden
* Sincronización automática con chatter
* Wizard de composición de mensajes

Estados de Orden (API ML):
--------------------------
* confirmed, payment_required, payment_in_process
* partially_paid, paid, partially_refunded
* pending_cancel, cancelled

Estados de Envío (API ML):
--------------------------
* pending, handling, ready_to_ship, shipped
* in_transit, out_for_delivery, delivered
* not_delivered, returned, cancelled
    ''',
    'author': 'DML',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'mercadolibre_connector',
        'mercadolibre_sales',
        'mercadolibre_shipments',
        'mail',
        'sale_management',
    ],
    'data': [
        # Security
        'security/mercadolibre_messaging_security.xml',
        'security/ir.model.access.csv',

        # Data - Templates first (referenced by schedules and rules)
        'data/mercadolibre_message_template_data.xml',
        'data/mercadolibre_messaging_schedule_data.xml',
        'data/mercadolibre_message_rule_data.xml',
        'data/ir_cron_data.xml',

        # Views - Configuration
        'views/mercadolibre_messaging_config_views.xml',
        'views/mercadolibre_messaging_schedule_views.xml',
        'views/mercadolibre_message_template_views.xml',
        'views/mercadolibre_message_rule_views.xml',

        # Views - Main
        'views/mercadolibre_conversation_views.xml',
        'views/mercadolibre_message_views.xml',
        'views/mercadolibre_message_queue_views.xml',

        # Views - Integration
        'views/sale_order_views.xml',
        'views/mercadolibre_order_views.xml',

        # Wizard
        'views/wizard_views.xml',

        # Menus (last)
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mercadolibre_messaging/static/src/css/ml_chat.css',
            'mercadolibre_messaging/static/src/js/ml_chat.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
