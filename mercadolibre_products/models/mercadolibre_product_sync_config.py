# -*- coding: utf-8 -*-

import json
import time
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MercadolibreProductSyncConfig(models.Model):
    _name = 'mercadolibre.product.sync.config'
    _description = 'Configuracion Sincronizacion de Productos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo para identificar esta configuracion'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]",
        help='Cuenta de MercadoLibre a sincronizar'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # =====================================================
    # DIRECCION DE SINCRONIZACION
    # =====================================================
    sync_direction = fields.Selection([
        ('ml_to_odoo', 'MercadoLibre -> Odoo'),
        ('odoo_to_ml', 'Odoo -> MercadoLibre'),
        ('bidirectional', 'Bidireccional'),
    ], string='Direccion Sync', default='ml_to_odoo', required=True,
       help='Direccion principal de la sincronizacion')

    # =====================================================
    # METODO DE VINCULACION
    # =====================================================
    link_method = fields.Selection([
        ('seller_sku', 'Por SELLER_SKU (Atributo ML)'),
        ('seller_custom_field', 'Por seller_custom_field'),
        ('barcode', 'Por Codigo de Barras'),
        ('manual', 'Solo Manual'),
    ], string='Metodo Vinculacion', default='seller_sku', required=True,
       help='Como vincular items ML con productos Odoo')

    # =====================================================
    # CAMPOS A SINCRONIZAR: ML -> ODOO
    # =====================================================
    sync_title_to_name = fields.Boolean(
        string='Titulo -> Nombre',
        default=False,
        help='Actualizar nombre del producto con titulo de ML'
    )
    sync_price_ml_to_odoo = fields.Boolean(
        string='Precio ML -> Odoo',
        default=False,
        help='Actualizar precio de venta con precio de ML'
    )
    sync_stock_ml_to_odoo = fields.Boolean(
        string='Stock ML -> Odoo',
        default=False,
        help='Actualizar stock de Odoo con stock de ML (genera ajuste de inventario)'
    )
    sync_description = fields.Boolean(
        string='Sincronizar Descripcion',
        default=False,
        help='Sincronizar descripcion de ML a Odoo'
    )
    sync_images = fields.Boolean(
        string='Sincronizar Imagenes',
        default=False,
        help='Descargar imagenes de ML a Odoo'
    )
    create_new_products = fields.Boolean(
        string='Crear Productos Nuevos',
        default=False,
        help='Crear productos en Odoo si no existe vinculo'
    )

    # =====================================================
    # CAMPOS A SINCRONIZAR: ODOO -> ML
    # =====================================================
    sync_price_odoo_to_ml = fields.Boolean(
        string='Precio Odoo -> ML',
        default=False,
        help='Enviar precio de Odoo a MercadoLibre'
    )
    sync_stock_odoo_to_ml = fields.Boolean(
        string='Stock Odoo -> ML',
        default=True,
        help='Enviar stock de Odoo a MercadoLibre'
    )
    sync_name_to_title = fields.Boolean(
        string='Nombre -> Titulo ML',
        default=False,
        help='Actualizar titulo de ML con nombre del producto'
    )

    # =====================================================
    # FILTROS
    # =====================================================
    item_status_filter = fields.Selection([
        ('all', 'Todos los Estados'),
        ('active', 'Solo Activos'),
        ('paused', 'Solo Pausados'),
    ], string='Filtrar por Estado ML', default='active')

    sync_only_linked = fields.Boolean(
        string='Solo Vinculados',
        default=True,
        help='Solo sincronizar items que ya estan vinculados a productos'
    )
    limit = fields.Integer(
        string='Limite',
        default=100,
        help='Numero maximo de items a sincronizar por ejecucion'
    )

    # =====================================================
    # VALORES POR DEFECTO (Creacion de Productos)
    # =====================================================
    default_category_id = fields.Many2one(
        'product.category',
        string='Categoria por Defecto',
        help='Categoria para nuevos productos creados desde ML'
    )
    default_product_type = fields.Selection([
        ('consu', 'Consumible'),
        ('product', 'Almacenable'),
    ], string='Tipo Producto', default='product')
    default_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM por Defecto',
        help='Unidad de medida para nuevos productos'
    )

    # =====================================================
    # STOCK: CONFIGURACION ESPECIFICA
    # =====================================================
    stock_location_id = fields.Many2one(
        'stock.location',
        string='Ubicacion Stock',
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
        help='Ubicacion para calcular stock disponible y crear ajustes'
    )
    stock_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacen',
        domain="[('company_id', '=', company_id)]",
        help='Almacen para sincronizacion de stock'
    )
    create_stock_adjustment = fields.Boolean(
        string='Crear Ajustes de Inventario',
        default=False,
        help='Crear ajustes de inventario automaticamente cuando hay diferencias'
    )
    stock_adjustment_reason = fields.Char(
        string='Motivo Ajuste',
        default='Sincronizacion MercadoLibre',
        help='Motivo a registrar en los ajustes de inventario'
    )

    # =====================================================
    # PROGRAMACION
    # =====================================================
    interval_number = fields.Integer(
        string='Ejecutar cada',
        default=30,
        required=True
    )
    interval_type = fields.Selection([
        ('minutes', 'Minutos'),
        ('hours', 'Horas'),
        ('days', 'Dias'),
    ], string='Tipo Intervalo', default='minutes', required=True)

    next_run = fields.Datetime(
        string='Proxima Ejecucion'
    )
    last_run = fields.Datetime(
        string='Ultima Ejecucion',
        readonly=True
    )

    # =====================================================
    # ESTADO
    # =====================================================
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('paused', 'Pausado'),
    ], string='Estado', default='draft', readonly=True, tracking=True)

    cron_id = fields.Many2one(
        'ir.cron',
        string='Tarea Programada',
        readonly=True,
        ondelete='set null'
    )

    # =====================================================
    # ESTADISTICAS
    # =====================================================
    last_sync_count = fields.Integer(
        string='Ultimos Sincronizados',
        readonly=True
    )
    last_sync_created = fields.Integer(
        string='Ultimos Nuevos',
        readonly=True
    )
    last_sync_updated = fields.Integer(
        string='Ultimos Actualizados',
        readonly=True
    )
    last_sync_errors = fields.Integer(
        string='Ultimos Errores',
        readonly=True
    )
    last_sync_log = fields.Text(
        string='Log Ultima Ejecucion',
        readonly=True
    )
    total_syncs = fields.Integer(
        string='Total Ejecuciones',
        readonly=True,
        default=0
    )
    total_items_synced = fields.Integer(
        string='Total Items Sincronizados',
        readonly=True,
        default=0
    )

    # =====================================================
    # METODOS DE CICLO DE VIDA
    # =====================================================
    def write(self, vals):
        result = super().write(vals)
        if 'active' in vals:
            for record in self:
                if record.cron_id:
                    record.cron_id.active = vals['active'] and record.state == 'active'
        return result

    def unlink(self):
        for record in self:
            if record.cron_id:
                record.cron_id.unlink()
        return super().unlink()

    # =====================================================
    # ACCIONES DE ESTADO
    # =====================================================
    def action_activate(self):
        """Activa la sincronizacion automatica"""
        for record in self:
            if not record.account_id.has_valid_token:
                raise ValidationError(
                    _('La cuenta %s no tiene un token valido.') % record.account_id.name
                )
            record._create_or_update_cron()
            if not record.next_run:
                record.next_run = fields.Datetime.now()
            record.state = 'active'

    def action_pause(self):
        """Pausa la sincronizacion"""
        for record in self:
            if record.cron_id:
                record.cron_id.active = False
            record.state = 'paused'

    def action_resume(self):
        """Reanuda la sincronizacion"""
        for record in self:
            if not record.account_id.has_valid_token:
                raise ValidationError(
                    _('La cuenta %s no tiene un token valido.') % record.account_id.name
                )
            if record.cron_id:
                record.cron_id.active = True
            else:
                record._create_or_update_cron()
            record.state = 'active'

    def action_run_now(self):
        """Ejecuta la sincronizacion manualmente"""
        self.ensure_one()
        return self._execute_sync()

    def _create_or_update_cron(self):
        """Crea o actualiza el cron job"""
        self.ensure_one()

        cron_vals = {
            'name': f'Sync Productos ML: {self.name}',
            'model_id': self.env['ir.model']._get('mercadolibre.product.sync.config').id,
            'state': 'code',
            'code': f'model.browse({self.id})._execute_sync()',
            'interval_number': self.interval_number,
            'interval_type': self.interval_type,
            'numbercall': -1,
            'active': True,
            'doall': False,
        }

        if self.next_run:
            cron_vals['nextcall'] = self.next_run
        else:
            cron_vals['nextcall'] = fields.Datetime.now()

        if self.cron_id:
            self.cron_id.write(cron_vals)
        else:
            cron = self.env['ir.cron'].sudo().create(cron_vals)
            self.cron_id = cron

    # =====================================================
    # EJECUCION DE SINCRONIZACION
    # =====================================================
    def _execute_sync(self):
        """Ejecuta la sincronizacion de productos"""
        self.ensure_one()

        _logger.info('=' * 60)
        _logger.info('SYNC PRODUCTOS ML: Iniciando "%s"', self.name)
        _logger.info('=' * 60)

        if not self.account_id.has_valid_token:
            _logger.error('Cuenta %s sin token valido', self.account_id.name)
            self.write({
                'last_run': fields.Datetime.now(),
                'last_sync_log': 'ERROR: Cuenta sin token valido',
                'last_sync_errors': 1,
            })
            return False

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append(f'  SYNC PRODUCTOS ML: {self.name}')
        log_lines.append('=' * 50)
        log_lines.append(f'  Fecha: {fields.Datetime.now()}')
        log_lines.append(f'  Cuenta: {self.account_id.name}')
        log_lines.append(f'  Direccion: {self.sync_direction}')
        log_lines.append(f'  Metodo vinculacion: {self.link_method}')
        log_lines.append('')

        sync_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0

        try:
            if self.sync_direction in ('ml_to_odoo', 'bidirectional'):
                result = self._sync_from_ml(log_lines)
                sync_count += result.get('sync_count', 0)
                created_count += result.get('created_count', 0)
                updated_count += result.get('updated_count', 0)
                error_count += result.get('error_count', 0)

            if self.sync_direction in ('odoo_to_ml', 'bidirectional'):
                result = self._sync_to_ml(log_lines)
                sync_count += result.get('sync_count', 0)
                updated_count += result.get('updated_count', 0)
                error_count += result.get('error_count', 0)

        except Exception as e:
            _logger.error('Error en sync: %s', str(e))
            log_lines.append(f'ERROR GENERAL: {str(e)}')
            error_count += 1

        # Resumen
        log_lines.append('')
        log_lines.append('-' * 50)
        log_lines.append('  RESUMEN')
        log_lines.append('-' * 50)
        log_lines.append(f'  Sincronizados: {sync_count}')
        log_lines.append(f'    Nuevos:      {created_count}')
        log_lines.append(f'    Actualizados:{updated_count}')
        log_lines.append(f'  Errores:       {error_count}')
        log_lines.append('=' * 50)

        # Calcular proxima ejecucion
        next_run = fields.Datetime.now()
        if self.interval_type == 'minutes':
            next_run += timedelta(minutes=self.interval_number)
        elif self.interval_type == 'hours':
            next_run += timedelta(hours=self.interval_number)
        elif self.interval_type == 'days':
            next_run += timedelta(days=self.interval_number)

        self.write({
            'last_run': fields.Datetime.now(),
            'last_sync_count': sync_count,
            'last_sync_created': created_count,
            'last_sync_updated': updated_count,
            'last_sync_errors': error_count,
            'last_sync_log': '\n'.join(log_lines),
            'next_run': next_run,
            'total_syncs': self.total_syncs + 1,
            'total_items_synced': self.total_items_synced + sync_count,
        })

        _logger.info('SYNC PRODUCTOS "%s" completada: %d sincronizados', self.name, sync_count)
        return True

    def _sync_from_ml(self, log_lines):
        """Sincroniza items desde MercadoLibre a Odoo"""
        log_lines.append('')
        log_lines.append('-' * 50)
        log_lines.append('  SINCRONIZACION ML -> ODOO')
        log_lines.append('-' * 50)

        sync_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0

        http = self.env['mercadolibre.http']
        ItemModel = self.env['mercadolibre.item']

        # Obtener lista de items del vendedor
        try:
            params = {
                'limit': self.limit,
            }
            if self.item_status_filter != 'all':
                params['status'] = self.item_status_filter

            response = http._request(
                account_id=self.account_id.id,
                endpoint=f'/users/{self.account_id.ml_user_id}/items/search',
                method='GET',
                params=params
            )

            item_ids = response.get('data', {}).get('results', [])
            total = response.get('data', {}).get('paging', {}).get('total', len(item_ids))

            log_lines.append(f'  Total items en ML: {total}')
            log_lines.append(f'  A procesar: {len(item_ids)}')

        except Exception as e:
            log_lines.append(f'  ERROR obteniendo lista: {str(e)}')
            return {'sync_count': 0, 'created_count': 0, 'updated_count': 0, 'error_count': 1}

        # Procesar cada item
        for ml_item_id in item_ids:
            try:
                # Obtener detalle del item
                item_response = http._request(
                    account_id=self.account_id.id,
                    endpoint=f'/items/{ml_item_id}',
                    method='GET'
                )
                item_data = item_response.get('data', {})

                # Crear o actualizar item local
                item, is_new = ItemModel.create_from_ml_data(item_data, self.account_id)
                sync_count += 1

                if is_new:
                    created_count += 1
                    action = 'NUEVO'
                else:
                    updated_count += 1
                    action = 'ACTUALIZADO'

                # Vincular producto si corresponde
                if not item.is_linked and self.link_method != 'manual':
                    self._auto_link_item(item)

                # Sincronizar campos a producto Odoo si esta vinculado
                if item.is_linked:
                    self._sync_item_to_odoo_product(item, log_lines)

                # Crear producto nuevo si corresponde
                elif self.create_new_products:
                    product = self._create_product_from_item(item)
                    if product:
                        item.write({
                            'product_id': product.id,
                            'product_tmpl_id': product.product_tmpl_id.id,
                        })
                        log_lines.append(f'    [{action}] {ml_item_id}: Producto creado')
                    else:
                        log_lines.append(f'    [{action}] {ml_item_id}: Error creando producto')

                log_lines.append(f'    [{action}] {ml_item_id}: {item.title[:40]}...')

            except Exception as e:
                error_count += 1
                log_lines.append(f'    [ERROR] {ml_item_id}: {str(e)}')
                _logger.error('Error procesando item %s: %s', ml_item_id, str(e))

            # Rate limit: esperar un poco entre requests
            time.sleep(0.1)

        return {
            'sync_count': sync_count,
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': error_count,
        }

    def _sync_to_ml(self, log_lines):
        """Sincroniza productos de Odoo a MercadoLibre"""
        log_lines.append('')
        log_lines.append('-' * 50)
        log_lines.append('  SINCRONIZACION ODOO -> ML')
        log_lines.append('-' * 50)

        sync_count = 0
        updated_count = 0
        error_count = 0

        # Obtener items vinculados
        domain = [
            ('account_id', '=', self.account_id.id),
            ('is_linked', '=', True),
        ]
        if self.item_status_filter != 'all':
            domain.append(('status', '=', self.item_status_filter))

        items = self.env['mercadolibre.item'].search(domain, limit=self.limit)
        log_lines.append(f'  Items vinculados a procesar: {len(items)}')

        http = self.env['mercadolibre.http']

        for item in items:
            try:
                updates = {}
                update_msgs = []

                # Sincronizar stock
                if self.sync_stock_odoo_to_ml:
                    new_stock = int(item.odoo_stock)
                    if new_stock != item.available_quantity:
                        if item.has_variations:
                            # Actualizar stock por variacion
                            for var in item.variation_ids:
                                if var.is_linked:
                                    var_stock = int(var.odoo_stock)
                                    if var_stock != var.available_quantity:
                                        try:
                                            http._request(
                                                account_id=self.account_id.id,
                                                endpoint=f'/items/{item.ml_item_id}/variations/{var.ml_variation_id}',
                                                method='PUT',
                                                body={'available_quantity': var_stock}
                                            )
                                            var.write({'available_quantity': var_stock})
                                        except Exception as e:
                                            _logger.warning('Error actualizando variacion %s: %s',
                                                          var.ml_variation_id, str(e))
                        else:
                            updates['available_quantity'] = new_stock
                            update_msgs.append(f'stock: {item.available_quantity}->{new_stock}')

                # Sincronizar precio
                if self.sync_price_odoo_to_ml:
                    product = item.product_id or (item.product_tmpl_id.product_variant_id if item.product_tmpl_id else False)
                    if product:
                        new_price = product.lst_price
                        if abs(new_price - item.price) > 0.01:
                            updates['price'] = new_price
                            update_msgs.append(f'precio: {item.price}->{new_price}')

                # Sincronizar titulo
                if self.sync_name_to_title:
                    product_tmpl = item.product_tmpl_id
                    if product_tmpl and product_tmpl.name != item.title:
                        # Nota: titulo no se puede cambiar si tiene ventas
                        if item.sold_quantity == 0:
                            updates['title'] = product_tmpl.name
                            update_msgs.append('titulo')

                # Enviar actualizaciones
                if updates:
                    http._request(
                        account_id=self.account_id.id,
                        endpoint=f'/items/{item.ml_item_id}',
                        method='PUT',
                        body=updates
                    )

                    # Actualizar registro local
                    local_updates = {'last_sync': fields.Datetime.now()}
                    if 'available_quantity' in updates:
                        local_updates['available_quantity'] = updates['available_quantity']
                    if 'price' in updates:
                        local_updates['price'] = updates['price']
                    if 'title' in updates:
                        local_updates['title'] = updates['title']
                    item.write(local_updates)

                    sync_count += 1
                    updated_count += 1
                    log_lines.append(f'    [OK] {item.ml_item_id}: {", ".join(update_msgs)}')

            except Exception as e:
                error_count += 1
                log_lines.append(f'    [ERROR] {item.ml_item_id}: {str(e)}')
                item.write({
                    'sync_status': 'error',
                    'sync_error': str(e)
                })

            # Rate limit
            time.sleep(0.1)

        return {
            'sync_count': sync_count,
            'updated_count': updated_count,
            'error_count': error_count,
        }

    def _auto_link_item(self, item):
        """Intenta vincular automaticamente un item con producto Odoo"""
        ProductProduct = self.env['product.product']
        product = False

        if self.link_method == 'seller_sku':
            if item.seller_sku:
                product = ProductProduct.search([
                    ('default_code', '=', item.seller_sku)
                ], limit=1)
            # Tambien buscar en variaciones
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

    def _sync_item_to_odoo_product(self, item, log_lines):
        """Sincroniza datos del item ML al producto Odoo vinculado"""
        product_tmpl = item.product_tmpl_id
        product = item.product_id

        if not product_tmpl and not product:
            return

        updates_tmpl = {}
        updates_prod = {}

        # Sincronizar titulo a nombre
        if self.sync_title_to_name and item.title:
            if product_tmpl and product_tmpl.name != item.title:
                updates_tmpl['name'] = item.title

        # Sincronizar precio
        if self.sync_price_ml_to_odoo and item.price:
            target = product or (product_tmpl.product_variant_id if product_tmpl else False)
            if target and target.lst_price != item.price:
                updates_prod['lst_price'] = item.price

        # Sincronizar descripcion
        if self.sync_description and item.description:
            if product_tmpl and product_tmpl.description_sale != item.description:
                updates_tmpl['description_sale'] = item.description

        # Aplicar actualizaciones
        if updates_tmpl and product_tmpl:
            product_tmpl.write(updates_tmpl)
        if updates_prod and product:
            product.write(updates_prod)

        # Sincronizar stock (crear ajuste de inventario)
        if self.sync_stock_ml_to_odoo and self.create_stock_adjustment:
            self._sync_stock_to_odoo(item, log_lines)

    def _sync_stock_to_odoo(self, item, log_lines):
        """Crea ajuste de inventario para igualar stock de ML"""
        if not item.is_linked:
            return

        product = item.product_id
        if not product:
            return

        location = self.stock_location_id
        if not location:
            return

        # Calcular diferencia
        current_odoo_stock = product.with_context(location=location.id).qty_available
        ml_stock = item.available_quantity
        difference = ml_stock - current_odoo_stock

        if abs(difference) < 0.01:
            return  # Sin diferencia significativa

        # Crear ajuste de inventario
        try:
            quant = self.env['stock.quant'].sudo().search([
                ('product_id', '=', product.id),
                ('location_id', '=', location.id),
            ], limit=1)

            if quant:
                quant.sudo().with_context(inventory_mode=True).write({
                    'inventory_quantity': ml_stock,
                    'inventory_diff_quantity': difference,
                })
                quant.sudo().action_apply_inventory()
            else:
                # Crear quant
                self.env['stock.quant'].sudo().with_context(inventory_mode=True).create({
                    'product_id': product.id,
                    'location_id': location.id,
                    'inventory_quantity': ml_stock,
                })

            log_lines.append(f'      Ajuste inventario: {product.default_code or product.name} '
                           f'{current_odoo_stock} -> {ml_stock}')

        except Exception as e:
            log_lines.append(f'      ERROR ajuste inventario: {str(e)}')
            _logger.error('Error creando ajuste inventario: %s', str(e))

    def _create_product_from_item(self, item):
        """Crea un producto Odoo desde un item ML"""
        try:
            vals = {
                'name': item.title,
                'default_code': item.seller_sku or item.seller_custom_field or item.ml_item_id,
                'type': self.default_product_type,
                'list_price': item.price,
                'sale_ok': True,
                'purchase_ok': True,
            }

            if self.default_category_id:
                vals['categ_id'] = self.default_category_id.id

            if self.default_uom_id:
                vals['uom_id'] = self.default_uom_id.id
                vals['uom_po_id'] = self.default_uom_id.id

            if item.description:
                vals['description_sale'] = item.description

            product_tmpl = self.env['product.template'].create(vals)
            return product_tmpl.product_variant_id

        except Exception as e:
            _logger.error('Error creando producto desde item %s: %s', item.ml_item_id, str(e))
            return False

    # =====================================================
    # ACCION: GENERAR REPORTE DE CONCILIACION
    # =====================================================
    def action_generate_reconcile_report(self):
        """Genera reporte de conciliacion de inventario"""
        self.ensure_one()

        ReconcileModel = self.env['mercadolibre.stock.reconcile']

        # Limpiar reportes anteriores de esta config
        ReconcileModel.search([
            ('sync_config_id', '=', self.id)
        ]).unlink()

        # Obtener items vinculados con diferencias
        items = self.env['mercadolibre.item'].search([
            ('account_id', '=', self.account_id.id),
            ('is_linked', '=', True),
            ('stock_alert', '=', True),
        ])

        reconcile_lines = []
        for item in items:
            if item.has_variations:
                for var in item.variation_ids:
                    if var.is_linked and var.stock_difference != 0:
                        reconcile_lines.append({
                            'sync_config_id': self.id,
                            'item_id': item.id,
                            'variation_id': var.id,
                            'product_id': var.product_id.id,
                            'ml_stock': var.available_quantity,
                            'odoo_stock': var.odoo_stock,
                            'difference': var.stock_difference,
                        })
            else:
                reconcile_lines.append({
                    'sync_config_id': self.id,
                    'item_id': item.id,
                    'product_id': item.product_id.id if item.product_id else (
                        item.product_tmpl_id.product_variant_id.id if item.product_tmpl_id else False
                    ),
                    'ml_stock': item.available_quantity,
                    'odoo_stock': item.odoo_stock,
                    'difference': item.stock_difference,
                })

        if reconcile_lines:
            ReconcileModel.create(reconcile_lines)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Conciliacion de Inventario'),
            'res_model': 'mercadolibre.stock.reconcile',
            'view_mode': 'tree,form',
            'domain': [('sync_config_id', '=', self.id)],
            'context': {'default_sync_config_id': self.id},
        }
