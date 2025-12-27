# -*- coding: utf-8 -*-
{
    'name': 'Kafka Migration Hub',
    'version': '16.0.1.0.0',
    'category': 'Tools/Migration',
    'summary': 'Migración universal de ERPs a Odoo con Apache Kafka e IA',
    'description': """
        Kafka Migration Hub
        ===================

        Sistema inteligente de migración de datos que permite:

        * Migrar desde cualquier ERP (SAP, Oracle, SQL Server, etc.) a Odoo
        * Migrar entre versiones de Odoo (13, 14, 15, 16, 17, 18, 19)
        * Análisis automático de esquemas con IA
        * Mapeo visual de tablas y campos
        * Migración en tiempo real con Apache Kafka
        * Portal self-service para clientes
        * Monitor de progreso en tiempo real

        Características:
        ----------------
        * Detección dinámica de estructura Odoo
        * Tópicos personalizables por usuario
        * Sugerencias de mapeo con IA (GPT/Claude)
        * Resolución automática de dependencias
        * Cola de errores (Dead Letter Queue)
        * Dashboard con estadísticas
    """,
    'author': 'SPR',
    'website': 'https://github.com/ProyectosSPR/modulos_odoo',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'portal',
        'web',
        'mail',
    ],
    'data': [
        # Security
        'security/migration_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/default_topics.xml',
        'data/kafka_config.xml',
        'data/ir_cron.xml',

        # Views - Backend (orden importante por dependencias)
        'views/migration_topic_views.xml',
        'views/source_connection_views.xml',
        'views/table_mapping_views.xml',
        'views/migration_log_views.xml',
        'views/wizard_views.xml',
        'views/migration_project_views.xml',
        'views/res_config_settings_views.xml',
        'views/odoo_connection_views.xml',
        'views/menus.xml',

        # Views - Portal
        'views/portal/portal_templates.xml',
        'views/portal/portal_dashboard.xml',
        'views/portal/portal_project.xml',
        'views/portal/portal_wizard.xml',
        'views/portal/portal_monitor.xml',
        'views/portal/portal_visual_mapper.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'kafka_migration_hub/static/src/css/portal_style.css',
            'kafka_migration_hub/static/src/css/visual_mapper.css',
            'kafka_migration_hub/static/src/js/portal_dashboard.js',
            'kafka_migration_hub/static/src/js/schema_visualizer.js',
            'kafka_migration_hub/static/src/js/drag_drop_mapper.js',
            'kafka_migration_hub/static/src/js/live_monitor.js',
            'kafka_migration_hub/static/src/js/visual_mapper.js',
        ],
        'web.assets_backend': [
            'kafka_migration_hub/static/src/css/backend_style.css',
            'kafka_migration_hub/static/src/css/visual_mapper.css',
        ],
    },
    'external_dependencies': {
        'python': [
            'confluent_kafka',
            'psycopg2',
            'pymysql',
            'cx_Oracle',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
