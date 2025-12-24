from odoo import fields, models, api

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    kiosk_face_recognition = fields.Boolean(string="Face Recognition on Kiosk", default=False)