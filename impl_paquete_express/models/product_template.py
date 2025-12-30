# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = "product.template"
    
    x_px_shp_code = fields.Many2one(
        comodel_name="px.anexo.01",
        string="Tipo de paquete"
    )

