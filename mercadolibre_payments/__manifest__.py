# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Payments',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Sincronizacion de pagos de MercadoPago con Odoo',
    'description': """
MercadoLibre Payments - Modulo de Pagos
=======================================

Este modulo permite sincronizar los pagos de MercadoPago con Odoo.

Funcionalidades:
----------------
* Sincronizacion de pagos desde MercadoPago
* Seguimiento de estados de pagos (approved, pending, rejected, etc.)
* Seguimiento de liberacion de dinero (released, pending, not_released)
* Detalle de cargos por pago (comisiones, impuestos, etc.)
* Filtros por estado, fechas, montos
* Sincronizacion manual y automatica via cron

Dependencias:
-------------
* mercadolibre_connector: Modulo base de conexion con MercadoLibre
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'license': 'LGPL-3',
    'depends': [
        'mercadolibre_connector',
        'account',
    ],
    'data': [
        'security/mercadolibre_payments_security.xml',
        'security/ir.model.access.csv',
        'security/mercadolibre_payments_rules.xml',
        'views/mercadolibre_payment_views.xml',
        'views/mercadolibre_payment_charge_views.xml',
        'wizard/mercadolibre_payment_sync_views.xml',
        'views/mercadolibre_payments_menus.xml',
        'data/mercadolibre_payments_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
