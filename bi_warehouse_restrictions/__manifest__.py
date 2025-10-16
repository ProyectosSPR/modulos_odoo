# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Warehouse Restriction for User | Stock Location Restriction',
    'version': '16.0.0.2',
    'category': 'Warehouse',
    'summary': 'User Warehouse Restriction Warehouse location restriction user restriction on warehouse location stock access control stock access rules stock restriction restrict warehouse restrict location operation restriction stock access rules warehouse access rules',
    'description': """ 

        Warehouse Restriction for User in odoo,
        Configure Restriction in odoo,
        Operation Types Restriction in odoo,
        Warehouse Locations Restriction in odoo,
        Warehouse Restriction in odoo,

    """,
    "author": "BROWSEINFO",
    "price": 23,
    "currency": 'EUR',
    "website" : "https://www.browseinfo.com/demo-request?app=bi_warehouse_restrictions&version=16&edition=Community ",
    'depends': ['base', 'stock'],
    'data': [
            'security/restriction_rules.xml',
            'views/res_users_inherited.xml',
            ],
    "license": "OPL-1",
    "auto_install": False,
    "installable": True,
    "live_test_url":'https://www.browseinfo.com/demo-request?app=bi_warehouse_restrictions&version=16&edition=Community ',
    "images":["static/description/Banner.gif"]
}
