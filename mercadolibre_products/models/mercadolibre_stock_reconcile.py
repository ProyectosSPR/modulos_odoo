# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MercadolibreStockReconcile(models.Model):
    _name = 'mercadolibre.stock.reconcile'
    _description = 'Conciliacion de Inventario ML vs Odoo'
    _order = 'difference desc, id'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=True
    )

    # =====================================================
    # RELACIONES
    # =====================================================
    sync_config_id = fields.Many2one(
        'mercadolibre.product.sync.config',
        string='Configuracion Sync',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        related='sync_config_id.account_id',
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='sync_config_id.company_id',
        store=True,
        readonly=True
    )
    item_id = fields.Many2one(
        'mercadolibre.item',
        string='Item ML',
        required=True,
        ondelete='cascade',
        index=True
    )
    variation_id = fields.Many2one(
        'mercadolibre.item.variation',
        string='Variacion',
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto Odoo',
        required=True,
        ondelete='cascade',
        index=True
    )

    # =====================================================
    # DATOS DE STOCK
    # =====================================================
    ml_stock = fields.Float(
        string='Stock MercadoLibre',
        digits='Product Unit of Measure',
        help='Stock disponible en MercadoLibre'
    )
    odoo_stock = fields.Float(
        string='Stock Odoo',
        digits='Product Unit of Measure',
        help='Stock disponible en Odoo'
    )
    difference = fields.Float(
        string='Diferencia',
        digits='Product Unit of Measure',
        help='ML - Odoo. Positivo = ML tiene mas. Negativo = Odoo tiene mas.'
    )
    difference_abs = fields.Float(
        string='Diferencia Absoluta',
        compute='_compute_difference_abs',
        store=True
    )
    difference_type = fields.Selection([
        ('ml_higher', 'ML tiene mas stock'),
        ('odoo_higher', 'Odoo tiene mas stock'),
        ('equal', 'Sin diferencia'),
    ], string='Tipo Diferencia', compute='_compute_difference_type', store=True)

    # =====================================================
    # INFORMACION DEL PRODUCTO
    # =====================================================
    product_default_code = fields.Char(
        string='SKU Odoo',
        related='product_id.default_code',
        store=True,
        readonly=True
    )
    product_name = fields.Char(
        string='Producto',
        related='product_id.name',
        store=True,
        readonly=True
    )
    ml_item_id = fields.Char(
        string='ID Item ML',
        related='item_id.ml_item_id',
        store=True,
        readonly=True
    )
    ml_title = fields.Char(
        string='Titulo ML',
        related='item_id.title',
        store=True,
        readonly=True
    )
    ml_seller_sku = fields.Char(
        string='SKU ML',
        related='item_id.seller_sku',
        store=True,
        readonly=True
    )
    variation_sku = fields.Char(
        string='SKU Variacion',
        related='variation_id.seller_sku',
        store=True,
        readonly=True
    )

    # =====================================================
    # ESTADO Y ACCIONES
    # =====================================================
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('reviewed', 'Revisado'),
        ('adjusted_ml', 'Ajustado en ML'),
        ('adjusted_odoo', 'Ajustado en Odoo'),
        ('ignored', 'Ignorado'),
    ], string='Estado', default='pending', tracking=True)

    notes = fields.Text(
        string='Notas',
        help='Notas sobre esta diferencia de inventario'
    )
    reviewed_by = fields.Many2one(
        'res.users',
        string='Revisado por'
    )
    reviewed_date = fields.Datetime(
        string='Fecha Revision'
    )

    # Ubicacion de referencia
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicacion',
        related='sync_config_id.stock_location_id',
        store=True,
        readonly=True
    )

    @api.depends('product_id', 'item_id', 'variation_id')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.product_default_code:
                parts.append(f'[{record.product_default_code}]')
            if record.product_name:
                parts.append(record.product_name[:30])
            if record.variation_sku:
                parts.append(f'(Var: {record.variation_sku})')
            record.display_name = ' '.join(parts) if parts else f'Reconcile #{record.id}'

    @api.depends('difference')
    def _compute_difference_abs(self):
        for record in self:
            record.difference_abs = abs(record.difference)

    @api.depends('difference')
    def _compute_difference_type(self):
        for record in self:
            if record.difference > 0:
                record.difference_type = 'ml_higher'
            elif record.difference < 0:
                record.difference_type = 'odoo_higher'
            else:
                record.difference_type = 'equal'

    # =====================================================
    # ACCIONES
    # =====================================================
    def action_mark_reviewed(self):
        """Marca como revisado"""
        for record in self:
            record.write({
                'state': 'reviewed',
                'reviewed_by': self.env.uid,
                'reviewed_date': fields.Datetime.now(),
            })

    def action_mark_ignored(self):
        """Marca como ignorado"""
        for record in self:
            record.write({
                'state': 'ignored',
                'reviewed_by': self.env.uid,
                'reviewed_date': fields.Datetime.now(),
            })

    def action_adjust_ml_to_odoo(self):
        """
        Ajusta el stock de Odoo para que coincida con ML.
        Crea un ajuste de inventario.
        """
        self.ensure_one()

        if not self.sync_config_id.stock_location_id:
            raise UserError(_('Debe configurar una ubicacion de stock en la configuracion de sincronizacion.'))

        location = self.sync_config_id.stock_location_id
        product = self.product_id

        try:
            # Buscar o crear quant
            quant = self.env['stock.quant'].sudo().search([
                ('product_id', '=', product.id),
                ('location_id', '=', location.id),
            ], limit=1)

            if quant:
                quant.sudo().with_context(inventory_mode=True).write({
                    'inventory_quantity': self.ml_stock,
                })
                quant.sudo().action_apply_inventory()
            else:
                self.env['stock.quant'].sudo().with_context(inventory_mode=True).create({
                    'product_id': product.id,
                    'location_id': location.id,
                    'inventory_quantity': self.ml_stock,
                })

            self.write({
                'state': 'adjusted_odoo',
                'odoo_stock': self.ml_stock,
                'difference': 0,
                'reviewed_by': self.env.uid,
                'reviewed_date': fields.Datetime.now(),
                'notes': (self.notes or '') + f'\nAjuste Odoo aplicado: {self.odoo_stock} -> {self.ml_stock}'
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Ajuste Aplicado'),
                    'message': _('Stock de Odoo ajustado a %d unidades.') % self.ml_stock,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            raise UserError(_('Error creando ajuste de inventario: %s') % str(e))

    def action_adjust_odoo_to_ml(self):
        """
        Ajusta el stock de ML para que coincida con Odoo.
        Envia actualizacion a la API de ML.
        """
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise UserError(_('La cuenta no tiene un token valido.'))

        http = self.env['mercadolibre.http']
        new_stock = int(self.odoo_stock)

        try:
            if self.variation_id:
                # Actualizar variacion
                http._request(
                    account_id=self.account_id.id,
                    endpoint=f'/items/{self.item_id.ml_item_id}/variations/{self.variation_id.ml_variation_id}',
                    method='PUT',
                    body={'available_quantity': new_stock}
                )
                self.variation_id.write({'available_quantity': new_stock})
            else:
                # Actualizar item
                http._request(
                    account_id=self.account_id.id,
                    endpoint=f'/items/{self.item_id.ml_item_id}',
                    method='PUT',
                    body={'available_quantity': new_stock}
                )
                self.item_id.write({'available_quantity': new_stock})

            self.write({
                'state': 'adjusted_ml',
                'ml_stock': new_stock,
                'difference': 0,
                'reviewed_by': self.env.uid,
                'reviewed_date': fields.Datetime.now(),
                'notes': (self.notes or '') + f'\nAjuste ML aplicado: {self.ml_stock} -> {new_stock}'
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Stock ML Actualizado'),
                    'message': _('Stock de MercadoLibre ajustado a %d unidades.') % new_stock,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            raise UserError(_('Error actualizando stock en ML: %s') % str(e))

    def action_refresh_stocks(self):
        """Actualiza los valores de stock desde ambas fuentes"""
        for record in self:
            # Actualizar stock Odoo
            if record.sync_config_id.stock_location_id:
                odoo_stock = record.product_id.with_context(
                    location=record.sync_config_id.stock_location_id.id
                ).qty_available
            else:
                odoo_stock = record.product_id.qty_available

            # Actualizar stock ML (desde el registro local)
            if record.variation_id:
                ml_stock = record.variation_id.available_quantity
            else:
                ml_stock = record.item_id.available_quantity

            record.write({
                'odoo_stock': odoo_stock,
                'ml_stock': ml_stock,
                'difference': ml_stock - odoo_stock,
            })

    def action_view_item(self):
        """Ver item de ML"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Item MercadoLibre'),
            'res_model': 'mercadolibre.item',
            'res_id': self.item_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_product(self):
        """Ver producto Odoo"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Producto'),
            'res_model': 'product.product',
            'res_id': self.product_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_stock_quant(self):
        """Ver quants del producto"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock por Ubicacion'),
            'res_model': 'stock.quant',
            'view_mode': 'tree,form',
            'domain': [('product_id', '=', self.product_id.id)],
            'context': {'search_default_internal_loc': 1},
        }

    # =====================================================
    # ACCIONES MASIVAS
    # =====================================================
    def action_bulk_adjust_ml_to_odoo(self):
        """Ajusta todos los seleccionados: ML -> Odoo"""
        errors = []
        success_count = 0

        for record in self:
            if record.state in ('adjusted_odoo', 'adjusted_ml', 'ignored'):
                continue
            try:
                record.action_adjust_ml_to_odoo()
                success_count += 1
            except Exception as e:
                errors.append(f'{record.product_name}: {str(e)}')

        msg = _('Ajustados %d registros en Odoo.') % success_count
        if errors:
            msg += _('\n\nErrores:\n') + '\n'.join(errors[:10])
            if len(errors) > 10:
                msg += _('\n... y %d errores mas') % (len(errors) - 10)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ajuste Masivo'),
                'message': msg,
                'type': 'success' if not errors else 'warning',
                'sticky': bool(errors),
            }
        }

    def action_bulk_adjust_odoo_to_ml(self):
        """Ajusta todos los seleccionados: Odoo -> ML"""
        errors = []
        success_count = 0

        for record in self:
            if record.state in ('adjusted_odoo', 'adjusted_ml', 'ignored'):
                continue
            try:
                record.action_adjust_odoo_to_ml()
                success_count += 1
            except Exception as e:
                errors.append(f'{record.product_name}: {str(e)}')

        msg = _('Actualizados %d registros en MercadoLibre.') % success_count
        if errors:
            msg += _('\n\nErrores:\n') + '\n'.join(errors[:10])
            if len(errors) > 10:
                msg += _('\n... y %d errores mas') % (len(errors) - 10)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ajuste Masivo'),
                'message': msg,
                'type': 'success' if not errors else 'warning',
                'sticky': bool(errors),
            }
        }

    def action_bulk_mark_reviewed(self):
        """Marca todos como revisados"""
        self.write({
            'state': 'reviewed',
            'reviewed_by': self.env.uid,
            'reviewed_date': fields.Datetime.now(),
        })

    def action_bulk_mark_ignored(self):
        """Marca todos como ignorados"""
        self.write({
            'state': 'ignored',
            'reviewed_by': self.env.uid,
            'reviewed_date': fields.Datetime.now(),
        })
