# -*- coding: utf-8 -*-

import json
import time
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MercadolibreProductSync(models.TransientModel):
    _name = 'mercadolibre.product.sync'
    _description = 'Asistente de Sincronizacion de Productos'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]"
    )

    # Modo de sincronizacion
    sync_mode = fields.Selection([
        ('all', 'Todos los Items'),
        ('specific', 'Item Especifico'),
        ('by_status', 'Por Estado'),
    ], string='Modo', default='all', required=True)

    specific_item_id = fields.Char(
        string='ID Item ML',
        help='ID del item especifico a sincronizar (ej: MLM123456789)'
    )

    status_filter = fields.Selection([
        ('active', 'Activos'),
        ('paused', 'Pausados'),
        ('closed', 'Cerrados'),
    ], string='Estado', default='active')

    # Opciones
    limit = fields.Integer(
        string='Limite',
        default=50,
        help='Numero maximo de items a sincronizar'
    )
    auto_link = fields.Boolean(
        string='Auto-vincular por SKU',
        default=True,
        help='Intentar vincular automaticamente items con productos por SKU'
    )
    link_method = fields.Selection([
        ('seller_sku', 'SELLER_SKU'),
        ('seller_custom_field', 'seller_custom_field'),
        ('barcode', 'Codigo de Barras'),
    ], string='Metodo Vinculacion', default='seller_sku')

    sync_variations = fields.Boolean(
        string='Sincronizar Variaciones',
        default=True
    )

    # Resultados
    state = fields.Selection([
        ('draft', 'Configuracion'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], string='Estado', default='draft')

    sync_count = fields.Integer(
        string='Items Sincronizados',
        readonly=True
    )
    created_count = fields.Integer(
        string='Nuevos',
        readonly=True
    )
    updated_count = fields.Integer(
        string='Actualizados',
        readonly=True
    )
    linked_count = fields.Integer(
        string='Vinculados',
        readonly=True
    )
    error_count = fields.Integer(
        string='Errores',
        readonly=True
    )
    sync_log = fields.Text(
        string='Log de Sincronizacion',
        readonly=True
    )

    def action_sync(self):
        """Ejecuta la sincronizacion de items"""
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise ValidationError(_('La cuenta no tiene un token valido.'))

        if self.sync_mode == 'specific':
            return self._sync_specific_item()

        _logger.info('=' * 60)
        _logger.info('SYNC PRODUCTOS WIZARD: Iniciando')
        _logger.info('=' * 60)

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append('    SINCRONIZACION DE PRODUCTOS MERCADOLIBRE')
        log_lines.append('=' * 50)
        log_lines.append('')
        log_lines.append(f'  Cuenta:    {self.account_id.name}')
        log_lines.append(f'  Modo:      {self.sync_mode}')
        if self.sync_mode == 'by_status':
            log_lines.append(f'  Estado:    {self.status_filter}')
        log_lines.append(f'  Limite:    {self.limit}')
        log_lines.append('')

        http = self.env['mercadolibre.http']
        ItemModel = self.env['mercadolibre.item']

        sync_count = 0
        created_count = 0
        updated_count = 0
        linked_count = 0
        error_count = 0

        try:
            # Construir parametros
            params = {'limit': self.limit}
            if self.sync_mode == 'by_status':
                params['status'] = self.status_filter

            # Obtener lista de items
            response = http._request(
                account_id=self.account_id.id,
                endpoint=f'/users/{self.account_id.ml_user_id}/items/search',
                method='GET',
                params=params
            )

            item_ids = response.get('data', {}).get('results', [])
            total = response.get('data', {}).get('paging', {}).get('total', 0)

            log_lines.append('-' * 50)
            log_lines.append('  RESULTADOS DE BUSQUEDA')
            log_lines.append('-' * 50)
            log_lines.append(f'  Total en ML: {total}')
            log_lines.append(f'  A procesar:  {len(item_ids)}')
            log_lines.append('')
            log_lines.append('-' * 50)
            log_lines.append('  DETALLE DE ITEMS')
            log_lines.append('-' * 50)

            for ml_item_id in item_ids:
                try:
                    # Obtener detalle del item
                    item_response = http._request(
                        account_id=self.account_id.id,
                        endpoint=f'/items/{ml_item_id}',
                        method='GET'
                    )
                    item_data = item_response.get('data', {})

                    # Crear o actualizar
                    item, is_new = ItemModel.create_from_ml_data(item_data, self.account_id)
                    sync_count += 1

                    if is_new:
                        created_count += 1
                        action = 'NUEVO'
                    else:
                        updated_count += 1
                        action = 'ACTUALIZADO'

                    # Auto-vincular
                    was_linked = item.is_linked
                    if self.auto_link and not item.is_linked:
                        self._auto_link_item(item)
                        if item.is_linked:
                            linked_count += 1
                            action += ' + VINCULADO'

                    title_short = item.title[:35] if item.title else ''
                    log_lines.append(f'  [{action:^20}] {ml_item_id}: {title_short}...')

                except Exception as e:
                    error_count += 1
                    log_lines.append(f'  [{"ERROR":^20}] {ml_item_id}: {str(e)[:50]}')
                    _logger.error('Error sincronizando item %s: %s', ml_item_id, str(e))

                # Rate limit
                time.sleep(0.1)

        except Exception as e:
            log_lines.append(f'ERROR: {str(e)}')
            error_count += 1

        # Resumen
        log_lines.append('')
        log_lines.append('=' * 50)
        log_lines.append('  RESUMEN')
        log_lines.append('=' * 50)
        log_lines.append(f'  Total sincronizados: {sync_count}')
        log_lines.append(f'    - Nuevos:          {created_count}')
        log_lines.append(f'    - Actualizados:    {updated_count}')
        log_lines.append(f'    - Vinculados:      {linked_count}')
        log_lines.append(f'  Errores:             {error_count}')
        log_lines.append('=' * 50)

        self.write({
            'state': 'done' if error_count == 0 else 'error',
            'sync_count': sync_count,
            'created_count': created_count,
            'updated_count': updated_count,
            'linked_count': linked_count,
            'error_count': error_count,
            'sync_log': '\n'.join(log_lines),
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizacion de Productos'),
            'res_model': 'mercadolibre.product.sync',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _sync_specific_item(self):
        """Sincroniza un item especifico"""
        self.ensure_one()

        if not self.specific_item_id:
            raise ValidationError(_('Debe ingresar el ID del item.'))

        ml_item_id = self.specific_item_id.strip().upper()

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append('    SINCRONIZACION DE ITEM ESPECIFICO')
        log_lines.append('=' * 50)
        log_lines.append('')
        log_lines.append(f'  Cuenta:  {self.account_id.name}')
        log_lines.append(f'  Item ID: {ml_item_id}')
        log_lines.append('')

        http = self.env['mercadolibre.http']
        ItemModel = self.env['mercadolibre.item']

        try:
            # Obtener detalle del item
            response = http._request(
                account_id=self.account_id.id,
                endpoint=f'/items/{ml_item_id}',
                method='GET'
            )
            item_data = response.get('data', {})

            if not item_data:
                raise UserError(_('Item no encontrado en MercadoLibre.'))

            log_lines.append('-' * 50)
            log_lines.append('  ITEM ENCONTRADO')
            log_lines.append('-' * 50)
            log_lines.append(f'  Titulo:   {item_data.get("title", "")}')
            log_lines.append(f'  Estado:   {item_data.get("status", "")}')
            log_lines.append(f'  Precio:   ${item_data.get("price", 0):,.2f}')
            log_lines.append(f'  Stock:    {item_data.get("available_quantity", 0)}')
            log_lines.append(f'  Vendidos: {item_data.get("sold_quantity", 0)}')
            log_lines.append('')

            # Crear o actualizar
            item, is_new = ItemModel.create_from_ml_data(item_data, self.account_id)

            action = 'NUEVO' if is_new else 'ACTUALIZADO'
            log_lines.append(f'  [{action}] Item sincronizado en Odoo')

            # Auto-vincular
            if self.auto_link and not item.is_linked:
                self._auto_link_item(item)
                if item.is_linked:
                    log_lines.append(f'  [VINCULADO] Producto: {item.product_id.name or item.product_tmpl_id.name}')

            # Variaciones
            if item.has_variations:
                log_lines.append(f'  Variaciones: {item.variation_count}')
                for var in item.variation_ids:
                    linked_status = 'Vinculado' if var.is_linked else 'Sin vincular'
                    log_lines.append(f'    - {var.attribute_display}: Stock {var.available_quantity} ({linked_status})')

            log_lines.append('')
            log_lines.append('=' * 50)
            log_lines.append('  SINCRONIZACION EXITOSA')
            log_lines.append('=' * 50)

            self.write({
                'state': 'done',
                'sync_count': 1,
                'created_count': 1 if is_new else 0,
                'updated_count': 0 if is_new else 1,
                'linked_count': 1 if item.is_linked else 0,
                'error_count': 0,
                'sync_log': '\n'.join(log_lines),
            })

        except Exception as e:
            log_lines.append(f'ERROR: {str(e)}')
            self.write({
                'state': 'error',
                'error_count': 1,
                'sync_log': '\n'.join(log_lines),
            })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizacion de Productos'),
            'res_model': 'mercadolibre.product.sync',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _auto_link_item(self, item):
        """Intenta vincular automaticamente un item"""
        ProductProduct = self.env['product.product']
        product = False

        if self.link_method == 'seller_sku':
            if item.seller_sku:
                product = ProductProduct.search([
                    ('default_code', '=', item.seller_sku)
                ], limit=1)
            # Buscar en variaciones
            if not product and item.has_variations:
                for var in item.variation_ids:
                    if var.seller_sku:
                        prod = ProductProduct.search([
                            ('default_code', '=', var.seller_sku)
                        ], limit=1)
                        if prod:
                            var.write({'product_id': prod.id})

        elif self.link_method == 'seller_custom_field':
            if item.seller_custom_field:
                product = ProductProduct.search([
                    ('default_code', '=', item.seller_custom_field)
                ], limit=1)

        elif self.link_method == 'barcode':
            if item.seller_sku:
                product = ProductProduct.search([
                    ('barcode', '=', item.seller_sku)
                ], limit=1)

        if product:
            item.write({
                'product_id': product.id,
                'product_tmpl_id': product.product_tmpl_id.id,
            })

    def action_view_items(self):
        """Ver items sincronizados"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Items Sincronizados'),
            'res_model': 'mercadolibre.item',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.account_id.id)],
            'context': {'default_account_id': self.account_id.id},
        }

    def action_new_sync(self):
        """Nueva sincronizacion"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizar Productos'),
            'res_model': 'mercadolibre.product.sync',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_account_id': self.account_id.id},
        }
