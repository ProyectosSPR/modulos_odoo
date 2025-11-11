from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    kiosk_face_recognition = fields.Boolean(related="company_id.kiosk_face_recognition", string="Face Recognition on Kiosk", readonly=False)