# -*- coding: utf-8 -*-

import json
import time
import logging
import pytz
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

MEXICO_TZ = pytz.timezone('America/Mexico_City')


class MercadolibreOrderSyncConfig(models.Model):
    _name = 'mercadolibre.order.sync.config'
    _description = 'Configuracion de Sincronizacion de Ordenes'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo para identificar esta sincronizacion'
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

    # Filtros
    status_filter = fields.Selection([
        ('all', 'Todos los Estados'),
        ('paid', 'Solo Pagadas'),
        ('confirmed', 'Confirmadas'),
    ], string='Filtrar por Estado', default='paid', required=True)

    # =====================================================
    # FILTRO POR TIPO LOGISTICO
    # =====================================================
    sync_all_logistic_types = fields.Boolean(
        string='Sincronizar Todos los Tipos Logisticos',
        default=True,
        help='Si esta activo, se sincronizan todos los tipos logisticos. '
             'Si esta desactivado, solo se sincronizan los tipos seleccionados.'
    )
    logistic_type_ids = fields.Many2many(
        'mercadolibre.logistic.type',
        'mercadolibre_sync_config_logistic_type_rel',
        'sync_config_id', 'logistic_type_id',
        string='Tipos Logisticos a Sincronizar',
        help='Seleccione los tipos logisticos que desea sincronizar. '
             'Solo las ordenes de estos tipos seran procesadas.'
    )
    logistic_type_codes = fields.Char(
        string='Codigos de Tipos Logisticos',
        compute='_compute_logistic_type_codes',
        store=True,
        help='Codigos de tipos logisticos seleccionados (para filtrado)'
    )

    period = fields.Selection([
        ('today', 'Hoy'),
        ('yesterday', 'Ayer'),
        ('last_3_days', 'Ultimos 3 dias'),
        ('last_7_days', 'Ultimos 7 dias'),
        ('last_15_days', 'Ultimos 15 dias'),
        ('last_30_days', 'Ultimos 30 dias'),
    ], string='Periodo', default='today', required=True)

    limit = fields.Integer(
        string='Limite',
        default=50,
        help='Numero maximo de ordenes a sincronizar por ejecucion'
    )

    # Programacion - FLEXIBLE (minutos, horas, dias)
    interval_number = fields.Integer(
        string='Ejecutar cada',
        default=15,
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
    last_sync_count = fields.Integer(
        string='Ultimas Sincronizadas',
        readonly=True
    )
    last_sync_created = fields.Integer(
        string='Ultimas Nuevas',
        readonly=True
    )
    last_sync_updated = fields.Integer(
        string='Ultimas Actualizadas',
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
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('paused', 'Pausado'),
    ], string='Estado', default='draft', readonly=True)

    cron_id = fields.Many2one(
        'ir.cron',
        string='Tarea Programada',
        readonly=True,
        ondelete='set null'
    )

    # Estadisticas
    total_syncs = fields.Integer(
        string='Total Ejecuciones',
        readonly=True,
        default=0
    )
    total_orders_synced = fields.Integer(
        string='Total Ordenes Sincronizadas',
        readonly=True,
        default=0
    )

    # =====================================================
    # CONFIGURACION DE CREACION DE ORDENES ODOO
    # =====================================================
    create_sale_orders = fields.Boolean(
        string='Crear Ordenes de Venta',
        default=True,
        help='Crear ordenes de venta (sale.order) automaticamente'
    )

    # Auto confirm
    auto_confirm_order = fields.Boolean(
        string='Confirmar Orden Auto',
        default=False,
        help='Confirmar las ordenes de venta automaticamente'
    )

    # Defaults
    default_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacen por Defecto',
        domain="[('company_id', '=', company_id)]"
    )
    default_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Tarifa por Defecto'
    )
    default_team_id = fields.Many2one(
        'crm.team',
        string='Equipo Ventas por Defecto'
    )
    default_customer_id = fields.Many2one(
        'res.partner',
        string='Cliente por Defecto',
        help='Cliente a usar cuando no se puede identificar al comprador'
    )
    default_product_id = fields.Many2one(
        'product.product',
        string='Producto por Defecto',
        help='Producto a usar cuando no se encuentra por SKU'
    )
    discount_product_id = fields.Many2one(
        'product.product',
        string='Producto Descuento Vendedor',
        help='Producto para registrar los descuentos aportados por el vendedor (co-fondeo)'
    )

    # =====================================================
    # CONFIGURACION DE MANEJO DE APORTE ML (CO-FONDEO)
    # =====================================================
    meli_discount_handling = fields.Selection([
        ('ignore', 'No registrar'),
        ('same_order', 'Linea en la misma orden'),
        ('separate_order', 'Orden de venta separada'),
    ], string='Manejo Aporte ML', default='ignore',
       help='Como manejar el aporte de MercadoLibre en promociones co-fondeadas')

    meli_discount_product_id = fields.Many2one(
        'product.product',
        string='Producto Aporte ML',
        help='Producto a usar cuando se registra el aporte de MercadoLibre como ingreso'
    )

    meli_discount_partner_id = fields.Many2one(
        'res.partner',
        string='Cliente para Aporte ML',
        help='Cliente a usar cuando se crea orden separada para aporte ML (ej: "MercadoLibre")'
    )

    # Sync discounts
    sync_discounts = fields.Boolean(
        string='Sincronizar Descuentos',
        default=True,
        help='Obtener informacion detallada de descuentos desde la API'
    )

    # Pack handling
    group_by_pack = fields.Boolean(
        string='Agrupar por Pack',
        default=True,
        help='Agrupar ordenes con el mismo pack_id en una sola orden de venta'
    )

    # Estadisticas de ordenes Odoo
    last_sale_orders_created = fields.Integer(
        string='Ultimas Ordenes Creadas',
        readonly=True
    )
    total_sale_orders_created = fields.Integer(
        string='Total Ordenes Creadas',
        readonly=True,
        default=0
    )

    @api.depends('logistic_type_ids', 'logistic_type_ids.code')
    def _compute_logistic_type_codes(self):
        """Calcula los codigos de tipos logisticos seleccionados"""
        for record in self:
            if record.logistic_type_ids:
                codes = record.logistic_type_ids.mapped('code')
                record.logistic_type_codes = ','.join(filter(None, codes))
            else:
                record.logistic_type_codes = ''

    def get_allowed_logistic_types(self):
        """
        Retorna lista de codigos de tipos logisticos permitidos para sincronizar.
        Si sync_all_logistic_types es True, retorna None (todos permitidos).
        """
        self.ensure_one()
        _logger.info(
            'get_allowed_logistic_types: sync_all=%s, logistic_type_ids=%s',
            self.sync_all_logistic_types,
            self.logistic_type_ids.mapped('code') if self.logistic_type_ids else []
        )
        if self.sync_all_logistic_types:
            _logger.info('Retornando None (todos los tipos permitidos)')
            return None
        if self.logistic_type_ids:
            codes = self.logistic_type_ids.mapped('code')
            _logger.info('Retornando tipos permitidos: %s', codes)
            return codes
        _logger.info('Retornando lista vacia (ningun tipo permitido)')
        return []

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

    def action_activate(self):
        """Activa la sincronizacion automatica"""
        for record in self:
            if not record.account_id.has_valid_token:
                raise ValidationError(_('La cuenta %s no tiene un token valido.') % record.account_id.name)

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
                raise ValidationError(_('La cuenta %s no tiene un token valido.') % record.account_id.name)

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
            'name': f'Sync Ordenes ML: {self.name}',
            'model_id': self.env['ir.model']._get('mercadolibre.order.sync.config').id,
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

    def _get_date_range(self):
        """Calcula el rango de fechas segun el periodo"""
        now_mexico = datetime.now(MEXICO_TZ)
        today = now_mexico.date()

        period_days = {
            'today': 0,
            'yesterday': 1,
            'last_3_days': 3,
            'last_7_days': 7,
            'last_15_days': 15,
            'last_30_days': 30,
        }

        days = period_days.get(self.period, 0)

        if self.period == 'yesterday':
            date_from = today - timedelta(days=1)
            date_to = today - timedelta(days=1)
        else:
            date_from = today - timedelta(days=days)
            date_to = today

        return date_from, date_to

    def _execute_sync(self):
        """Ejecuta la sincronizacion de ordenes"""
        self.ensure_one()

        _logger.info('='*60)
        _logger.info('SYNC ORDENES ML: Iniciando "%s"', self.name)
        _logger.info('='*60)

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
        log_lines.append(f'  SYNC ORDENES ML: {self.name}')
        log_lines.append('=' * 50)

        now_mexico = datetime.now(MEXICO_TZ)
        log_lines.append(f'  Fecha (Mexico): {now_mexico.strftime("%d/%m/%Y %H:%M:%S")}')
        log_lines.append('')

        date_from, date_to = self._get_date_range()

        log_lines.append(f'  Cuenta:    {self.account_id.name}')
        log_lines.append(f'  Periodo:   {self.period}')
        log_lines.append(f'  Fechas:    {date_from.strftime("%d/%m/%Y")} a {date_to.strftime("%d/%m/%Y")}')
        log_lines.append('')

        # Obtener token
        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            log_lines.append(f'ERROR: No se pudo obtener token: {str(e)}')
            self.write({
                'last_run': fields.Datetime.now(),
                'last_sync_log': '\n'.join(log_lines),
                'last_sync_errors': 1,
            })
            return False

        import requests

        # Construir parametros de busqueda
        params = {
            'seller': self.account_id.ml_user_id,
            'sort': 'date_desc',
            'limit': self.limit,
        }

        # Filtro por fechas
        if date_from:
            dt_from = datetime.combine(date_from, datetime.min.time())
            dt_from_mx = MEXICO_TZ.localize(dt_from)
            params['order.date_created.from'] = dt_from_mx.strftime('%Y-%m-%dT%H:%M:%S.000%z')
            params['order.date_created.from'] = params['order.date_created.from'][:-2] + ':' + params['order.date_created.from'][-2:]

        if date_to:
            dt_to = datetime.combine(date_to, datetime.max.time().replace(microsecond=999000))
            dt_to_mx = MEXICO_TZ.localize(dt_to)
            params['order.date_created.to'] = dt_to_mx.strftime('%Y-%m-%dT%H:%M:%S.999%z')
            params['order.date_created.to'] = params['order.date_created.to'][:-2] + ':' + params['order.date_created.to'][-2:]

        # Filtro por estado
        if self.status_filter and self.status_filter != 'all':
            params['order.status'] = self.status_filter

        url = 'https://api.mercadolibre.com/orders/search'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        LogModel = self.env['mercadolibre.log'].sudo()
        headers_log = {k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()}
        start_time = time.time()

        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)
            duration = time.time() - start_time

            response_body_log = response.text[:10000] if response.text else ''
            LogModel.create({
                'log_type': 'api_request',
                'level': 'success' if response.status_code == 200 else 'error',
                'account_id': self.account_id.id,
                'message': f'Order Sync "{self.name}": GET /orders/search - {response.status_code}',
                'request_url': response.url,
                'request_method': 'GET',
                'request_headers': json.dumps(headers_log, indent=2),
                'request_body': json.dumps(params, indent=2),
                'response_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers), indent=2),
                'response_body': response_body_log,
                'duration': duration,
            })

            if response.status_code != 200:
                log_lines.append(f'ERROR API: {response.status_code}')
                self.write({
                    'last_run': fields.Datetime.now(),
                    'last_sync_log': '\n'.join(log_lines),
                    'last_sync_errors': 1,
                })
                return False

            data = response.json()

        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexion: %s', str(e))
            log_lines.append(f'ERROR conexion: {str(e)}')
            self.write({
                'last_run': fields.Datetime.now(),
                'last_sync_log': '\n'.join(log_lines),
                'last_sync_errors': 1,
            })
            return False

        results = data.get('results', [])
        total = data.get('paging', {}).get('total', len(results))

        log_lines.append(f'  Total en ML:   {total}')
        log_lines.append(f'  A procesar:    {len(results)}')
        log_lines.append('')

        OrderModel = self.env['mercadolibre.order']
        sync_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0

        # Contadores para ordenes Odoo
        sale_orders_created = 0
        sale_orders_errors = 0

        synced_orders = []

        for order_data in results:
            ml_id = order_data.get('id')

            try:
                order, is_new = OrderModel.create_from_ml_data(order_data, self.account_id)
                sync_count += 1
                if is_new:
                    created_count += 1
                else:
                    updated_count += 1

                if order:
                    synced_orders.append(order)

                    # Sincronizar descuentos si esta configurado
                    if self.sync_discounts:
                        order._sync_discounts_from_api()

                    # Sincronizar logistic_type desde shipment si no vino en la orden
                    if not order.logistic_type and order.ml_shipment_id:
                        try:
                            logistic_type = order._fetch_logistic_type_from_shipment()
                            if logistic_type:
                                order.write({'logistic_type': logistic_type})
                                _logger.info('Logistic type actualizado para orden %s: %s',
                                           order.ml_order_id, logistic_type)
                        except Exception as e:
                            _logger.warning('Error obteniendo logistic_type para %s: %s',
                                          order.ml_order_id, str(e))

            except Exception as e:
                error_count += 1
                _logger.error('Error procesando orden %s: %s', ml_id, str(e))

        # Crear ordenes de venta si esta configurado
        if self.create_sale_orders and synced_orders:
            log_lines.append('')
            log_lines.append('-' * 50)
            log_lines.append('  CREACION DE ORDENES DE VENTA')
            log_lines.append('-' * 50)

            # Log detallado de configuracion
            _logger.warning('='*60)
            _logger.warning('INICIO CREACION ORDENES VENTA - Config: %s', self.name)
            _logger.warning('sync_all_logistic_types: %s', self.sync_all_logistic_types)
            _logger.warning('logistic_type_ids seleccionados: %s',
                          self.logistic_type_ids.mapped(lambda x: (x.id, x.name, x.code)) if self.logistic_type_ids else 'NINGUNO')
            _logger.warning('='*60)

            # Obtener tipos logisticos permitidos
            allowed_logistic_types = self.get_allowed_logistic_types()
            if allowed_logistic_types is not None:
                log_lines.append(f'  Tipos logisticos permitidos: {", ".join(allowed_logistic_types) or "Ninguno"}')
                log_lines.append(f'  sync_all_logistic_types: {self.sync_all_logistic_types}')
                _logger.warning('*** FILTRO ACTIVO ***: Solo se crearan ordenes con tipo en: %s', allowed_logistic_types)
            else:
                log_lines.append('  Tipos logisticos: Todos (sin filtro) - VERIFICAR CONFIGURACION')
                log_lines.append('  NOTA: Para filtrar, desmarca "Sincronizar Todos los Tipos Logisticos"')
                _logger.warning('*** SIN FILTRO ***: sync_all_logistic_types=True, se crearan TODAS las ordenes')
                _logger.warning('Para activar filtrado: desmarca "Sincronizar Todos los Tipos Logisticos" en la config')

            # Agrupar por pack_id si esta configurado
            if self.group_by_pack:
                orders_to_process = self._group_orders_by_pack(synced_orders)
            else:
                orders_to_process = synced_orders

            # Contadores adicionales para filtrado por tipo logistico
            skipped_logistic_type = 0
            skipped_no_logistic = 0

            for order in orders_to_process:
                if order.sale_order_id:
                    continue

                if order.status not in ('paid', 'partially_paid'):
                    continue

                # Filtrar por tipo logistico si esta configurado
                if allowed_logistic_types is not None:
                    order_logistic = order.logistic_type
                    _logger.info('Orden %s: logistic_type=%s, permitidos=%s',
                               order.ml_order_id, order_logistic, allowed_logistic_types)

                    if not order_logistic:
                        # Si no tiene logistic_type, intentar obtenerlo del shipment
                        if order.ml_shipment_id:
                            try:
                                fetched_type = order._fetch_logistic_type_from_shipment()
                                if fetched_type:
                                    order.write({'logistic_type': fetched_type})
                                    order_logistic = fetched_type
                                    _logger.info('Orden %s: logistic_type obtenido del shipment: %s',
                                               order.ml_order_id, fetched_type)
                            except Exception as e:
                                _logger.warning('Error obteniendo logistic_type para filtro: %s', str(e))

                    if not order_logistic:
                        skipped_no_logistic += 1
                        log_lines.append(f'    [SKIP] {order.ml_order_id}: sin tipo logistico')
                        _logger.info('Orden %s omitida: sin tipo logistico', order.ml_order_id)
                        continue

                    if order_logistic not in allowed_logistic_types:
                        skipped_logistic_type += 1
                        log_lines.append(f'    [SKIP] {order.ml_order_id}: tipo {order_logistic} no permitido')
                        _logger.info('Orden %s omitida: tipo logistico %s no esta en %s',
                                   order.ml_order_id, order_logistic, allowed_logistic_types)
                        continue

                try:
                    sale_order = order._create_sale_order(self)
                    if sale_order:
                        sale_orders_created += 1
                        log_lines.append(f'    [OK] {order.ml_order_id}: {sale_order.name} ({order.logistic_type or "sin tipo"})')
                except Exception as e:
                    sale_orders_errors += 1
                    log_lines.append(f'    [ERROR] {order.ml_order_id}: {str(e)}')

            log_lines.append(f'  Ordenes creadas: {sale_orders_created}')
            if skipped_logistic_type:
                log_lines.append(f'  Omitidas (tipo no permitido): {skipped_logistic_type}')
            if skipped_no_logistic:
                log_lines.append(f'  Omitidas (sin tipo): {skipped_no_logistic}')
            log_lines.append(f'  Errores:         {sale_orders_errors}')

        log_lines.append('')
        log_lines.append('-' * 50)
        log_lines.append('  RESUMEN SYNC')
        log_lines.append('-' * 50)
        log_lines.append(f'  Sincronizadas: {sync_count}')
        log_lines.append(f'    Nuevas:      {created_count}')
        log_lines.append(f'    Actualizadas:{updated_count}')
        log_lines.append(f'  Errores:       {error_count}')
        if self.create_sale_orders:
            log_lines.append(f'  Ordenes Odoo:  {sale_orders_created}')
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
            'total_orders_synced': self.total_orders_synced + sync_count,
            'last_sale_orders_created': sale_orders_created,
            'total_sale_orders_created': self.total_sale_orders_created + sale_orders_created,
        })

        _logger.info('SYNC ORDENES "%s" completada: %d sincronizadas', self.name, sync_count)
        return True

    def _group_orders_by_pack(self, orders):
        """
        Agrupa ordenes por pack_id para crear una sola orden de venta por pack.
        Retorna solo la primera orden de cada pack (que tendra todos los items).
        """
        packs_processed = set()
        result = []

        for order in orders:
            if order.ml_pack_id:
                if order.ml_pack_id not in packs_processed:
                    packs_processed.add(order.ml_pack_id)
                    result.append(order)
            else:
                result.append(order)

        return result
