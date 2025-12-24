# -*- coding: utf-8 -*-
{
    'name': 'Dashboard picking',
    'summary': 'Dashboard picking',
    'description': 'Dashboard picking',
    'version': '16.20250226',
    'category': 'Stock/Stock',
    'author': 'Eduardo Velaochaga - eduardo_velaochaga@yahoo.com',
    'depends': [
        'stock',
    ],
    'data': [
        'views/stock_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dashboard_picking/static/src/js/*.js',
            'dashboard_picking/static/src/xml/*.xml',
            'dashboard_picking/static/src/scss/*.scss',

            # Don't include dark mode files in light mode
            ('remove', 'dashboard_picking/static/src/scss/*.dark.scss'),
        ],
        'web.dark_mode_assets_backend': [
            'dashboard_picking/static/src/scss/*.dark.scss',
        ],
    },
}
