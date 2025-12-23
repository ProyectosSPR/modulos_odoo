# -*- coding: utf-8 -*-
from odoo import models, fields


class AIConversationExtend(models.Model):
    """Extend ai.conversation to add activity task relationship"""
    _inherit = 'ai.conversation'

    # Related activity tasks created from this conversation
    activity_task_ids = fields.One2many(
        'ai.activity.task',
        'conversation_id',
        string='Activity Tasks'
    )
    activity_task_count = fields.Integer(
        string='Tasks',
        compute='_compute_activity_task_count'
    )

    def _compute_activity_task_count(self):
        for record in self:
            record.activity_task_count = len(record.activity_task_ids)

    def action_view_activity_tasks(self):
        """View related activity tasks"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Activity Tasks',
            'res_model': 'ai.activity.task',
            'view_mode': 'tree,form',
            'domain': [('conversation_id', '=', self.id)],
            'context': {'default_conversation_id': self.id},
        }
