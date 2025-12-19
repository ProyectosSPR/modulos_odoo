# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreItemExperienceProblem(models.Model):
    _name = 'mercadolibre.item.experience.problem'
    _description = 'Problema de Experiencia de Compra'
    _order = 'order asc'

    experience_id = fields.Many2one(
        'mercadolibre.item.experience',
        string='Experiencia',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        related='experience_id.account_id',
        store=True,
        readonly=True
    )

    # Orden y prioridad
    order = fields.Integer(
        string='Orden',
        default=0
    )
    is_main_problem = fields.Boolean(
        string='Es Problema Principal',
        default=False
    )

    # === NIVEL 1 (Categoría principal) ===
    level_one_key = fields.Selection([
        ('PRODUCT', 'Producto'),
        ('OPERATION', 'Operación'),
        ('DELIVERY', 'Entrega'),
        ('OTHER', 'Otro'),
    ], string='Categoría (L1)')

    level_one_color = fields.Char(
        string='Color L1',
        help='Color hexadecimal del nivel 1'
    )

    level_one_title = fields.Char(
        string='Título L1',
        compute='_compute_level_titles',
        store=True
    )

    # === NIVEL 2 (Subcategoría) ===
    level_two_key = fields.Char(
        string='Clave L2'
    )
    level_two_title = fields.Char(
        string='Título L2',
        help='Ej: Estaban en mal estado, Dificultades para preparar'
    )

    # === NIVEL 3 (Detalle específico) ===
    level_three_key = fields.Char(
        string='Clave L3'
    )
    level_three_title = fields.Char(
        string='Título L3',
        help='Ej: El producto llegó dañado, No tenías stock'
    )

    # === SOLUCION SUGERIDA ===
    remedy = fields.Text(
        string='Solución Sugerida',
        help='Recomendación de MercadoLibre para solucionar el problema'
    )

    # === CANTIDADES ===
    claims_count = fields.Integer(
        string='Reclamos',
        default=0
    )
    cancellations_count = fields.Integer(
        string='Cancelaciones',
        default=0
    )
    total_count = fields.Integer(
        string='Total Problemas',
        compute='_compute_total_count',
        store=True
    )
    quantity_text = fields.Char(
        string='Cantidad (texto)',
        help='Ej: 3 problemas'
    )

    @api.depends('level_one_key')
    def _compute_level_titles(self):
        titles = {
            'PRODUCT': 'Con el producto entregado',
            'OPERATION': 'Al gestionar o preparar la venta',
            'DELIVERY': 'Al despachar o entregar el producto',
            'OTHER': 'Otros problemas',
        }
        for record in self:
            record.level_one_title = titles.get(record.level_one_key, '')

    @api.depends('claims_count', 'cancellations_count')
    def _compute_total_count(self):
        for record in self:
            record.total_count = record.claims_count + record.cancellations_count
