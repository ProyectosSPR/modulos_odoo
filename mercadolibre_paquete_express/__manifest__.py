# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Paquete Express',
    'version': '16.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Integracion de Paquete Express con ordenes MercadoLibre',
    'description': """
MercadoLibre Paquete Express Integration
========================================

Este modulo complementa impl_paquete_express para trabajar con ordenes de MercadoLibre:

* Boton de cotizacion en ordenes de venta vinculadas a ML
* Formulario con direccion de envio pre-llenada desde ML
* Manejo de productos kit (suma de pesos/volumenes de componentes)
* Seleccion de tipo de paquete cuando hay multiples productos
* Entrada de direccion libre (no forzada desde partner)
* Opcion de enviar info de envio al cliente via mensaje ML
    """,
    'author': 'Tu Empresa',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'impl_paquete_express',
        'mercadolibre_sales',
        'mercadolibre_shipments',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/ml_px_quotation_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/px_quotation_response_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
