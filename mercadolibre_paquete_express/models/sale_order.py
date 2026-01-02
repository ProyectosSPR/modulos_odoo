# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Campos computados para mostrar direccion ML
    ml_shipping_address = fields.Text(
        string='Direccion Envio ML',
        compute='_compute_ml_shipping_address',
        help='Direccion de envio desde MercadoLibre'
    )
    ml_shipment_record_id = fields.Many2one(
        'mercadolibre.shipment',
        string='Envio ML',
        compute='_compute_ml_shipment_record',
        help='Registro de envio de MercadoLibre asociado'
    )
    has_ml_shipping_data = fields.Boolean(
        string='Tiene Datos Envio ML',
        compute='_compute_ml_shipping_address'
    )

    @api.depends('ml_order_id')
    def _compute_ml_shipment_record(self):
        for order in self:
            shipment = False
            if order.ml_order_id:
                ml_order = self.env['mercadolibre.order'].search([
                    ('ml_order_id', '=', order.ml_order_id)
                ], limit=1)
                if ml_order and ml_order.ml_shipment_id:
                    shipment = self.env['mercadolibre.shipment'].search([
                        ('ml_shipment_id', '=', ml_order.ml_shipment_id)
                    ], limit=1)
            order.ml_shipment_record_id = shipment

    @api.depends('ml_shipment_record_id')
    def _compute_ml_shipping_address(self):
        for order in self:
            address_parts = []
            has_data = False

            shipment = order.ml_shipment_record_id
            if shipment:
                if shipment.receiver_name:
                    address_parts.append(f'Receptor: {shipment.receiver_name}')
                    has_data = True
                if shipment.receiver_phone:
                    address_parts.append(f'Tel: {shipment.receiver_phone}')

                addr_line = []
                if shipment.street_name:
                    addr = shipment.street_name
                    if shipment.street_number:
                        addr += f' {shipment.street_number}'
                    addr_line.append(addr)
                if shipment.city:
                    addr_line.append(shipment.city)
                if shipment.state:
                    addr_line.append(shipment.state)
                if shipment.zip_code:
                    addr_line.append(f'CP {shipment.zip_code}')
                    has_data = True

                if addr_line:
                    address_parts.append(', '.join(addr_line))

                if shipment.comments:
                    address_parts.append(f'Ref: {shipment.comments}')

            order.ml_shipping_address = '\n'.join(address_parts) if address_parts else ''
            order.has_ml_shipping_data = has_data

    def action_open_px_quotation_wizard(self):
        """
        Abre el wizard de cotizacion de Paquete Express para ordenes ML.
        """
        self.ensure_one()

        # Validar que la orden tenga lineas
        if not self.order_line:
            raise UserError(_('La orden no tiene lineas de producto.'))

        # Validar productos con peso/volumen
        products_without_weight = []
        products_without_volume = []
        products_without_package = []

        for line in self.order_line:
            product = line.product_id
            if not product or product.type == 'service':
                continue

            if not product.weight:
                products_without_weight.append(product.name)
            if not product.volume:
                products_without_volume.append(product.name)
            if not hasattr(product, 'x_px_shp_code') or not product.x_px_shp_code:
                products_without_package.append(product.name)

        # Mostrar advertencia si hay productos sin configurar
        warning_messages = []
        if products_without_weight:
            warning_messages.append(
                f"Productos sin peso: {', '.join(products_without_weight[:3])}"
                + (f" y {len(products_without_weight) - 3} mas" if len(products_without_weight) > 3 else "")
            )
        if products_without_volume:
            warning_messages.append(
                f"Productos sin volumen: {', '.join(products_without_volume[:3])}"
                + (f" y {len(products_without_volume) - 3} mas" if len(products_without_volume) > 3 else "")
            )
        if products_without_package:
            warning_messages.append(
                f"Productos sin tipo de paquete: {', '.join(products_without_package[:3])}"
                + (f" y {len(products_without_package) - 3} mas" if len(products_without_package) > 3 else "")
            )

        # Por ahora solo advertencia en log, el wizard mostrara el error si falta algo
        if warning_messages:
            for msg in warning_messages:
                self.message_post(body=f"Advertencia cotizacion: {msg}")

        return {
            'type': 'ir.actions.act_window',
            'name': _('Cotizar Paquete Express'),
            'res_model': 'ml.px.quotation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_model': 'sale.order',
            }
        }

    def action_view_ml_shipment(self):
        """
        Ver el envio de MercadoLibre asociado.
        """
        self.ensure_one()
        if not self.ml_shipment_record_id:
            raise UserError(_('No hay envio de MercadoLibre asociado.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Envio MercadoLibre'),
            'res_model': 'mercadolibre.shipment',
            'res_id': self.ml_shipment_record_id.id,
            'view_mode': 'form',
        }
