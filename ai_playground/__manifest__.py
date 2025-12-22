# -*- coding: utf-8 -*-
{
    'name': 'AI Playground',
    'version': '16.0.1.0.0',
    'category': 'Tools/AI',
    'summary': 'Testing interface for AI agents with debug capabilities',
    'description': """
AI Playground - Agent Testing Environment
==========================================

This module provides:
- Interactive chat interface to test AI agents
- Channel simulation (test as MercadoLibre, WhatsApp, etc.)
- Debug panel showing prompts, tool calls, and responses
- Test different customer contexts
- Prompt preview and testing

Features:
- Real-time chat with AI agents
- View raw AI responses and tool executions
- Test behavior rules and triggers
- Simulate different channels and customers
    """,
    'author': 'DML',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'ai_agent_core',
        'ai_chatbot_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_playground_views.xml',
        'views/ai_playground_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_playground/static/src/css/playground.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
