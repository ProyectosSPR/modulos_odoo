# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError
import requests
import json
import base64
import platform
sistema = platform.system()


class PxShipment(models.Model):
    _name = "px.shipment"

    data = fields.Char(string='Codigo de seguimiento')
    object_dto = fields.Char(string='DTO')
    credit_amnt = fields.Float(string='Monto del Crédito')
    sub_totl_amnt = fields.Float(string='Monto Subtotal')
    total_amnt = fields.Float(string='Monto Total')
    pdf_ticket = fields.Binary(string='Ticket PDF')
    is_cancel = fields.Boolean(string='Fue cancelado')

    sale_order_id = fields.Many2one('sale.order', string='Orden', ondelete='cascade', required=True, unique=True)


    def px_api_print_ticket(self):
        url = "{0}/wsReportPaquetexpress/GenCartaPorte?trackingNoGen={1}&measure=4x6".format(self.env.company.x_px_uri_ticket, self.data)

        payload = ""
        headers = {
        'Content-Type': 'application/json'
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code is not 200:
            raise UserError("Ocurrio un error al obtener una respuesta del Api.")

        return response.content
    
    def px_api_tracking(self, tracking_cod):
        url = "{0}/ptxws/rest/api/v3/guia/historico/{1}/{2}".format(self.env.company.x_px_uri, tracking_cod, self.env.company.x_px_quotation_token)

        payload = ""
        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code is not 200:
            raise UserError("Ocurrio un error al obtener una respuesta del Api.")

        return json.loads(response.text)
    
    def px_api_cancelation(self, tracking_code):
        url = "{0}/RadRestFul/api/rad/v1/cancelguia".format(self.env.company.x_px_uri)

        payload = json.dumps({
            "header": {
                 "security":{  
                    "user": self.env.company.x_px_quotation_user,
                    "token": self.env.company.x_px_quotation_token
                }
            },
            "body": {  
                "request":{  
                    "data":[tracking_code]
                }
            }
        })

        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        if response.status_code is not 200:
            raise UserError("Ocurrio un error al obtener una respuesta del Api.")
        
        data = json.loads(response.text)
        
        print(json.dumps(data, indent=4))

        return data


    def action_tracking(self):
        data = self.px_api_tracking(self.data)

        data_tracking = data['body']['response']

        if not data_tracking['success']:
            #ERROR
            print("asd")

        details_tracking = []
        for record in data_tracking['data']:
            details_tracking.append((0, 0, {
                "date": record.get("fecha", ""),
                "time": record.get("hora", ""),
                "branch": record.get("sucursal", ""),
                "status": record.get("status", ""),
                "event_id": record.get("eventoId", ""),
                "event_description": record.get("eventoDescripcion", ""),
                "event_image": record.get("eventoImagen", ""),
                "origin_branch": record.get("sucursalOrigen", ""),
                "promise": record.get("promesa", ""),
                "destination_city": record.get("ciudadDestino", ""),
                "event_city": record.get("ciudadEvento", ""),
                "guide": record.get("guia", ""),
                "tracking": record.get("rastreo", ""),
                "reference": record.get("referencia", ""),
                "delivery_type": record.get("tipoEntrega", ""),
                "datetime": record.get("fechahora", ""),
                "destination_branch": record.get("sucursalDestino", "")
            }))

        data_create = {
            'name': self.data,
            'details': details_tracking
        }

        tracking_register = self.env['px.shipment.tracking'].create(data_create)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Seguimiento',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'px.shipment.tracking',
            'domain': [],
            'res_id': tracking_register.id,
            'context': {},
            'target': 'new'
        }


    def action_print_ticket(self):
        data = self.px_api_print_ticket()

        self.pdf_ticket = base64.b64encode(data)

        return {
            'res_model':
            'ir.actions.act_url',
            'type':
            'ir.actions.act_url',
            'target':
            'new',
            'url': ('/web/content/?model=px.shipment&id={0}'
                    '&filename_field={1}'
                    '&field=pdf_ticket&download=true'
                    '&filename={1}.pdf'.format(self.id, self.data)),
        }
        
    def action_cancelation(self):
        data = self.px_api_cancelation(self.data)

        data_tracking = data['body']['response']

        if data_tracking["success"]:
            self.is_cancel = True
        else:
            raise UserError("Ocurrio un error al obtener una respuesta del Api.")

