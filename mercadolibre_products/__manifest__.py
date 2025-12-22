# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Products',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'summary': 'Sincronizacion de productos entre MercadoLibre y Odoo',
    'description': """
MercadoLibre Products - Modulo de Productos
===========================================

Este modulo permite sincronizar productos entre MercadoLibre y Odoo.

Funcionalidades:
----------------
* Sincronizacion bidireccional de productos (ML <-> Odoo)
* Vinculacion por SKU, seller_custom_field o codigo de barras
* Sincronizacion selectiva de campos (precio, stock, titulo, descripcion, imagenes)
* Conciliacion de inventario ML vs Odoo con alertas de descuadre
* Publicacion de productos de Odoo a MercadoLibre
* Actualizacion automatica de stock desde Odoo a ML
* Soporte para productos con variaciones
* Configuracion flexible por cuenta ML
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
        'product',
        'stock',
        'sale',
        'mail',
    ],
    'data': [
        # Security
        'security/mercadolibre_products_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/mercadolibre_products_cron.xml',
        # Views
        'views/mercadolibre_item_views.xml',
        'views/mercadolibre_category_views.xml',
        'views/mercadolibre_product_sync_config_views.xml',
        'views/mercadolibre_stock_reconcile_views.xml',
        'views/mercadolibre_account_views.xml',
        'views/product_template_views.xml',
        'views/mercadolibre_products_menus.xml',
        # Wizards
        'wizard/mercadolibre_product_sync_views.xml',
        'wizard/mercadolibre_product_publish_views.xml',
        'wizard/mercadolibre_product_link_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
