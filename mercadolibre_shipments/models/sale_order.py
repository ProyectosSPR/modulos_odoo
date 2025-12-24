# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Relacion con envio ML
    ml_shipment_id_rel = fields.Many2one(
        'mercadolibre.shipment',
        string='Envio ML',
        compute='_compute_ml_shipment',
        store=True,
        readonly=True
    )

    ml_shipment_status = fields.Selection(
        related='ml_shipment_id_rel.status',
        string='Estado Envio ML',
        store=True,
        readonly=True
    )

    ml_tracking_number = fields.Char(
        related='ml_shipment_id_rel.tracking_number',
        string='Numero de Guia ML',
        readonly=True
    )

    ml_carrier_name = fields.Char(
        related='ml_shipment_id_rel.carrier_name',
        string='Transportista ML',
        readonly=True
    )

    ml_delivery_address = fields.Char(
        related='ml_shipment_id_rel.address_line',
        string='Direccion Entrega ML',
        readonly=True
    )

    ml_estimated_delivery = fields.Date(
        related='ml_shipment_id_rel.estimated_delivery_date',
        string='Entrega Estimada ML',
        readonly=True
    )

    @api.depends('ml_shipment_id')
    def _compute_ml_shipment(self):
        """Busca el shipment relacionado con esta orden de venta"""
        Shipment = self.env['mercadolibre.shipment']
        for record in self:
            if record.ml_shipment_id:
                shipment = Shipment.search([
                    ('ml_shipment_id', '=', record.ml_shipment_id)
                ], limit=1)
                record.ml_shipment_id_rel = shipment.id if shipment else False
            else:
                record.ml_shipment_id_rel = False

    def action_view_ml_shipment(self):
        """Ver el envio de MercadoLibre"""
        self.ensure_one()

        if not self.ml_shipment_id_rel:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Envio'),
                    'message': _('Esta orden no tiene envio de MercadoLibre asociado'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Envio MercadoLibre'),
            'res_model': 'mercadolibre.shipment',
            'res_id': self.ml_shipment_id_rel.id,
            'view_mode': 'form',
        }

    def action_sync_ml_shipment(self):
        """Sincroniza el envio de MercadoLibre"""
        self.ensure_one()

        if not self.ml_shipment_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Envio'),
                    'message': _('Esta orden no tiene ID de envio de MercadoLibre'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if not self.ml_account_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Cuenta'),
                    'message': _('Esta orden no tiene cuenta de MercadoLibre asociada'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        Shipment = self.env['mercadolibre.shipment']
        shipment = Shipment.sync_shipment_by_id(self.ml_shipment_id, self.ml_account_id)

        if shipment:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronizacion exitosa'),
                    'message': _('Envio sincronizado: %s') % shipment.name,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se pudo sincronizar el envio'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
