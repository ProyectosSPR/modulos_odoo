# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # =====================================================
    # VINCULACION CON MERCADOLIBRE
    # =====================================================
    ml_item_ids = fields.One2many(
        'mercadolibre.item',
        'product_tmpl_id',
        string='Publicaciones ML'
    )
    ml_item_count = fields.Integer(
        string='Publicaciones ML',
        compute='_compute_ml_item_count'
    )
    has_ml_items = fields.Boolean(
        string='Tiene Publicaciones ML',
        compute='_compute_ml_item_count',
        store=True
    )

    # =====================================================
    # CONTROL DE SINCRONIZACION
    # =====================================================
    ml_sync_enabled = fields.Boolean(
        string='Sincronizar con ML',
        default=False,
        help='Habilitar sincronizacion automatica con MercadoLibre'
    )
    ml_auto_sync_stock = fields.Boolean(
        string='Auto-sync Stock a ML',
        default=True,
        help='Actualizar stock en ML automaticamente cuando cambie en Odoo'
    )
    ml_auto_sync_price = fields.Boolean(
        string='Auto-sync Precio a ML',
        default=False,
        help='Actualizar precio en ML automaticamente cuando cambie en Odoo'
    )
    ml_last_sync = fields.Datetime(
        string='Ultima Sync ML',
        readonly=True
    )

    # =====================================================
    # STOCK COMPARISON
    # =====================================================
    ml_total_stock = fields.Float(
        string='Stock Total ML',
        compute='_compute_ml_stock_info',
        help='Suma del stock disponible en todas las publicaciones ML'
    )
    ml_stock_difference = fields.Float(
        string='Diferencia Stock ML',
        compute='_compute_ml_stock_info',
        help='Diferencia entre stock Odoo y stock ML total'
    )
    ml_stock_alert = fields.Boolean(
        string='Alerta Stock ML',
        compute='_compute_ml_stock_info',
        store=True
    )

    @api.depends('ml_item_ids')
    def _compute_ml_item_count(self):
        for record in self:
            record.ml_item_count = len(record.ml_item_ids)
            record.has_ml_items = record.ml_item_count > 0

    @api.depends('ml_item_ids', 'ml_item_ids.available_quantity',
                 'qty_available', 'ml_item_ids.is_linked')
    def _compute_ml_stock_info(self):
        for record in self:
            linked_items = record.ml_item_ids.filtered(lambda i: i.is_linked)
            ml_stock = sum(linked_items.mapped('available_quantity'))
            record.ml_total_stock = ml_stock
            record.ml_stock_difference = record.qty_available - ml_stock
            record.ml_stock_alert = abs(record.ml_stock_difference) > 0 and record.has_ml_items

    # =====================================================
    # ACCIONES
    # =====================================================
    def action_view_ml_items(self):
        """Ver publicaciones de ML vinculadas"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicaciones MercadoLibre'),
            'res_model': 'mercadolibre.item',
            'view_mode': 'tree,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {'default_product_tmpl_id': self.id},
        }

    def action_sync_to_ml(self):
        """Sincroniza este producto a todas sus publicaciones en ML"""
        self.ensure_one()

        if not self.ml_item_ids:
            raise UserError(_('Este producto no tiene publicaciones en MercadoLibre vinculadas.'))

        errors = []
        success_count = 0

        for item in self.ml_item_ids:
            try:
                # Sincronizar stock si esta habilitado
                if self.ml_auto_sync_stock or item.auto_sync_stock:
                    item.action_sync_stock_to_ml()
                    success_count += 1

                # Sincronizar precio si esta habilitado
                if self.ml_auto_sync_price or item.auto_sync_price:
                    item.action_sync_price_to_ml()

            except Exception as e:
                errors.append(f'{item.ml_item_id}: {str(e)}')

        self.write({'ml_last_sync': fields.Datetime.now()})

        if errors:
            raise UserError(_('Errores durante la sincronizacion:\n') + '\n'.join(errors))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronizacion Completada'),
                'message': _('Se sincronizaron %d publicaciones.') % success_count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_sync_from_ml(self):
        """Trae datos desde ML para este producto"""
        self.ensure_one()

        if not self.ml_item_ids:
            raise UserError(_('Este producto no tiene publicaciones en MercadoLibre vinculadas.'))

        for item in self.ml_item_ids:
            item.action_sync_from_ml()

        self.write({'ml_last_sync': fields.Datetime.now()})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronizacion Completada'),
                'message': _('Se actualizaron los datos desde MercadoLibre.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_publish_to_ml(self):
        """Abre wizard para publicar este producto en ML"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Publicar en MercadoLibre'),
            'res_model': 'mercadolibre.product.publish',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_ids': [(6, 0, [self.id])],
            }
        }

    def action_link_ml_item(self):
        """Abre wizard para vincular a item ML existente"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vincular a Item ML'),
            'res_model': 'mercadolibre.product.link',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.id,
                'default_link_mode': 'product_to_item',
            }
        }

    # =====================================================
    # ACCIONES MASIVAS (SERVER ACTIONS)
    # =====================================================
    def action_sync_to_ml_batch(self):
        """Accion para sincronizar varios productos a ML"""
        errors = []
        success_count = 0

        for product in self:
            if not product.ml_item_ids:
                continue
            try:
                for item in product.ml_item_ids:
                    if product.ml_auto_sync_stock or item.auto_sync_stock:
                        item.action_sync_stock_to_ml()
                        success_count += 1
            except Exception as e:
                errors.append(f'{product.name}: {str(e)}')

        msg = _('Se sincronizaron %d publicaciones.') % success_count
        if errors:
            msg += _('\n\nErrores:\n') + '\n'.join(errors[:5])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronizacion Masiva'),
                'message': msg,
                'type': 'success' if not errors else 'warning',
                'sticky': bool(errors),
            }
        }

    def action_sync_from_ml_batch(self):
        """Accion para traer datos de ML para varios productos"""
        errors = []
        success_count = 0

        for product in self:
            if not product.ml_item_ids:
                continue
            try:
                for item in product.ml_item_ids:
                    item.action_sync_from_ml()
                    success_count += 1
            except Exception as e:
                errors.append(f'{product.name}: {str(e)}')

        msg = _('Se actualizaron %d publicaciones.') % success_count
        if errors:
            msg += _('\n\nErrores:\n') + '\n'.join(errors[:5])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronizacion Masiva'),
                'message': msg,
                'type': 'success' if not errors else 'warning',
                'sticky': bool(errors),
            }
        }
