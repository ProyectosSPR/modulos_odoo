# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Sales',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'summary': 'Sincronizacion de ordenes de MercadoLibre con Odoo',
    'description': """
MercadoLibre Sales - Modulo de Ventas
=====================================

Este modulo permite sincronizar las ordenes de venta de MercadoLibre con Odoo.

Funcionalidades:
----------------
* Sincronizacion de ordenes desde MercadoLibre
* Agrupacion por pack_id (carrito de compras)
* Manejo de descuentos y co-fondeo (ML + Vendedor)
* Configuracion por tipo logistico (Full, Agencia, Propio)
* Auto-confirmacion de picking segun tipo logistico
* Creacion automatica de sale.order en Odoo
* Sincronizacion manual y automatica via cron configurable
* Soporte para compradores y sus direcciones

Dependencias:
-------------
* mercadolibre_connector: Modulo base de conexion con MercadoLibre
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'license': 'LGPL-3',
    'depends': [
        'mercadolibre_connector',
        'sale_management',
        'stock',
        'delivery',
        'mail',
    ],
    'data': [
        'security/mercadolibre_sales_security.xml',
        'security/ir.model.access.csv',
        'data/mercadolibre_logistic_type_data.xml',
        'data/mercadolibre_sales_actions.xml',
        'views/mercadolibre_order_views.xml',
        'views/mercadolibre_order_item_views.xml',
        'views/mercadolibre_order_discount_views.xml',
        'views/mercadolibre_buyer_views.xml',
        'views/mercadolibre_logistic_type_views.xml',
        'views/mercadolibre_order_sync_config_views.xml',
        'views/mercadolibre_account_views.xml',
        'views/sale_order_views.xml',
        'wizard/mercadolibre_order_sync_views.xml',
        'views/mercadolibre_sales_menus.xml',
        'data/mercadolibre_sales_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
