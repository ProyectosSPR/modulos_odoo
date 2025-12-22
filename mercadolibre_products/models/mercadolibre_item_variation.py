# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreItemVariation(models.Model):
    _name = 'mercadolibre.item.variation'
    _description = 'Variacion de Item MercadoLibre'
    _order = 'item_id, id'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )

    # =====================================================
    # RELACIONES
    # =====================================================
    item_id = fields.Many2one(
        'mercadolibre.item',
        string='Item ML',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        related='item_id.account_id',
        store=True,
        readonly=True
    )

    # =====================================================
    # IDENTIFICADORES
    # =====================================================
    ml_variation_id = fields.Char(
        string='ID Variacion ML',
        required=True,
        index=True
    )

    # =====================================================
    # VINCULACION ODOO
    # =====================================================
    product_id = fields.Many2one(
        'product.product',
        string='Variante Odoo',
        ondelete='set null',
        index=True,
        help='Variante de producto de Odoo vinculada'
    )
    is_linked = fields.Boolean(
        string='Vinculado',
        compute='_compute_is_linked',
        store=True
    )

    # =====================================================
    # DATOS DE LA VARIACION
    # =====================================================
    price = fields.Float(
        string='Precio',
        digits='Product Price'
    )
    available_quantity = fields.Integer(
        string='Stock Disponible ML'
    )
    sold_quantity = fields.Integer(
        string='Vendidos',
        readonly=True
    )

    # SKU
    seller_sku = fields.Char(
        string='SKU Variacion',
        index=True,
        help='SELLER_SKU de esta variacion'
    )

    # Atributos (color, talla, etc)
    attribute_combinations = fields.Text(
        string='Combinacion Atributos',
        help='JSON con la combinacion de atributos'
    )
    attribute_display = fields.Char(
        string='Atributos',
        compute='_compute_attribute_display',
        store=True
    )

    # Imagenes
    picture_ids = fields.Char(
        string='IDs Imagenes',
        help='IDs de imagenes de esta variacion'
    )

    # =====================================================
    # STOCK COMPARISON
    # =====================================================
    odoo_stock = fields.Float(
        string='Stock Odoo',
        compute='_compute_odoo_stock',
        help='Stock disponible en Odoo'
    )
    stock_difference = fields.Float(
        string='Diferencia',
        compute='_compute_stock_difference',
        store=True
    )

    # =====================================================
    # SYNC
    # =====================================================
    last_sync = fields.Datetime(
        string='Ultima Sync'
    )
    active = fields.Boolean(
        default=True
    )

    _sql_constraints = [
        ('ml_variation_id_item_uniq', 'unique(ml_variation_id, item_id)',
         'La variacion ya existe para este item.')
    ]

    @api.depends('attribute_display', 'seller_sku', 'ml_variation_id')
    def _compute_name(self):
        for record in self:
            parts = []
            if record.attribute_display:
                parts.append(record.attribute_display)
            if record.seller_sku:
                parts.append(f'[{record.seller_sku}]')
            record.name = ' - '.join(parts) if parts else record.ml_variation_id

    @api.depends('product_id')
    def _compute_is_linked(self):
        for record in self:
            record.is_linked = bool(record.product_id)

    @api.depends('attribute_combinations')
    def _compute_attribute_display(self):
        for record in self:
            if record.attribute_combinations:
                try:
                    attrs = json.loads(record.attribute_combinations)
                    parts = []
                    for attr in attrs:
                        name = attr.get('name', attr.get('id', ''))
                        value = attr.get('value_name', '')
                        if name and value:
                            parts.append(f'{name}: {value}')
                    record.attribute_display = ', '.join(parts)
                except (json.JSONDecodeError, TypeError):
                    record.attribute_display = ''
            else:
                record.attribute_display = ''

    @api.depends('product_id', 'product_id.qty_available')
    def _compute_odoo_stock(self):
        for record in self:
            if record.product_id:
                record.odoo_stock = record.product_id.qty_available
            else:
                record.odoo_stock = 0

    @api.depends('available_quantity', 'odoo_stock', 'product_id')
    def _compute_stock_difference(self):
        for record in self:
            if record.is_linked:
                record.stock_difference = record.available_quantity - record.odoo_stock
            else:
                record.stock_difference = 0

    @api.model
    def create_from_ml_data(self, data, item):
        """
        Crea o actualiza una variacion desde datos de ML.

        Args:
            data: dict con datos de la variacion
            item: mercadolibre.item record

        Returns:
            mercadolibre.item.variation record
        """
        ml_variation_id = str(data.get('id', ''))
        if not ml_variation_id:
            return False

        existing = self.search([
            ('ml_variation_id', '=', ml_variation_id),
            ('item_id', '=', item.id)
        ], limit=1)

        # Extraer atributos
        attribute_combinations = data.get('attribute_combinations', [])

        # Extraer seller_sku
        seller_sku = ''
        for attr in attribute_combinations:
            if attr.get('id') == 'SELLER_SKU':
                seller_sku = attr.get('value_name', '')
                break

        # Si no viene en attribute_combinations, buscar en attributes
        if not seller_sku:
            attributes = data.get('attributes', [])
            for attr in attributes:
                if attr.get('id') == 'SELLER_SKU':
                    seller_sku = attr.get('value_name', '')
                    break

        vals = {
            'ml_variation_id': ml_variation_id,
            'item_id': item.id,
            'price': data.get('price', item.price),
            'available_quantity': data.get('available_quantity', 0),
            'sold_quantity': data.get('sold_quantity', 0),
            'seller_sku': seller_sku,
            'attribute_combinations': json.dumps(attribute_combinations) if attribute_combinations else False,
            'picture_ids': json.dumps(data.get('picture_ids', [])) if data.get('picture_ids') else False,
            'last_sync': fields.Datetime.now(),
            'active': True,
        }

        if existing:
            existing.write(vals)
            return existing
        else:
            return self.create(vals)

    def action_sync_stock_to_ml(self):
        """Envia el stock de esta variacion a ML"""
        self.ensure_one()

        if not self.is_linked:
            raise UserError(_('La variacion no esta vinculada a un producto de Odoo.'))

        if not self.item_id.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token valido.'))

        new_quantity = int(self.odoo_stock)
        http = self.env['mercadolibre.http']

        try:
            http._request(
                account_id=self.item_id.account_id.id,
                endpoint=f'/items/{self.item_id.ml_item_id}/variations/{self.ml_variation_id}',
                method='PUT',
                body={'available_quantity': new_quantity}
            )

            self.write({
                'available_quantity': new_quantity,
                'last_sync': fields.Datetime.now(),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Stock Actualizado'),
                    'message': _('Stock de variacion actualizado: %d unidades.') % new_quantity,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_('Error actualizando stock: %s') % str(e))

    def action_link_product(self):
        """Abre wizard para vincular variante"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vincular Variante'),
            'res_model': 'mercadolibre.product.link',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_variation_id': self.id,
                'default_item_id': self.item_id.id,
                'default_account_id': self.item_id.account_id.id,
            }
        }

    def action_auto_link_by_sku(self):
        """Intenta vincular automaticamente por SKU"""
        linked_count = 0
        for variation in self:
            if variation.is_linked:
                continue

            if variation.seller_sku:
                product = self.env['product.product'].search([
                    ('default_code', '=', variation.seller_sku)
                ], limit=1)

                if product:
                    variation.write({'product_id': product.id})
                    linked_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vinculacion Automatica'),
                'message': _('Se vincularon %d variaciones.') % linked_count,
                'type': 'success' if linked_count > 0 else 'warning',
                'sticky': False,
            }
        }
