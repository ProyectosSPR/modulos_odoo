# -*- coding: utf-8 -*-

import logging
import time
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MercadolibreSyncWizard(models.TransientModel):
    _name = 'mercadolibre.sync.wizard'
    _description = 'Sincronización Bidireccional con MercadoLibre'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta MercadoLibre',
        required=True,
        domain="[('state', '=', 'connected')]"
    )

    # Productos a sincronizar (solo los que tienen items vinculados)
    product_tmpl_ids = fields.Many2many(
        'product.template',
        string='Productos'
    )

    # Contadores
    product_count = fields.Integer(
        string='Total Productos',
        compute='_compute_counts'
    )
    linked_count = fields.Integer(
        string='Con Items ML Vinculados',
        compute='_compute_counts'
    )
    not_linked_count = fields.Integer(
        string='Sin Vincular',
        compute='_compute_counts'
    )

    # Dirección por campo
    stock_direction = fields.Selection([
        ('odoo_to_ml', 'Odoo → ML'),
        ('ml_to_odoo', 'ML → Odoo'),
        ('none', 'No sincronizar'),
    ], string='Stock', default='none', required=True)

    price_direction = fields.Selection([
        ('odoo_to_ml', 'Odoo → ML'),
        ('ml_to_odoo', 'ML → Odoo'),
        ('none', 'No sincronizar'),
    ], string='Precio', default='none', required=True)

    description_direction = fields.Selection([
        ('odoo_to_ml', 'Odoo → ML'),
        ('ml_to_odoo', 'ML → Odoo'),
        ('none', 'No sincronizar'),
    ], string='Descripción', default='none', required=True)

    brand_model_direction = fields.Selection([
        ('odoo_to_ml', 'Odoo → ML'),
        ('ml_to_odoo', 'ML → Odoo'),
        ('none', 'No sincronizar'),
    ], string='Marca/Modelo', default='none', required=True)

    # Estado y resultados
    state = fields.Selection([
        ('draft', 'Configuración'),
        ('syncing', 'Sincronizando'),
        ('done', 'Completado'),
    ], string='Estado', default='draft')

    sync_log = fields.Text(
        string='Log de Sincronización',
        readonly=True
    )
    synced_count = fields.Integer(
        string='Sincronizados',
        readonly=True
    )
    error_count = fields.Integer(
        string='Errores',
        readonly=True
    )

    @api.depends('product_tmpl_ids', 'account_id')
    def _compute_counts(self):
        for record in self:
            products = record.product_tmpl_ids
            record.product_count = len(products)

            linked = 0
            for product in products:
                if record.account_id and product.ml_item_ids.filtered(
                    lambda i: i.account_id == record.account_id
                ):
                    linked += 1

            record.linked_count = linked
            record.not_linked_count = len(products) - linked

    def _get_linked_items(self):
        """Obtiene los items vinculados de los productos seleccionados"""
        items = self.env['mercadolibre.item']
        for product in self.product_tmpl_ids:
            product_items = product.ml_item_ids.filtered(
                lambda i: i.account_id == self.account_id
            )
            items |= product_items
        return items

    def action_sync(self):
        """Ejecuta la sincronización bidireccional"""
        self.ensure_one()

        if not self.account_id:
            raise ValidationError(_('Seleccione una cuenta de MercadoLibre.'))

        if not self.account_id.has_valid_token:
            raise ValidationError(_('La cuenta no tiene un token válido.'))

        # Verificar que hay algo que sincronizar
        if all([
            self.stock_direction == 'none',
            self.price_direction == 'none',
            self.description_direction == 'none',
            self.brand_model_direction == 'none',
        ]):
            raise ValidationError(_('Seleccione al menos un campo para sincronizar.'))

        self.write({'state': 'syncing'})

        log_lines = []
        log_lines.append('=' * 60)
        log_lines.append('    SINCRONIZACIÓN BIDIRECCIONAL')
        log_lines.append('=' * 60)
        log_lines.append(f'  Cuenta: {self.account_id.name}')
        log_lines.append(f'  Fecha: {fields.Datetime.now()}')
        log_lines.append('')
        log_lines.append('  Configuración:')
        log_lines.append(f'    Stock:        {dict(self._fields["stock_direction"].selection).get(self.stock_direction)}')
        log_lines.append(f'    Precio:       {dict(self._fields["price_direction"].selection).get(self.price_direction)}')
        log_lines.append(f'    Descripción:  {dict(self._fields["description_direction"].selection).get(self.description_direction)}')
        log_lines.append(f'    Marca/Modelo: {dict(self._fields["brand_model_direction"].selection).get(self.brand_model_direction)}')
        log_lines.append('')
        log_lines.append('-' * 60)

        http = self.env['mercadolibre.http']
        synced_count = 0
        error_count = 0

        items = self._get_linked_items()
        log_lines.append(f'  Items a sincronizar: {len(items)}')
        log_lines.append('')

        for item in items:
            product = item.product_tmpl_id
            if not product:
                continue

            item_log = []
            has_changes = False

            try:
                # Primero, obtener datos actuales de ML si es necesario
                ml_data = None
                if any([
                    self.stock_direction == 'ml_to_odoo',
                    self.price_direction == 'ml_to_odoo',
                    self.description_direction == 'ml_to_odoo',
                    self.brand_model_direction == 'ml_to_odoo',
                ]):
                    response = http._request(
                        account_id=self.account_id.id,
                        endpoint=f'/items/{item.ml_item_id}',
                        method='GET'
                    )
                    ml_data = response.get('data', {})

                # STOCK
                if self.stock_direction == 'odoo_to_ml':
                    new_stock = int(product.qty_available)
                    if new_stock != item.available_quantity:
                        http._request(
                            account_id=self.account_id.id,
                            endpoint=f'/items/{item.ml_item_id}',
                            method='PUT',
                            body={'available_quantity': new_stock}
                        )
                        item.write({'available_quantity': new_stock})
                        item_log.append(f'Stock: {item.available_quantity} → {new_stock} (Odoo→ML)')
                        has_changes = True

                elif self.stock_direction == 'ml_to_odoo' and ml_data:
                    ml_stock = ml_data.get('available_quantity', 0)
                    if ml_stock != product.qty_available:
                        # Actualizar stock en Odoo (crear movimiento de inventario)
                        self._update_odoo_stock(product, ml_stock)
                        item_log.append(f'Stock: {product.qty_available} → {ml_stock} (ML→Odoo)')
                        has_changes = True

                # PRECIO
                if self.price_direction == 'odoo_to_ml':
                    new_price = product.list_price
                    if new_price != item.price:
                        http._request(
                            account_id=self.account_id.id,
                            endpoint=f'/items/{item.ml_item_id}',
                            method='PUT',
                            body={'price': new_price}
                        )
                        item.write({'price': new_price})
                        item_log.append(f'Precio: ${item.price} → ${new_price} (Odoo→ML)')
                        has_changes = True

                elif self.price_direction == 'ml_to_odoo' and ml_data:
                    ml_price = ml_data.get('price', 0)
                    if ml_price != product.list_price:
                        product.write({'list_price': ml_price})
                        item_log.append(f'Precio: ${product.list_price} → ${ml_price} (ML→Odoo)')
                        has_changes = True

                # DESCRIPCIÓN
                if self.description_direction == 'odoo_to_ml':
                    if product.description_sale:
                        http._request(
                            account_id=self.account_id.id,
                            endpoint=f'/items/{item.ml_item_id}/description',
                            method='PUT',
                            body={'plain_text': product.description_sale}
                        )
                        item.write({'description': product.description_sale})
                        item_log.append('Descripción: Odoo→ML')
                        has_changes = True

                elif self.description_direction == 'ml_to_odoo':
                    # Obtener descripción de ML
                    try:
                        desc_response = http._request(
                            account_id=self.account_id.id,
                            endpoint=f'/items/{item.ml_item_id}/description',
                            method='GET'
                        )
                        ml_desc = desc_response.get('data', {}).get('plain_text', '')
                        if ml_desc and ml_desc != product.description_sale:
                            product.write({'description_sale': ml_desc})
                            item_log.append('Descripción: ML→Odoo')
                            has_changes = True
                    except Exception:
                        pass

                # MARCA/MODELO
                if self.brand_model_direction == 'odoo_to_ml':
                    brand_name = product.ml_brand or 'Genérico'
                    model_name = product.ml_model or product.default_code or product.name[:30]

                    attributes = [
                        {'id': 'BRAND', 'value_name': brand_name},
                        {'id': 'MODEL', 'value_name': model_name},
                    ]
                    http._request(
                        account_id=self.account_id.id,
                        endpoint=f'/items/{item.ml_item_id}',
                        method='PUT',
                        body={'attributes': attributes}
                    )
                    item.write({'brand': brand_name, 'model': model_name})
                    item_log.append(f'Marca/Modelo: {brand_name}/{model_name} (Odoo→ML)')
                    has_changes = True

                elif self.brand_model_direction == 'ml_to_odoo' and ml_data:
                    # Extraer marca y modelo de atributos
                    ml_brand = ''
                    ml_model = ''
                    for attr in ml_data.get('attributes', []):
                        if attr.get('id') == 'BRAND':
                            ml_brand = attr.get('value_name', '')
                        elif attr.get('id') == 'MODEL':
                            ml_model = attr.get('value_name', '')

                    if ml_brand or ml_model:
                        vals = {}
                        if ml_brand and ml_brand != product.ml_brand:
                            vals['ml_brand'] = ml_brand
                        if ml_model and ml_model != product.ml_model:
                            vals['ml_model'] = ml_model
                        if vals:
                            product.write(vals)
                            item_log.append(f'Marca/Modelo: {ml_brand}/{ml_model} (ML→Odoo)')
                            has_changes = True

                # Actualizar última sincronización
                if has_changes:
                    item.write({
                        'last_sync': fields.Datetime.now(),
                        'sync_status': 'synced',
                        'sync_error': False,
                    })
                    synced_count += 1
                    log_lines.append(f'  [OK] {product.name[:35]} ({item.ml_item_id})')
                    for log in item_log:
                        log_lines.append(f'       → {log}')

                # Rate limit
                time.sleep(0.2)

            except Exception as e:
                error_count += 1
                error_msg = str(e)[:80]
                item.write({
                    'sync_status': 'error',
                    'sync_error': error_msg,
                })
                log_lines.append(f'  [ERROR] {product.name[:35]}')
                log_lines.append(f'          {error_msg}')
                _logger.error('Error sincronizando %s: %s', item.ml_item_id, str(e))

        # Resumen
        log_lines.append('')
        log_lines.append('=' * 60)
        log_lines.append('  RESUMEN')
        log_lines.append('=' * 60)
        log_lines.append(f'  Sincronizados: {synced_count}')
        log_lines.append(f'  Errores:       {error_count}')
        log_lines.append('=' * 60)

        self.write({
            'state': 'done',
            'sync_log': '\n'.join(log_lines),
            'synced_count': synced_count,
            'error_count': error_count,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronización Bidireccional'),
            'res_model': 'mercadolibre.sync.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _update_odoo_stock(self, product, new_qty):
        """Actualiza el stock en Odoo creando un ajuste de inventario"""
        # Buscar la ubicación de stock principal
        location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        if not location:
            location = self.env['stock.location'].search([
                ('usage', '=', 'internal')
            ], limit=1)

        if not location:
            _logger.warning('No se encontró ubicación de stock para actualizar')
            return

        # Buscar o crear quant
        product_variant = product.product_variant_id
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product_variant.id),
            ('location_id', '=', location.id),
        ], limit=1)

        if quant:
            quant.sudo().write({'quantity': new_qty})
        else:
            self.env['stock.quant'].sudo().create({
                'product_id': product_variant.id,
                'location_id': location.id,
                'quantity': new_qty,
            })

    def action_new_sync(self):
        """Nueva sincronización"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronización Bidireccional'),
            'res_model': 'mercadolibre.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_product_tmpl_ids': self.product_tmpl_ids.ids},
        }
