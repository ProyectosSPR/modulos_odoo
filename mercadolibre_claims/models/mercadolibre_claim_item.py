# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class MercadolibreClaimItem(models.Model):
    """
    Items/Productos asociados a un reclamo.
    Almacena la información del producto de la orden reclamada.
    """
    _name = 'mercadolibre.claim.item'
    _description = 'Item de Reclamo MercadoLibre'
    _order = 'id'

    claim_id = fields.Many2one(
        'mercadolibre.claim',
        string='Reclamo',
        required=True,
        ondelete='cascade',
        index=True
    )

    # === IDENTIFICADORES ===
    ml_item_id = fields.Char(
        string='Item ID ML',
        readonly=True,
        index=True,
        help='ID del item/publicación en MercadoLibre'
    )
    ml_order_item_id = fields.Char(
        string='Order Item ID',
        readonly=True,
        help='ID del item dentro de la orden'
    )
    variation_id = fields.Char(
        string='Variación ID',
        readonly=True
    )

    # === INFORMACIÓN DEL PRODUCTO ===
    title = fields.Char(
        string='Título',
        readonly=True
    )
    category_id = fields.Char(
        string='Categoría ID',
        readonly=True
    )

    # === VARIACIÓN ===
    variation_name = fields.Char(
        string='Variación',
        readonly=True,
        help='Ej: Color: Rojo, Talla: M'
    )
    seller_sku = fields.Char(
        string='SKU Vendedor',
        readonly=True
    )

    # === CANTIDADES ===
    quantity = fields.Integer(
        string='Cantidad Comprada',
        readonly=True
    )
    claimed_quantity = fields.Integer(
        string='Cantidad Reclamada',
        readonly=True
    )

    # === PRECIOS ===
    unit_price = fields.Float(
        string='Precio Unitario',
        readonly=True,
        digits=(12, 2)
    )
    currency_id_ml = fields.Char(
        string='Moneda',
        readonly=True
    )
    total_amount = fields.Float(
        string='Monto Total',
        compute='_compute_total_amount',
        store=True,
        digits=(12, 2)
    )

    # === IMÁGENES ===
    thumbnail = fields.Char(
        string='URL Miniatura',
        readonly=True
    )
    picture_url = fields.Char(
        string='URL Imagen',
        readonly=True
    )

    # === CONDICIÓN ===
    condition = fields.Selection([
        ('new', 'Nuevo'),
        ('used', 'Usado'),
        ('refurbished', 'Reacondicionado'),
    ], string='Condición', readonly=True)

    # === GARANTÍA ===
    warranty = fields.Char(
        string='Garantía',
        readonly=True
    )

    # === ESTADO EN EL RECLAMO ===
    item_status = fields.Selection([
        ('claimed', 'Reclamado'),
        ('returned', 'Devuelto'),
        ('kept', 'Conservado por Comprador'),
    ], string='Estado del Item', default='claimed')

    @api.depends('unit_price', 'quantity')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = (record.unit_price or 0) * (record.quantity or 0)

    def name_get(self):
        result = []
        for record in self:
            name = record.title or record.ml_item_id or 'Item'
            if record.variation_name:
                name = f"{name} ({record.variation_name})"
            result.append((record.id, name))
        return result
