# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MercadolibreProductLink(models.TransientModel):
    _name = 'mercadolibre.product.link'
    _description = 'Asistente para Vincular Productos con Items ML'

    # Modo de vinculacion
    link_mode = fields.Selection([
        ('item_to_product', 'Vincular Item ML a Producto Odoo'),
        ('product_to_item', 'Vincular Producto Odoo a Item ML'),
    ], string='Modo', default='item_to_product', required=True)

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        domain="[('state', '=', 'connected')]"
    )

    # Item ML (cuando se vincula desde item)
    item_id = fields.Many2one(
        'mercadolibre.item',
        string='Item ML'
    )
    variation_id = fields.Many2one(
        'mercadolibre.item.variation',
        string='Variacion ML'
    )

    # Producto Odoo
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Plantilla Producto'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Variante Producto'
    )

    # Busqueda de item ML (cuando se vincula desde producto)
    search_ml_item_id = fields.Char(
        string='Buscar Item ML por ID',
        help='ID del item en MercadoLibre (ej: MLM123456789)'
    )
    search_result_ids = fields.Many2many(
        'mercadolibre.item',
        string='Items Encontrados',
        compute='_compute_search_results'
    )
    selected_item_id = fields.Many2one(
        'mercadolibre.item',
        string='Item Seleccionado'
    )
    selected_variation_id = fields.Many2one(
        'mercadolibre.item.variation',
        string='Variacion Seleccionada'
    )

    # Informacion
    item_info = fields.Text(
        string='Info Item',
        compute='_compute_item_info'
    )
    product_info = fields.Text(
        string='Info Producto',
        compute='_compute_product_info'
    )

    @api.depends('item_id', 'variation_id', 'selected_item_id')
    def _compute_item_info(self):
        for record in self:
            item = record.item_id or record.selected_item_id
            if item:
                info_lines = [
                    f'ID: {item.ml_item_id}',
                    f'Titulo: {item.title}',
                    f'Precio: ${item.price:,.2f}',
                    f'Stock: {item.available_quantity}',
                    f'Estado: {item.status}',
                ]
                if item.seller_sku:
                    info_lines.append(f'SKU: {item.seller_sku}')
                if item.seller_custom_field:
                    info_lines.append(f'Custom Field: {item.seller_custom_field}')
                if record.variation_id:
                    info_lines.append('')
                    info_lines.append('--- Variacion ---')
                    info_lines.append(f'ID Var: {record.variation_id.ml_variation_id}')
                    info_lines.append(f'Atributos: {record.variation_id.attribute_display}')
                    info_lines.append(f'Stock Var: {record.variation_id.available_quantity}')
                    if record.variation_id.seller_sku:
                        info_lines.append(f'SKU Var: {record.variation_id.seller_sku}')
                record.item_info = '\n'.join(info_lines)
            else:
                record.item_info = ''

    @api.depends('product_tmpl_id', 'product_id')
    def _compute_product_info(self):
        for record in self:
            product = record.product_id or (record.product_tmpl_id.product_variant_id if record.product_tmpl_id else False)
            if product:
                info_lines = [
                    f'Nombre: {product.name}',
                    f'Ref: {product.default_code or "Sin referencia"}',
                    f'Precio: ${product.lst_price:,.2f}',
                    f'Stock: {product.qty_available}',
                ]
                if product.barcode:
                    info_lines.append(f'Codigo Barras: {product.barcode}')
                record.product_info = '\n'.join(info_lines)
            else:
                record.product_info = ''

    @api.depends('search_ml_item_id', 'account_id')
    def _compute_search_results(self):
        for record in self:
            if record.search_ml_item_id and record.account_id:
                items = self.env['mercadolibre.item'].search([
                    ('ml_item_id', 'ilike', record.search_ml_item_id),
                    ('account_id', '=', record.account_id.id),
                ], limit=10)
                record.search_result_ids = items
            else:
                record.search_result_ids = False

    def action_search_item(self):
        """Busca un item en ML por su ID"""
        self.ensure_one()

        if not self.search_ml_item_id:
            raise ValidationError(_('Ingrese el ID del item a buscar.'))

        if not self.account_id:
            raise ValidationError(_('Seleccione una cuenta de MercadoLibre.'))

        ml_item_id = self.search_ml_item_id.strip().upper()

        # Buscar primero en registros locales
        existing = self.env['mercadolibre.item'].search([
            ('ml_item_id', '=', ml_item_id),
            ('account_id', '=', self.account_id.id),
        ], limit=1)

        if existing:
            self.selected_item_id = existing
            return {
                'type': 'ir.actions.act_window',
                'name': _('Vincular Producto'),
                'res_model': 'mercadolibre.product.link',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        # Si no existe, traerlo de ML
        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token valido.'))

        http = self.env['mercadolibre.http']
        ItemModel = self.env['mercadolibre.item']

        try:
            response = http._request(
                account_id=self.account_id.id,
                endpoint=f'/items/{ml_item_id}',
                method='GET'
            )
            item_data = response.get('data', {})

            if not item_data:
                raise UserError(_('Item no encontrado en MercadoLibre.'))

            # Crear registro local
            item, _ = ItemModel.create_from_ml_data(item_data, self.account_id)
            self.selected_item_id = item

        except Exception as e:
            raise UserError(_('Error buscando item: %s') % str(e))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Vincular Producto'),
            'res_model': 'mercadolibre.product.link',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_link(self):
        """Crea la vinculacion entre item ML y producto Odoo"""
        self.ensure_one()

        item = self.item_id or self.selected_item_id
        variation = self.variation_id or self.selected_variation_id
        product_tmpl = self.product_tmpl_id
        product = self.product_id

        if not item and not variation:
            raise ValidationError(_('Debe seleccionar un item o variacion de MercadoLibre.'))

        if not product_tmpl and not product:
            raise ValidationError(_('Debe seleccionar un producto de Odoo.'))

        # Determinar producto final
        if product:
            product_tmpl = product.product_tmpl_id
        elif product_tmpl:
            product = product_tmpl.product_variant_id

        # Crear vinculacion
        if variation:
            # Vincular variacion
            variation.write({'product_id': product.id})
            msg = _('Variacion %s vinculada a %s') % (variation.ml_variation_id, product.name)
        else:
            # Vincular item
            item.write({
                'product_id': product.id,
                'product_tmpl_id': product_tmpl.id,
            })
            msg = _('Item %s vinculado a %s') % (item.ml_item_id, product_tmpl.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vinculacion Exitosa'),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_unlink(self):
        """Elimina la vinculacion"""
        self.ensure_one()

        item = self.item_id or self.selected_item_id
        variation = self.variation_id or self.selected_variation_id

        if variation:
            variation.write({'product_id': False})
            msg = _('Variacion %s desvinculada') % variation.ml_variation_id
        elif item:
            item.write({
                'product_id': False,
                'product_tmpl_id': False,
            })
            msg = _('Item %s desvinculado') % item.ml_item_id
        else:
            raise ValidationError(_('No hay item o variacion para desvincular.'))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Desvinculacion Exitosa'),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.onchange('item_id')
    def _onchange_item_id(self):
        """Al seleccionar item, cargar su producto vinculado si existe"""
        if self.item_id:
            self.account_id = self.item_id.account_id
            if self.item_id.product_tmpl_id:
                self.product_tmpl_id = self.item_id.product_tmpl_id
            if self.item_id.product_id:
                self.product_id = self.item_id.product_id

    @api.onchange('variation_id')
    def _onchange_variation_id(self):
        """Al seleccionar variacion, cargar datos"""
        if self.variation_id:
            self.item_id = self.variation_id.item_id
            if self.variation_id.product_id:
                self.product_id = self.variation_id.product_id

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        """Al seleccionar template, mostrar items vinculados"""
        if self.product_tmpl_id:
            linked_items = self.env['mercadolibre.item'].search([
                ('product_tmpl_id', '=', self.product_tmpl_id.id)
            ], limit=1)
            if linked_items:
                self.selected_item_id = linked_items[0]
