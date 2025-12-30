# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = "res.company"
    
    x_px_uri = fields.Char(string="Uri paquete express", default="http://qaglp.paquetexpress.mx:7007")
    x_px_uri_ticket = fields.Char(string="Uri paquete express ticket", default="http://qaglp.paquetexpress.mx:8083")
    x_px_quotation_user = fields.Char(string="Usuario")
    x_px_quotation_password = fields.Char(string="Clave")
    x_px_quotation_type = fields.Char(string="Tipo")
    x_px_quotation_token = fields.Char(string="Token")

