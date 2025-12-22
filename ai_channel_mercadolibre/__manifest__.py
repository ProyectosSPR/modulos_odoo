# -*- coding: utf-8 -*-
{
    'name': 'AI Channel - MercadoLibre',
    'version': '16.0.1.0.0',
    'category': 'Tools/AI',
    'summary': 'MercadoLibre messaging integration for AI agents',
    'description': """
AI Channel MercadoLibre - Messaging Integration
================================================

This module provides:
- MercadoLibre messaging API integration
- Automatic response to customer messages
- Order and question context extraction
- Message formatting for MercadoLibre
- Webhook handler for incoming messages

Features:
- Connect AI agents to MercadoLibre accounts
- Auto-reply to customer questions
- Extract order context from conversations
- Handle attachments and special messages

Requirements:
- MercadoLibre seller account
- API credentials (App ID, Client Secret)
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
        'data/ai_channel_data.xml',
        'views/oauth_templates.xml',
        'views/meli_config_views.xml',
        'views/meli_message_views.xml',
        'views/meli_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
