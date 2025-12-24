# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models


class InheritResUsers(models.Model):
    _inherit = 'res.users'


    restrict_operation = fields.Boolean(string="Restrict Operation")
    restrict_location = fields.Boolean(string="Restrict Location")
    restrict_warehouse_list = fields.Boolean(string="Restrict warehouse")

    warehouse_ids = fields.Many2many('stock.warehouse','rel_warehouse_restrictions', string="Allowed Warehouse")
    location_ids = fields.Many2many('stock.location', string="Allowed Location",check_company=True)
    operation_ids = fields.Many2many('stock.picking.type', string="Warehouse Operation")


    @api.onchange('restrict_operation')
    def _onchange_restrict_operation(self):
        if self.restrict_operation == False:
            self.operation_ids=[(6,0,[])]
        

    @api.onchange('restrict_location')
    def _onchange_restrict_location(self):
        if self.restrict_location == False :
            self.location_ids=[(6,0,[])]

    @api.onchange('restrict_warehouse_list')
    def _onchange_restrict_warehouse_list(self):
        if self.restrict_warehouse_list == False:
            self.warehouse_ids=[(6,0,[])]
    

    



