# -*- coding: utf-8 -*-

from odoo import models, fields, _


class TipoFlujo(models.Model):
    _name = 'tipo.flujo'
    _description = 'Tipo de Financiamiento'
    _rec_name = "descripcion"

    descripcion = fields.Char('Descripción') 
    tipo = fields.Selection(
        selection=[('01', 'Actividades Operativas'), 
                   ('02', 'Actividades de Inversión'), 
                   ('03', 'Actividades Financieras'),
                   ],
        string=_('Tipo de Flujo'),)


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    tipo_flujo = fields.Many2one('tipo.flujo', string='Tipo de flujo de efectivo')
