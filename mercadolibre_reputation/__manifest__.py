# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Reputation',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'summary': 'Gestión de Reputación y Experiencia de Compra de MercadoLibre',
    'description': '''
MercadoLibre Reputation - Módulo de Reputación
===============================================

Este módulo permite gestionar y monitorear la reputación del vendedor
y la experiencia de compra por publicación en MercadoLibre.

Funcionalidades:
----------------
* Dashboard ejecutivo con métricas de reputación
* Reputación global del vendedor (nivel, power seller, métricas)
* Experiencia de compra por ítem/publicación
* Detalle de problemas y soluciones sugeridas
* Historial de evolución de métricas
* Sincronización automática configurable
* Alertas cuando métricas se acercan a límites
* Smart buttons en ventas y reclamos
* Vista Kanban de ítems por estado de experiencia

Dependencias:
-------------
* mercadolibre_connector: Módulo base de conexión con MercadoLibre
    ''',
    'author': 'DML',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'mercadolibre_connector',
        'mail',
    ],
    'data': [
        # Security
        'security/mercadolibre_reputation_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/ir_cron.xml',
        # Views
        'views/mercadolibre_seller_reputation_views.xml',
        'views/mercadolibre_item_experience_views.xml',
        'views/mercadolibre_reputation_sync_config_views.xml',
        'views/mercadolibre_reputation_history_views.xml',
        'views/mercadolibre_account_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mercadolibre_reputation/static/src/css/reputation.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
