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


class MercadolibreOrderSync(models.TransientModel):
    _name = 'mercadolibre.order.sync'
    _description = 'Asistente de Sincronizacion de Ordenes'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]"
    )

    # Busqueda especifica
    search_specific = fields.Boolean(
        string='Buscar Orden Especifica',
        default=False
    )
    specific_order_id = fields.Char(
        string='ID de Orden',
        help='ID de la orden de MercadoLibre a sincronizar'
    )

    # Filtros
    date_from = fields.Date(
        string='Desde',
        default=lambda self: fields.Date.today() - timedelta(days=7)
    )
    date_to = fields.Date(
        string='Hasta',
        default=lambda self: fields.Date.today()
    )
    status_filter = fields.Selection([
        ('all', 'Todos los Estados'),
        ('paid', 'Solo Pagadas'),
        ('confirmed', 'Confirmadas'),
        ('cancelled', 'Canceladas'),
    ], string='Filtrar por Estado', default='paid', required=True)

    limit = fields.Integer(
        string='Limite',
        default=50
    )

    # Sync discounts
    sync_discounts = fields.Boolean(
        string='Sincronizar Descuentos',
        default=True,
        help='Obtener informacion detallada de descuentos'
    )

    # Sync logistic type
    sync_logistic_type = fields.Boolean(
        string='Sincronizar Tipo Envio',
        default=True,
        help='Obtener tipo logistico desde el shipment cuando no viene en la orden'
    )

    # Results
    sync_count = fields.Integer(
        string='Ordenes Sincronizadas',
        readonly=True
    )
    created_count = fields.Integer(
        string='Nuevas',
        readonly=True
    )
    updated_count = fields.Integer(
        string='Actualizadas',
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
    state = fields.Selection([
        ('draft', 'Configuracion'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], string='Estado', default='draft')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to:
                if record.date_from > record.date_to:
                    raise ValidationError(_('La fecha desde no puede ser mayor que la fecha hasta.'))

    def action_sync(self):
        """Ejecuta la sincronizacion de ordenes"""
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise ValidationError(_('La cuenta no tiene un token valido.'))

        if self.search_specific:
            return self._sync_specific_order()

        _logger.info('='*60)
        _logger.info('INICIANDO SINCRONIZACION DE ORDENES')
        _logger.info('='*60)

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append('    SINCRONIZACION DE ORDENES MERCADOLIBRE')
        log_lines.append('=' * 50)
        log_lines.append('')

        def format_date_mx(d):
            if not d:
                return 'N/A'
            meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                     'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            return f'{d.day:02d}/{meses[d.month-1]}/{d.year}'

        status_labels = {
            'all': 'Todos los Estados',
            'paid': 'Solo Pagadas',
            'confirmed': 'Confirmadas',
            'cancelled': 'Canceladas',
        }

        log_lines.append(f'  Cuenta:    {self.account_id.name}')
        log_lines.append(f'  Estado:    {status_labels.get(self.status_filter)}')
        log_lines.append(f'  Periodo:   {format_date_mx(self.date_from)} a {format_date_mx(self.date_to)}')
        log_lines.append(f'  Limite:    {self.limit}')
        log_lines.append('')

        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            _logger.error('Error obteniendo token: %s', str(e))
            self.write({
                'state': 'error',
                'sync_log': f'Error: {str(e)}',
            })
            raise ValidationError(_(f'Error obteniendo token: {str(e)}'))

        import requests

        # Construir parametros
        params = {
            'seller': self.account_id.ml_user_id,
            'sort': 'date_desc',
            'limit': self.limit,
        }

        if self.date_from:
            dt_from = datetime.combine(self.date_from, datetime.min.time())
            dt_from_mx = MEXICO_TZ.localize(dt_from)
            params['order.date_created.from'] = dt_from_mx.strftime('%Y-%m-%dT%H:%M:%S.000%z')
            params['order.date_created.from'] = params['order.date_created.from'][:-2] + ':' + params['order.date_created.from'][-2:]

        if self.date_to:
            dt_to = datetime.combine(self.date_to, datetime.max.time().replace(microsecond=999000))
            dt_to_mx = MEXICO_TZ.localize(dt_to)
            params['order.date_created.to'] = dt_to_mx.strftime('%Y-%m-%dT%H:%M:%S.999%z')
            params['order.date_created.to'] = params['order.date_created.to'][:-2] + ':' + params['order.date_created.to'][-2:]

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
                'message': f'Order Sync Wizard: GET /orders/search - {response.status_code}',
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
                error_msg = f'Error API: {response.status_code} - {response.text}'
                log_lines.append(f'ERROR: {error_msg}')
                self.write({
                    'state': 'error',
                    'sync_log': '\n'.join(log_lines),
                })
                raise ValidationError(error_msg)

            data = response.json()

        except requests.exceptions.RequestException as e:
            log_lines.append(f'ERROR conexion: {str(e)}')
            self.write({
                'state': 'error',
                'sync_log': '\n'.join(log_lines),
            })
            raise ValidationError(_(f'Error de conexion: {str(e)}'))

        results = data.get('results', [])
        paging = data.get('paging', {})
        total = paging.get('total', len(results))

        log_lines.append('-' * 50)
        log_lines.append('  RESULTADOS DE BUSQUEDA')
        log_lines.append('-' * 50)
        log_lines.append(f'  Total en MercadoLibre: {total}')
        log_lines.append(f'  Obtenidas:             {len(results)}')
        log_lines.append('')
        log_lines.append('-' * 50)
        log_lines.append('  DETALLE DE ORDENES')
        log_lines.append('-' * 50)

        OrderModel = self.env['mercadolibre.order']
        sync_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0

        for order_data in results:
            ml_id = order_data.get('id')
            status = order_data.get('status')
            amount = order_data.get('total_amount', 0)
            pack_id = order_data.get('pack_id', '')

            try:
                order, is_new = OrderModel.create_from_ml_data(order_data, self.account_id)
                sync_count += 1
                if is_new:
                    created_count += 1
                    action_label = 'NUEVO'
                else:
                    updated_count += 1
                    action_label = 'ACTUALIZADO'

                # Sincronizar descuentos si esta activado
                if self.sync_discounts and order:
                    order._sync_discounts_from_api()

                # Sincronizar tipo logistico si no vino en la orden
                logistic_info = ''
                if self.sync_logistic_type and order:
                    if not order.logistic_type and order.ml_shipment_id:
                        try:
                            logistic_type = order._fetch_logistic_type_from_shipment()
                            if logistic_type:
                                order.write({'logistic_type': logistic_type})
                                logistic_info = f' [{logistic_type}]'
                        except Exception as e:
                            _logger.warning('Error obteniendo logistic_type para %s: %s',
                                          order.ml_order_id, str(e))
                    elif order.logistic_type:
                        logistic_info = f' [{order.logistic_type}]'

                pack_info = f' Pack:{pack_id}' if pack_id else ''
                log_lines.append(f'  [{action_label:^11}]  #{ml_id}  ${amount:>12,.2f}  {status}{pack_info}{logistic_info}')

            except Exception as e:
                error_count += 1
                log_lines.append(f'  [ERROR      ]  #{ml_id}  {str(e)}')
                _logger.error('Error procesando orden %s: %s', ml_id, str(e))

        log_lines.append('')
        log_lines.append('=' * 50)
        log_lines.append('  RESUMEN')
        log_lines.append('=' * 50)
        log_lines.append(f'  Total sincronizadas: {sync_count}')
        log_lines.append(f'    - Nuevas:          {created_count}')
        log_lines.append(f'    - Actualizadas:    {updated_count}')
        log_lines.append(f'  Errores:             {error_count}')
        log_lines.append('=' * 50)

        self.write({
            'state': 'done',
            'sync_count': sync_count,
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': error_count,
            'sync_log': '\n'.join(log_lines),
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizacion de Ordenes'),
            'res_model': 'mercadolibre.order.sync',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _sync_specific_order(self):
        """Sincroniza una orden especifica por su ID"""
        self.ensure_one()

        if not self.specific_order_id:
            raise ValidationError(_('Debe ingresar el ID de la orden a buscar.'))

        order_id = self.specific_order_id.strip()

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append('    BUSQUEDA DE ORDEN ESPECIFICA')
        log_lines.append('=' * 50)
        log_lines.append('')
        log_lines.append(f'  Cuenta:    {self.account_id.name}')
        log_lines.append(f'  ID Orden:  {order_id}')
        log_lines.append('')

        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            self.write({
                'state': 'error',
                'sync_log': f'Error: {str(e)}',
            })
            raise ValidationError(_(f'Error obteniendo token: {str(e)}'))

        import requests

        url = f'https://api.mercadolibre.com/orders/{order_id}'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        LogModel = self.env['mercadolibre.log'].sudo()
        headers_log = {k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()}
        start_time = time.time()

        try:
            response = requests.get(url, headers=headers, timeout=60)
            duration = time.time() - start_time

            response_body_log = response.text[:10000] if response.text else ''
            LogModel.create({
                'log_type': 'api_request',
                'level': 'success' if response.status_code == 200 else 'error',
                'account_id': self.account_id.id,
                'message': f'Order Sync Specific: GET /orders/{order_id} - {response.status_code}',
                'request_url': url,
                'request_method': 'GET',
                'request_headers': json.dumps(headers_log, indent=2),
                'response_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers), indent=2),
                'response_body': response_body_log,
                'duration': duration,
            })

            if response.status_code == 404:
                log_lines.append(f'  ERROR: Orden {order_id} no encontrada')
                self.write({
                    'state': 'error',
                    'sync_log': '\n'.join(log_lines),
                })
                raise ValidationError(_(f'Orden {order_id} no encontrada en MercadoLibre.'))

            if response.status_code != 200:
                error_msg = f'Error API: {response.status_code}'
                log_lines.append(f'  ERROR: {error_msg}')
                self.write({
                    'state': 'error',
                    'sync_log': '\n'.join(log_lines),
                })
                raise ValidationError(error_msg)

            order_data = response.json()

        except requests.exceptions.RequestException as e:
            log_lines.append(f'  ERROR conexion: {str(e)}')
            self.write({
                'state': 'error',
                'sync_log': '\n'.join(log_lines),
            })
            raise ValidationError(_(f'Error de conexion: {str(e)}'))

        log_lines.append('-' * 50)
        log_lines.append('  ORDEN ENCONTRADA')
        log_lines.append('-' * 50)
        log_lines.append(f'  ID:         {order_data.get("id")}')
        log_lines.append(f'  Estado:     {order_data.get("status")}')
        log_lines.append(f'  Monto:      ${order_data.get("total_amount", 0):,.2f}')
        log_lines.append(f'  Pack ID:    {order_data.get("pack_id", "N/A")}')
        log_lines.append(f'  Fecha:      {order_data.get("date_created")}')
        log_lines.append('')

        OrderModel = self.env['mercadolibre.order']

        try:
            order, is_new = OrderModel.create_from_ml_data(order_data, self.account_id)
            action_label = 'NUEVA' if is_new else 'ACTUALIZADA'

            # Sincronizar descuentos
            if self.sync_discounts and order:
                order._sync_discounts_from_api()
                log_lines.append(f'  Descuentos sincronizados: {len(order.discount_ids)}')

            # Sincronizar tipo logistico
            if self.sync_logistic_type and order:
                if not order.logistic_type and order.ml_shipment_id:
                    try:
                        logistic_type = order._fetch_logistic_type_from_shipment()
                        if logistic_type:
                            order.write({'logistic_type': logistic_type})
                            log_lines.append(f'  Tipo logistico sincronizado: {logistic_type}')
                    except Exception as e:
                        log_lines.append(f'  Error sincronizando tipo logistico: {str(e)}')
                elif order.logistic_type:
                    log_lines.append(f'  Tipo logistico: {order.logistic_type}')

            log_lines.append('-' * 50)
            log_lines.append('  RESULTADO')
            log_lines.append('-' * 50)
            log_lines.append(f'  Orden {action_label} exitosamente')
            log_lines.append(f'  ID interno: {order.id}')
            log_lines.append('=' * 50)

            self.write({
                'state': 'done',
                'sync_count': 1,
                'created_count': 1 if is_new else 0,
                'updated_count': 0 if is_new else 1,
                'error_count': 0,
                'sync_log': '\n'.join(log_lines),
            })

        except Exception as e:
            log_lines.append('-' * 50)
            log_lines.append('  ERROR AL SINCRONIZAR')
            log_lines.append('-' * 50)
            log_lines.append(f'  {str(e)}')
            log_lines.append('=' * 50)

            self.write({
                'state': 'error',
                'sync_count': 0,
                'error_count': 1,
                'sync_log': '\n'.join(log_lines),
            })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizacion de Ordenes'),
            'res_model': 'mercadolibre.order.sync',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_orders(self):
        """Ver ordenes sincronizadas"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ordenes Sincronizadas'),
            'res_model': 'mercadolibre.order',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.account_id.id)],
            'context': {'default_account_id': self.account_id.id},
        }

    def action_new_sync(self):
        """Nueva sincronizacion"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizar Ordenes'),
            'res_model': 'mercadolibre.order.sync',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_account_id': self.account_id.id},
        }
