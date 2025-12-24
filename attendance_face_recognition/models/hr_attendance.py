from odoo import fields, models, api

class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    check_in_image = fields.Binary(string="Check In Image", readonly=False)
    check_out_image = fields.Binary(string="Check Out Image", readonly=False)