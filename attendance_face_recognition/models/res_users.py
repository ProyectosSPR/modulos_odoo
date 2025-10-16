from odoo import api, fields, models, modules, _

class ResUsers(models.Model):    
    _inherit = 'res.users'
    
    attendance_face_recognition = fields.Boolean(string="Attendances Face Recognition", default=False)

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['attendance_face_recognition']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['attendance_face_recognition']
    
    def attendance_face_recognition_reload(self):
        return {
            "type": "ir.actions.client",
            "tag": "reload_context"
        }

    @api.model
    def action_get_attendance_face_recognition(self):
        if self.env.user:
            return self.env['ir.actions.act_window']._for_xml_id('attendance_face_recognition.action_simple_face_recognition')
