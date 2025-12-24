# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Connector',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'summary': 'Integración con MercadoLibre - Multi-empresa y Multi-tienda',
    'description': """
        Conector MercadoLibre para Odoo 16
        ===================================

        Características principales:
        * Autenticación OAuth 2.0 con MercadoLibre
        * Soporte multi-empresa y multi-tienda
        * Actualización automática de tokens
        * Sistema de invitaciones por correo
        * API Playground para pruebas
        * Sistema de logs robusto
    """,
    'author': 'Tu Compañía',
    'website': 'https://www.tucompania.com',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        # Security
        'security/mercadolibre_security.xml',
        'security/ir.model.access.csv',
        'security/mercadolibre_rules.xml',

        # Data
        'data/ir_cron.xml',
        'data/mail_template_invitation.xml',
        'data/mail_template_connected.xml',

        # Views
        'views/mercadolibre_config_views.xml',
        'views/mercadolibre_account_views.xml',
        'views/mercadolibre_invitation_views.xml',
        'views/mercadolibre_log_views.xml',
        'views/mercadolibre_playground_views.xml',
        'views/mercadolibre_menus.xml',
        'views/templates.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
