# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreShipmentStatusHistory(models.Model):
    _name = 'mercadolibre.shipment.status.history'
    _description = 'Historial de Estados de Envio'
    _order = 'date desc, id desc'

    shipment_id = fields.Many2one(
        'mercadolibre.shipment',
        string='Envio',
        required=True,
        ondelete='cascade',
        index=True
    )

    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('handling', 'En Preparacion'),
        ('ready_to_ship', 'Listo para Enviar'),
        ('shipped', 'Enviado'),
        ('in_transit', 'En Transito'),
        ('out_for_delivery', 'En Reparto'),
        ('delivered', 'Entregado'),
        ('not_delivered', 'No Entregado'),
        ('returned', 'Devuelto'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', required=True, index=True)

    substatus = fields.Char(
        string='Subestado'
    )

    date = fields.Datetime(
        string='Fecha',
        required=True,
        default=fields.Datetime.now
    )

    notes = fields.Text(
        string='Notas'
    )

    @api.model
    def get_status_label(self, status):
        """Obtiene la etiqueta del estado"""
        status_dict = dict(self._fields['status'].selection)
        return status_dict.get(status, status)
