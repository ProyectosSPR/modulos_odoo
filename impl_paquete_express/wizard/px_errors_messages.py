# -*- coding: utf-8 -*-

from odoo import models, fields


class PxErrorsMessages(models.TransientModel):
    _name = 'px.errors.messages'

    name = fields.Char(string='Mensaje')
    details = fields.One2many('px.errors.messages.details', 'messages_id', string='Detalles')


class PxErrorsMessages(models.TransientModel):
    _name = 'px.errors.messages.details'

    messages_id = fields.Many2one('px.errors.messages', string='Mensaje', ondelete='cascade', index=True)
    code = fields.Char(string='Código')
    name = fields.Char(string='Descripción')