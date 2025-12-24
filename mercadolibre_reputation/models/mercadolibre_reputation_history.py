# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreReputationHistory(models.Model):
    _name = 'mercadolibre.reputation.history'
    _description = 'Historial de Reputación'
    _order = 'date desc'

    reputation_id = fields.Many2one(
        'mercadolibre.seller.reputation',
        string='Reputación',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        index=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    date = fields.Date(
        string='Fecha',
        required=True,
        index=True
    )

    # === NIVEL ===
    level_id = fields.Selection([
        ('5_green', 'Verde'),
        ('4_light_green', 'Verde Claro'),
        ('3_yellow', 'Amarillo'),
        ('2_orange', 'Naranja'),
        ('1_red', 'Rojo'),
        ('newbie', 'Sin Reputación'),
    ], string='Nivel')

    # === METRICAS ===
    claims_rate = fields.Float(
        string='Tasa Reclamos (%)',
        digits=(5, 4)
    )
    cancellations_rate = fields.Float(
        string='Tasa Cancelaciones (%)',
        digits=(5, 4)
    )
    delayed_rate = fields.Float(
        string='Tasa Despacho Tardío (%)',
        digits=(5, 4)
    )
    sales_completed = fields.Integer(
        string='Ventas Completadas'
    )

    _sql_constraints = [
        ('reputation_date_uniq', 'unique(reputation_id, date)',
         'Ya existe un registro para esta fecha.')
    ]
