# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class MercadolibreOrder(models.Model):
    _inherit = 'mercadolibre.order'

    # Relacion con envio
    shipment_id = fields.Many2one(
        'mercadolibre.shipment',
        string='Envio',
        compute='_compute_shipment_id',
        store=True,
        readonly=True
    )

    shipment_status = fields.Selection(
        related='shipment_id.status',
        string='Estado Envio',
        store=True,
        readonly=True
    )

    shipment_tracking = fields.Char(
        related='shipment_id.tracking_number',
        string='Numero de Guia',
        readonly=True
    )

    shipment_carrier = fields.Char(
        related='shipment_id.carrier_name',
        string='Transportista',
        readonly=True
    )

    has_shipment = fields.Boolean(
        string='Tiene Envio',
        compute='_compute_has_shipment',
        store=True
    )

    # Direccion de entrega (desde shipment)
    delivery_address = fields.Char(
        related='shipment_id.address_line',
        string='Direccion de Entrega',
        readonly=True
    )

    delivery_city = fields.Char(
        related='shipment_id.city',
        string='Ciudad Entrega',
        readonly=True
    )

    delivery_state = fields.Char(
        related='shipment_id.state',
        string='Estado Entrega',
        readonly=True
    )

    @api.depends('ml_shipment_id', 'account_id')
    def _compute_shipment_id(self):
        """Busca el shipment asociado a esta orden"""
        Shipment = self.env['mercadolibre.shipment']
        for record in self:
            if record.ml_shipment_id:
                shipment = Shipment.search([
                    ('ml_shipment_id', '=', record.ml_shipment_id),
                    ('account_id', '=', record.account_id.id)
                ], limit=1)
                record.shipment_id = shipment.id if shipment else False
            else:
                record.shipment_id = False

    @api.depends('shipment_id')
    def _compute_has_shipment(self):
        for record in self:
            record.has_shipment = bool(record.shipment_id)

    def action_sync_shipment(self):
        """Sincroniza el envio de esta orden desde la API"""
        self.ensure_one()

        if not self.ml_shipment_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Envio'),
                    'message': _('Esta orden no tiene ID de envio'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        Shipment = self.env['mercadolibre.shipment']
        shipment = Shipment.sync_shipment_by_id(self.ml_shipment_id, self.account_id)

        if shipment:
            # Vincular el shipment con esta orden
            if not shipment.order_id:
                shipment.order_id = self.id

            # Actualizar logistic_type en la orden si es diferente
            if shipment.logistic_type and self.logistic_type != shipment.logistic_type:
                self.write({'logistic_type': shipment.logistic_type})
                _logger.info('Actualizado logistic_type de orden %s a %s',
                           self.ml_order_id, shipment.logistic_type)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronizacion exitosa'),
                    'message': _('Envio sincronizado: %s - Estado: %s') % (
                        shipment.name,
                        dict(shipment._fields['status'].selection).get(shipment.status, '')
                    ),
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

    def action_view_shipment(self):
        """Ver el envio asociado"""
        self.ensure_one()

        if not self.shipment_id:
            # Si no hay shipment pero hay ID, intentar sincronizar primero
            if self.ml_shipment_id:
                return self.action_sync_shipment()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Envio'),
                    'message': _('Esta orden no tiene envio asociado'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Envio'),
            'res_model': 'mercadolibre.shipment',
            'res_id': self.shipment_id.id,
            'view_mode': 'form',
        }

    def action_download_label(self):
        """Descarga la etiqueta de envio"""
        self.ensure_one()

        if not self.shipment_id:
            if self.ml_shipment_id:
                # Sincronizar primero
                self.action_sync_shipment()
                self._compute_shipment_id()

        if self.shipment_id:
            return self.shipment_id.action_download_label_pdf()
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Envio'),
                    'message': _('No hay envio para descargar etiqueta'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
