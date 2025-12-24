from odoo import models
from odoo.http import request

class Http(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        user = self.env.user
        company = self.env.company
        result = super(Http, self).session_info()
        if self.env.user.has_group('base.group_user'):
            result['attendance_face_recognition'] = user.attendance_face_recognition
            result['kiosk_face_recognition'] = company.kiosk_face_recognition
        return result