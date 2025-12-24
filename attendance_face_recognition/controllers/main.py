from odoo import http
from odoo.http import request
import base64

class HrAttendanceFaceRecognition(http.Controller):
    
    @http.route('/attendance_face_recognition/loadLabeledImages/', type='json', auth="none")
    def load_labeled_images(self):
        descriptions = []
        employees = request.env['hr.employee'].sudo().search([])
        for employee in employees:
            descriptors = []
            for faces in employee.user_faces:
                if faces.descriptor and faces.descriptor != 'false':
                    descriptors.append(faces.descriptor)
            if descriptors:
                vals = {
                    "label": employee.id,
                    "descriptors": descriptors,
                }
                descriptions.append(vals)
        return descriptions

    @http.route('/attendance_face_recognition/getName/<int:employee_id>/', type='json', auth="none")
    def get_name(self,employee_id):
        name = False
        if employee_id:
            employee = request.env['hr.employee'].sudo().search([('id', '=', int(employee_id))])
            name =  employee.name
        return name