# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Shipments',
    'version': '16.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Gestion de envios de MercadoLibre',
    'description': """
MercadoLibre Shipments - Modulo de Envios
=========================================

Este modulo permite gestionar y sincronizar los envios de MercadoLibre con Odoo.

Funcionalidades:
----------------
* Sincronizacion de datos de envio desde MercadoLibre
* Seguimiento de estados del envio (pendiente, enviado, entregado, etc)
* Informacion de tracking y numero de guia
* Datos del transportista y tipo logistico
* Direccion de entrega completa
* Historial de cambios de estado
* Relacion con ordenes de venta de Odoo
* Descarga de etiquetas de envio

Estados soportados:
-------------------
* pending: Pendiente de envio
* ready_to_ship: Listo para enviar
* shipped: Enviado
* delivered: Entregado
* not_delivered: No entregado
* cancelled: Cancelado

Dependencias:
-------------
* mercadolibre_sales: Modulo de ventas de MercadoLibre
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'license': 'LGPL-3',
    'depends': [
        'mercadolibre_sales',
        'stock',
        'delivery',
    ],
    'data': [
        'security/mercadolibre_shipments_security.xml',
        'security/ir.model.access.csv',
        'views/mercadolibre_shipment_views.xml',
        'views/mercadolibre_shipment_status_history_views.xml',
        'views/mercadolibre_order_views.xml',
        'views/sale_order_views.xml',
        'views/mercadolibre_shipments_menus.xml',
        'wizard/mercadolibre_shipment_sync_views.xml',
        'data/mercadolibre_shipments_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
