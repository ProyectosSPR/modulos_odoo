# -*- coding: utf-8 -*-
from odoo import models, fields

class PxShipment(models.Model):
    _name = "px.shipment.tracking"

    name = fields.Char(string='Codigo de envio')
    details = fields.One2many('px.shipment.tracking.details', 'shipment_id', string='Detalles')

class PxShipment(models.Model):
    _name = "px.shipment.tracking.details"

    shipment_id = fields.Many2one('px.shipment.tracking', string='Envio', ondelete='cascade', index=True)

    date = fields.Char('Fecha')
    time = fields.Char('Hora')
    branch = fields.Char('Sucursal')
    status = fields.Char('Estado')
    event_id = fields.Char('Evento ID')
    event_description = fields.Char('Evento Descripcion')
    event_image = fields.Char('Evento Imagen')
    origin_branch = fields.Char('Sucursal Origen')
    promise = fields.Char('Promesa')
    destination_city = fields.Char('Ciudad Destino')
    event_city = fields.Char('Ciudad Evento')
    guide = fields.Char('Guia')
    tracking = fields.Char('Rastreo')
    reference = fields.Char('Referencia')
    delivery_type = fields.Char('Tipo de Entrega')
    datetime = fields.Char('Fecha y Hora')
    destination_branch = fields.Char('Sucursal Destino')
