# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Billing',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Sincronización de facturación de MercadoLibre y MercadoPago',
    'description': """
MercadoLibre Billing - Módulo de Facturación
=============================================

Este módulo permite sincronizar las facturas y comisiones de MercadoLibre
y MercadoPago con Odoo.

Funcionalidades:
----------------
* Sincronización de facturas desde MercadoLibre (ML) y MercadoPago (MP)
* Soporte para BILL y CREDIT_NOTE
* Creación automática de Purchase Orders
* Conversión a facturas de proveedor
* Detección y registro de notas de crédito
* Sincronización manual y automática vía cron
* Configuración por cuenta ML/MP
* Sistema de logs robusto

Dependencias:
-------------
* mercadolibre_connector: Módulo base de conexión con MercadoLibre
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'license': 'LGPL-3',
    'depends': [
        'mercadolibre_connector',
        'purchase',
        'account',
        'mail',
    ],
    'data': [
        # Security
        'security/mercadolibre_billing_security.xml',
        'security/ir.model.access.csv',
        'security/mercadolibre_billing_rules.xml',

        # Data
        'data/product_data.xml',
        'data/mercadolibre_billing_cron.xml',

        # Views
        'views/mercadolibre_billing_period_views.xml',
        'views/mercadolibre_billing_detail_views.xml',
        'views/mercadolibre_billing_sync_config_views.xml',
        'views/purchase_order_views.xml',
        'views/account_move_views.xml',
        'views/mercadolibre_billing_menus.xml',

        # Wizard
        'wizard/mercadolibre_billing_sync_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
