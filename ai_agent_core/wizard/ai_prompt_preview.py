# -*- coding: utf-8 -*-
from odoo import models, fields


class AIAgentPromptPreview(models.TransientModel):
    _name = 'ai.agent.prompt.preview'
    _description = 'AI Agent Prompt Preview'

    agent_id = fields.Many2one('ai.agent', string='Agent', readonly=True)
    prompt_preview = fields.Text(string='Prompt Preview', readonly=True)
