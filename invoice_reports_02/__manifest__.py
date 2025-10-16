# -*- coding: utf-8 -*-
##############################################################################
#                 @author IT Admin
#
##############################################################################

{
    'name': 'Formato de reporte de factura 02',
    'version': '16.01',
    'description': ''' Pagos y facturas
    ''',
    'category': 'Accounting',
    'author': 'IT Admin',
    'website': 'www.itadmin.com.mx',
    'depends': [
        'base',
        'account','cdfi_invoice','purchase',
    ],
    'data': [
        'report/invoice_report_custom.xml',
        'report/payment_report_custom.xml',
        'report/sale_report_custom.xml',
    ],
    'application': False,
    'installable': True,
    'price': 0.00,
    'currency': 'USD',
    'license': 'OPL-1',	
}
