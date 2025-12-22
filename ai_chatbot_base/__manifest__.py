# -*- coding: utf-8 -*-
{
    'name': 'AI Chatbot Base',
    'version': '16.0.1.0.0',
    'category': 'Tools/AI',
    'summary': 'Multi-channel router and message adapters for AI agents',
    'description': """
AI Chatbot Base - Multi-channel Communication Layer
====================================================

This module provides:
- Message routing between channels and AI agents
- Channel adapters for different platforms
- Message format conversion (plain text, markdown, HTML)
- Webhook handling for incoming messages
- Response formatting per channel requirements

Supported Channels:
- MercadoLibre (requires ai_channel_mercadolibre)
- WhatsApp (requires ai_channel_whatsapp)
- Telegram (requires ai_channel_telegram)
- Email
- Web Widget
    """,
    'author': 'DML',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'ai_agent_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_webhook_views.xml',
        'views/ai_chatbot_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
