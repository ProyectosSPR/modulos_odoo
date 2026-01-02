# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    px_quotation_data = fields.Char(string="Cotización")
    px_service_data = fields.Char(string="Servicio seleccionado")
    px_shipment_data = fields.Char(string="Servicio seleccionado")

    px_shipment_id = fields.One2many('px.shipment', 'sale_order_id', string='Envio paquete express')

    def action_view_paquete_express(self):
        self.ensure_one()
        if not self.px_shipment_id:
            raise UserError(_('No hay envio de Paquete Express para esta orden. Primero debe crear una cotizacion.'))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Envio paquete express',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'px.shipment',
            'view_id': self.env.ref('impl_paquete_express.view_px_shipment_form').id,
            'res_id': self.px_shipment_id[0].id,
            'target': 'new'
        }