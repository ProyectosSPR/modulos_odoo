# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MercadolibreCategory(models.Model):
    _name = 'mercadolibre.category'
    _description = 'Categoria MercadoLibre'
    _parent_name = 'parent_id'
    _parent_store = True
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        index=True
    )
    ml_category_id = fields.Char(
        string='ID Categoria ML',
        required=True,
        index=True
    )
    parent_id = fields.Many2one(
        'mercadolibre.category',
        string='Categoria Padre',
        ondelete='cascade',
        index=True
    )
    parent_path = fields.Char(
        index=True
    )
    child_ids = fields.One2many(
        'mercadolibre.category',
        'parent_id',
        string='Subcategorias'
    )
    site_id = fields.Char(
        string='Sitio',
        default='MLM',
        help='Sitio de MercadoLibre (MLM=Mexico, MLA=Argentina, etc)'
    )
    path_from_root = fields.Char(
        string='Ruta Completa',
        compute='_compute_path_from_root',
        store=True
    )
    active = fields.Boolean(
        default=True
    )

    _sql_constraints = [
        ('ml_category_id_site_uniq', 'unique(ml_category_id, site_id)',
         'La categoria ya existe para este sitio.')
    ]

    @api.depends('name', 'parent_id', 'parent_id.path_from_root')
    def _compute_path_from_root(self):
        for record in self:
            if record.parent_id:
                record.path_from_root = f'{record.parent_id.path_from_root} / {record.name}'
            else:
                record.path_from_root = record.name

    @api.model
    def get_or_create_from_ml(self, ml_category_id, site_id='MLM', account=None):
        """
        Obtiene o crea una categoria desde MercadoLibre.

        Args:
            ml_category_id: ID de la categoria en ML
            site_id: Sitio de ML
            account: Cuenta ML para hacer request (opcional)

        Returns:
            mercadolibre.category record
        """
        existing = self.search([
            ('ml_category_id', '=', ml_category_id),
            ('site_id', '=', site_id)
        ], limit=1)

        if existing:
            return existing

        # Obtener datos de la categoria desde ML
        try:
            import requests
            url = f'https://api.mercadolibre.com/categories/{ml_category_id}'
            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                _logger.warning('No se pudo obtener categoria %s: %s',
                              ml_category_id, response.status_code)
                # Crear con datos minimos
                return self.create({
                    'name': ml_category_id,
                    'ml_category_id': ml_category_id,
                    'site_id': site_id,
                })

            data = response.json()

            # Crear categoria padre si existe
            parent = False
            path_from_root = data.get('path_from_root', [])
            if len(path_from_root) > 1:
                # El ultimo es la categoria actual, el penultimo es el padre
                parent_data = path_from_root[-2]
                parent = self.get_or_create_from_ml(
                    parent_data.get('id'),
                    site_id,
                    account
                )

            return self.create({
                'name': data.get('name', ml_category_id),
                'ml_category_id': ml_category_id,
                'site_id': site_id,
                'parent_id': parent.id if parent else False,
            })

        except Exception as e:
            _logger.error('Error obteniendo categoria %s: %s', ml_category_id, str(e))
            # Crear con datos minimos
            return self.create({
                'name': ml_category_id,
                'ml_category_id': ml_category_id,
                'site_id': site_id,
            })

    def action_refresh_from_ml(self):
        """Actualiza la categoria desde MercadoLibre"""
        self.ensure_one()

        try:
            import requests
            url = f'https://api.mercadolibre.com/categories/{self.ml_category_id}'
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                self.write({
                    'name': data.get('name', self.name),
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Categoria Actualizada'),
                        'message': _('La categoria se actualizo correctamente.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            raise UserError(_('Error actualizando categoria: %s') % str(e))

    @api.model
    def action_sync_root_categories(self, site_id='MLM'):
        """
        Sincroniza las categorias raiz de MercadoLibre.
        Este metodo se puede llamar desde un boton o manualmente.
        """
        import requests

        url = f'https://api.mercadolibre.com/sites/{site_id}/categories'
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                raise UserError(_('Error obteniendo categorias: %s') % response.status_code)

            categories_data = response.json()
            created_count = 0
            updated_count = 0

            for cat_data in categories_data:
                existing = self.search([
                    ('ml_category_id', '=', cat_data.get('id')),
                    ('site_id', '=', site_id)
                ], limit=1)

                if existing:
                    existing.write({'name': cat_data.get('name')})
                    updated_count += 1
                else:
                    self.create({
                        'name': cat_data.get('name'),
                        'ml_category_id': cat_data.get('id'),
                        'site_id': site_id,
                    })
                    created_count += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronizacion Completada'),
                    'message': _('Creadas: %d, Actualizadas: %d') % (created_count, updated_count),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            raise UserError(_('Error sincronizando categorias: %s') % str(e))

    @api.model
    def action_sync_subcategories(self, parent_ml_id, site_id='MLM'):
        """
        Sincroniza las subcategorias de una categoria padre.
        """
        import requests

        url = f'https://api.mercadolibre.com/categories/{parent_ml_id}'
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                raise UserError(_('Error obteniendo subcategorias: %s') % response.status_code)

            data = response.json()
            children = data.get('children_categories', [])

            if not children:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sin Subcategorias'),
                        'message': _('Esta categoria no tiene subcategorias o es una categoria final.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            # Obtener categoria padre
            parent = self.search([
                ('ml_category_id', '=', parent_ml_id),
                ('site_id', '=', site_id)
            ], limit=1)

            created_count = 0
            for child_data in children:
                existing = self.search([
                    ('ml_category_id', '=', child_data.get('id')),
                    ('site_id', '=', site_id)
                ], limit=1)

                if not existing:
                    self.create({
                        'name': child_data.get('name'),
                        'ml_category_id': child_data.get('id'),
                        'site_id': site_id,
                        'parent_id': parent.id if parent else False,
                    })
                    created_count += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Subcategorias Sincronizadas'),
                    'message': _('Se crearon %d subcategorias.') % created_count,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            raise UserError(_('Error sincronizando subcategorias: %s') % str(e))

    def action_load_children(self):
        """Carga las subcategorias de esta categoria"""
        self.ensure_one()
        return self.action_sync_subcategories(self.ml_category_id, self.site_id)

    def name_get(self):
        """Muestra la ruta completa en selectores"""
        result = []
        for record in self:
            if record.path_from_root:
                result.append((record.id, record.path_from_root))
            else:
                result.append((record.id, record.name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        """Busca por nombre o ID de categoria ML"""
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('ml_category_id', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid, order=order)
