# -*- coding: utf-8 -*-
{
    'name': 'MercadoLibre Label Editor',
    'version': '16.0.1.1.0',
    'category': 'Sales',
    'summary': 'Personaliza etiquetas de MercadoLibre con campos dinámicos',
    'description': """
MercadoLibre Label Editor
=========================

Personaliza etiquetas de envío de MercadoLibre agregando información adicional
como número de orden, datos del cliente, fechas, etc.

Características principales:
* Editor de plantillas con campos personalizables
* Campos dinámicos usando variables (${sale_order.name})
* Configuración de posición, fuente, color y rotación
* Integración automática al descargar etiquetas ML
* Vista previa con datos de ejemplo
* Soporte multi-empresa

Flujo de trabajo:
1. Crea una plantilla con campos personalizados
2. Asigna la plantilla a un tipo logístico
3. Al descargar etiquetas ML, se aplica automáticamente
4. El PDF personalizado se guarda como adjunto

Variables disponibles:
* ${sale_order.name} - Número de orden
* ${sale_order.partner_id.name} - Cliente
* ${ml_order.ml_order_id} - ID orden ML
* ${today} - Fecha actual
* Y muchas más...

Requisitos:
* mercadolibre_sales
* PyPDF2
* reportlab
* pdf2image (opcional, para preview)
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'license': 'LGPL-3',
    'depends': [
        'mercadolibre_sales',
        'web',
    ],
    'external_dependencies': {
        'python': [
            'PyPDF2',
            'reportlab',
        ]
    },
    'data': [
        # Security
        'security/ml_label_security.xml',
        'security/ir.model.access.csv',

        # Views
        'views/ml_label_template_views.xml',
        'views/ml_label_editor_views.xml',
        'views/mercadolibre_logistic_type_views.xml',
        'views/mercadolibre_order_views.xml',

        # Wizard
        'wizard/ml_label_preview_wizard_views.xml',

        # Data
        'data/ml_label_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mercadolibre_label_editor/static/src/scss/label_editor.scss',
            'mercadolibre_label_editor/static/src/js/label_editor_widget.js',
            'mercadolibre_label_editor/static/src/xml/label_editor_template.xml',
            # PDF.js from CDN (loaded dynamically in widget)
        ],
    },
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': None,
}
