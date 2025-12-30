# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResCompany(models.Model):
    _name = "px.anexo.01"

    name = fields.Char(string="Nombre")
    code = fields.Char(string="Codigo")