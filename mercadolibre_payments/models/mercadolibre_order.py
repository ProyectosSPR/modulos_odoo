# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class MercadolibreOrderPaymentExtend(models.Model):
    """
    Extiende mercadolibre.order para agregar campo de liberación de dinero
    relacionado desde sale.order.
    """
    _inherit = 'mercadolibre.order'

    # Campo relacionado desde sale.order
    ml_money_release_status = fields.Selection(
        related='sale_order_id.ml_money_release_status',
        string='Dinero',
        store=False,  # No almacenar para evitar migración de BD
        readonly=True,
        help='Estado de liberación del dinero en MercadoPago'
    )
