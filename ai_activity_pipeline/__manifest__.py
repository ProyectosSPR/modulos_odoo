# -*- coding: utf-8 -*-
{
    'name': 'AI Activity Pipeline',
    'version': '16.0.1.0.0',
    'category': 'Tools/AI',
    'summary': 'Task queue and automation pipeline for AI-generated activities',
    'description': """
AI Activity Pipeline - Task Automation System
==============================================

This module provides:
- Task queue for AI-generated activities
- Human review workflow for pending tasks
- Automated task execution via cron
- Task validation and error handling
- Activity types: invoices, leads, tickets, emails, etc.

Features:
- Approval workflow before task execution
- Automatic data extraction from conversations
- Integration with Odoo business objects
- Task prioritization and scheduling
    """,
    'author': 'DML',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'ai_agent_core',
        'crm',
        'sale',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'views/ai_activity_task_views.xml',
        'views/ai_activity_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
