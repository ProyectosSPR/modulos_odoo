# -*- coding: utf-8 -*-
{
    'name': 'Mercado Libre Connector',
    'version': '16.0.1.0.0',
    'category': 'Sales/eCommerce',
    'summary': 'Integración completa con Mercado Libre - Multi-empresa y Multi-tienda',
    'description': """
        Mercado Libre Connector
        =======================

        Conecta tu Odoo con Mercado Libre de forma profesional.

        Características principales:
        ----------------------------
        * Autenticación OAuth 2.0 con refresh automático
        * Soporte multi-empresa y multi-tienda
        * Sistema de logs robusto
        * API Playground para pruebas
        * Invitaciones por email
        * Auto-retry en errores de token
        * Gestión de tokens con health status

        Países soportados:
        ------------------
        * México (MLM)
        * Argentina (MLA)
        * Brasil (MLB)
        * Colombia (MCO)
        * Chile (MLC)
        * Perú (MPE)
        * Y más...
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        # Seguridad
        'security/mercadolibre_security.xml',
        'security/ir.model.access.csv',
        'security/mercadolibre_rules.xml',

        # Data
        'data/ir_cron.xml',
        'data/mail_template_invitation.xml',
        'data/mail_template_connected.xml',
        'data/mercadolibre_playground_templates.xml',

        # Vistas
        'views/mercadolibre_config_views.xml',
        'views/mercadolibre_account_views.xml',
        'views/mercadolibre_invitation_views.xml',
        'views/mercadolibre_log_views.xml',
        'views/mercadolibre_playground_views.xml',
        'views/mercadolibre_menus.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mercadolibre_connector/static/src/js/playground_editor.js',
        ],
    },
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}
