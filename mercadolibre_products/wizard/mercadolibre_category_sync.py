# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreCategorySync(models.TransientModel):
    _name = 'mercadolibre.category.sync'
    _description = 'Sincronizar Categorías de MercadoLibre'

    site_id = fields.Selection([
        ('MLM', 'México (MLM)'),
        ('MLA', 'Argentina (MLA)'),
        ('MLB', 'Brasil (MLB)'),
        ('MLC', 'Chile (MLC)'),
        ('MCO', 'Colombia (MCO)'),
        ('MLU', 'Uruguay (MLU)'),
        ('MPE', 'Perú (MPE)'),
        ('MLV', 'Venezuela (MLV)'),
        ('MEC', 'Ecuador (MEC)'),
        ('MBO', 'Bolivia (MBO)'),
        ('MPA', 'Panamá (MPA)'),
        ('MRD', 'Rep. Dominicana (MRD)'),
        ('MCR', 'Costa Rica (MCR)'),
        ('MGT', 'Guatemala (MGT)'),
        ('MHN', 'Honduras (MHN)'),
        ('MNI', 'Nicaragua (MNI)'),
        ('MSV', 'El Salvador (MSV)'),
        ('MPY', 'Paraguay (MPY)'),
    ], string='Sitio ML', default='MLM', required=True,
       help='Sitio de MercadoLibre del cual sincronizar categorías')

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        domain="[('state', '=', 'connected')]",
        help='Seleccione una cuenta para usar su sitio configurado'
    )

    sync_mode = fields.Selection([
        ('root', 'Solo Categorías Raíz'),
        ('specific', 'Categoría Específica'),
    ], string='Modo', default='root', required=True)

    category_id = fields.Many2one(
        'mercadolibre.category',
        string='Categoría',
        domain="[('site_id', '=', site_id)]",
        help='Categoría de la cual cargar subcategorías'
    )

    ml_category_id = fields.Char(
        string='ID Categoría ML',
        help='ID de categoría en MercadoLibre (ej: MLM1648)'
    )

    # Estadísticas
    existing_root_count = fields.Integer(
        string='Categorías Raíz Existentes',
        compute='_compute_stats'
    )
    existing_total_count = fields.Integer(
        string='Total Categorías',
        compute='_compute_stats'
    )

    @api.onchange('account_id')
    def _onchange_account_id(self):
        """Usa el sitio de la cuenta seleccionada"""
        if self.account_id:
            self.site_id = self.account_id.site_id

    @api.depends('site_id')
    def _compute_stats(self):
        CategoryModel = self.env['mercadolibre.category']
        for record in self:
            if record.site_id:
                record.existing_root_count = CategoryModel.search_count([
                    ('site_id', '=', record.site_id),
                    ('parent_id', '=', False)
                ])
                record.existing_total_count = CategoryModel.search_count([
                    ('site_id', '=', record.site_id)
                ])
            else:
                record.existing_root_count = 0
                record.existing_total_count = 0

    def action_sync(self):
        """Ejecuta la sincronización según el modo seleccionado"""
        self.ensure_one()
        CategoryModel = self.env['mercadolibre.category']

        if self.sync_mode == 'root':
            return CategoryModel.action_sync_root_categories(site_id=self.site_id)

        elif self.sync_mode == 'specific':
            if self.category_id:
                return self.category_id.action_load_children()
            elif self.ml_category_id:
                # Sincronizar por ID de ML directamente
                return CategoryModel.action_sync_subcategories(
                    self.ml_category_id,
                    self.site_id
                )
            else:
                raise UserError(_('Debe seleccionar una categoría o ingresar un ID de MercadoLibre.'))

    def action_view_categories(self):
        """Ver las categorías del sitio seleccionado"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Categorías ML - %s') % self.site_id,
            'res_model': 'mercadolibre.category',
            'view_mode': 'tree,form',
            'domain': [('site_id', '=', self.site_id)],
            'context': {
                'default_site_id': self.site_id,
                'search_default_root_categories': 1,
            },
        }
