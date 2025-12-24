# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MercadolibreClaimResolution(models.Model):
    _name = 'mercadolibre.claim.resolution'
    _description = 'Resolucion Esperada de Reclamo MercadoLibre'
    _order = 'date_created desc'

    claim_id = fields.Many2one(
        'mercadolibre.claim',
        string='Reclamo',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta',
        related='claim_id.account_id',
        store=True
    )

    # === PLAYER ===
    player_role = fields.Selection([
        ('complainant', 'Comprador'),
        ('respondent', 'Vendedor'),
        ('mediator', 'Mediador'),
    ], string='Rol', readonly=True)

    user_id = fields.Char(
        string='ID Usuario',
        readonly=True
    )

    # === RESOLUCION ===
    expected_resolution = fields.Selection([
        ('refund', 'Reembolso Total'),
        ('product', 'Recibir Producto'),
        ('change_product', 'Cambio de Producto'),
        ('return_product', 'Devolucion de Producto'),
        ('partial_refund', 'Reembolso Parcial'),
    ], string='Resolucion Esperada', readonly=True)

    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptada'),
        ('rejected', 'Rechazada'),
    ], string='Estado', readonly=True)

    # === DETALLES (para reembolso parcial) ===
    details = fields.Text(
        string='Detalles (JSON)',
        readonly=True
    )
    percentage = fields.Float(
        string='Porcentaje',
        readonly=True,
        help='Porcentaje de reembolso parcial'
    )
    seller_amount = fields.Float(
        string='Monto Vendedor',
        readonly=True
    )
    seller_currency = fields.Char(
        string='Moneda',
        readonly=True
    )

    # === FECHAS ===
    date_created = fields.Datetime(
        string='Fecha Creacion',
        readonly=True
    )
    date_last_updated = fields.Datetime(
        string='Ultima Actualizacion',
        readonly=True
    )

    display_name = fields.Char(
        compute='_compute_display_name'
    )

    @api.depends('expected_resolution', 'player_role', 'status')
    def _compute_display_name(self):
        resolution_labels = {
            'refund': 'Reembolso',
            'product': 'Producto',
            'change_product': 'Cambio',
            'return_product': 'Devolucion',
            'partial_refund': 'Reembolso Parcial',
        }
        role_labels = {
            'complainant': 'Comprador',
            'respondent': 'Vendedor',
            'mediator': 'Mediador',
        }
        for rec in self:
            resolution = resolution_labels.get(rec.expected_resolution, rec.expected_resolution or '')
            role = role_labels.get(rec.player_role, '')
            rec.display_name = f'{resolution} ({role})' if role else resolution

    @api.model
    def create_from_ml_data(self, data, claim):
        """Crea una resolucion desde datos de la API"""
        # Extraer detalles
        details = data.get('details', []) or []
        details_dict = {d.get('key'): d.get('value') for d in details if d.get('key')}

        vals = {
            'claim_id': claim.id,
            'player_role': data.get('player_role', ''),
            'user_id': str(data.get('user_id', '')),
            'expected_resolution': data.get('expected_resolution', ''),
            'status': data.get('status', ''),
            'details': json.dumps(details) if details else '',
            'percentage': float(details_dict.get('percentage', 0) or 0),
            'seller_amount': float(details_dict.get('seller_amount', 0) or 0),
            'seller_currency': details_dict.get('seller_currency', ''),
            'date_created': claim._parse_datetime(data.get('date_created')),
            'date_last_updated': claim._parse_datetime(data.get('last_updated')),
        }

        return self.create(vals)
