# -*- coding: utf-8 -*-
{
    'name': 'AI MCP MercadoLibre',
    'version': '16.0.1.0.0',
    'category': 'AI/MCP',
    'summary': 'Servidor MCP para integrar MercadoLibre con agentes IA',
    'description': """
        Módulo que expone servidores MCP (Model Context Protocol) para:
        - Consultar datos de MercadoLibre (órdenes, envíos, productos, etc.)
        - Acceder a documentación oficial de MercadoLibre

        Características:
        - Usa token siempre actualizado de mercadolibre_connector
        - Endpoints configurables desde la UI
        - Sistema de dependencias entre endpoints para guiar a la IA
        - Multi-cuenta (seleccionar cuenta por petición)
        - Logs completos de todas las peticiones
        - Integración con ai_agent_core
    """,
    'author': 'Tu Empresa',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'ai_agent_core',
        'mercadolibre_connector',
    ],
    'data': [
        # Security
        'security/ai_mcp_ml_security.xml',
        'security/ir.model.access.csv',
        # Views
        'views/ai_mcp_ml_server_views.xml',
        'views/ai_mcp_ml_endpoint_views.xml',
        'views/ai_mcp_ml_log_views.xml',
        'views/ai_mcp_ml_menus.xml',
        # Data
        'data/ai_mcp_ml_endpoints_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
