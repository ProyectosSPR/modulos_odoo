# -*- coding: utf-8 -*-
{
    'name': 'AI Tools for Odoo',
    'version': '16.0.1.0.0',
    'category': 'Tools/AI',
    'summary': 'Pre-built AI tools for querying and interacting with Odoo data',
    'description': """
AI Tools for Odoo - Business Data Access
=========================================

This module provides ready-to-use AI tools for:
- Searching products and checking stock
- Getting order status and history
- Customer information lookup
- Invoice and payment status
- CRM lead information
- Creating activity tasks

All tools are designed to be used by AI agents to answer
customer questions and perform actions in Odoo.
    """,
    'author': 'DML',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'ai_agent_core',
        'ai_activity_pipeline',
        'sale',
        'stock',
        'account',
        'crm',
        'product',
    ],
    'data': [
        'data/ai_tools_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
