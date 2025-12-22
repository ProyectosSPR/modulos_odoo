# -*- coding: utf-8 -*-
{
    'name': 'AI Agent Core',
    'version': '16.0.1.0.0',
    'category': 'Tools/AI',
    'summary': 'Core module for AI agents with LangGraph orchestration',
    'description': """
AI Agent Core - Intelligent Chatbot Framework
==============================================

Core module that provides:
- AI Agent configuration with structured prompts
- Behavior rules engine
- Multi-LLM provider support (Gemini, OpenAI, Anthropic, Ollama)
- LangGraph-based agent orchestration
- Tool registry for extending agent capabilities
- Conversation history management

This module serves as the foundation for building intelligent chatbots
that can interact with Odoo data and perform automated tasks.
    """,
    'author': 'DML',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'external_dependencies': {
        'python': [
            'langchain',
            'langchain-core',
            'langchain-google-genai',
            'langgraph',
        ],
    },
    'data': [
        'security/ai_security.xml',
        'security/ir.model.access.csv',
        'data/ai_provider_data.xml',
        'data/ai_tool_data.xml',
        'views/ai_agent_views.xml',
        'views/ai_provider_views.xml',
        'views/ai_prompt_views.xml',
        'views/ai_rule_views.xml',
        'views/ai_tool_views.xml',
        'views/ai_conversation_views.xml',
        'views/ai_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_agent_core/static/src/css/ai_agent.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
