# -*- coding: utf-8 -*-
{
    'name': 'Portal de Facturación',
    'version': '16.0.1.0.0',
    'category': 'Accounting/Portal',
    'summary': 'Portal de facturación para clientes de MercadoLibre',
    'description': """
Portal de Facturación - DML Médica
==================================

Portal web para que los clientes de MercadoLibre puedan:
- Iniciar sesión con su receiver_id o email
- Buscar sus órdenes de venta por referencia
- Subir su Constancia de Situación Fiscal (CSF)
- Solicitar facturación de múltiples órdenes
- Ver el progreso de su solicitud en tiempo real

Características:
- Validación híbrida de CSF (OCR local + IA fallback)
- Configuración dinámica de campos a extraer
- Integración con Google Gemini para extracción inteligente
- Barra de progreso en tiempo real
- Creación automática de clientes en Odoo
    """,
    'author': 'DML Médica',
    'website': 'https://www.dml-medica.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'account',
        'website',
        'portal',
        'l10n_mx_edi',
    ],
    'data': [
        # Seguridad
        'security/billing_portal_security.xml',
        'security/ir.model.access.csv',
        # Datos
        'data/csf_fields_data.xml',
        'data/billing_status_data.xml',
        'data/billing_settings_data.xml',
        # Vistas Backend
        'views/csf_field_config_views.xml',
        'views/billing_request_views.xml',
        'views/billing_settings_views.xml',
        'views/res_partner_views.xml',
        'views/menu.xml',
        # Vistas Portal
        'views/portal_templates.xml',
        'views/portal_login_templates.xml',
        'views/portal_orders_templates.xml',
        'views/portal_billing_form_templates.xml',
        'views/portal_progress_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'billing_portal/static/src/css/billing_portal.css',
            'billing_portal/static/src/js/billing_portal.js',
            'billing_portal/static/src/js/csf_uploader.js',
            'billing_portal/static/src/js/progress_tracker.js',
            'billing_portal/static/src/js/order_selector.js',
        ],
    },
    'external_dependencies': {
        'python': ['PyMuPDF', 'requests'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
