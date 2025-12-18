# -*- coding: utf-8 -*-

import json
import time
import logging
import pytz
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Timezone de Mexico Ciudad de Mexico
MEXICO_TZ = pytz.timezone('America/Mexico_City')


class MercadolibrePaymentSync(models.TransientModel):
    _name = 'mercadolibre.payment.sync'
    _description = 'Asistente de Sincronizacion de Pagos'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]"
    )
    date_field = fields.Selection([
        ('date_created', 'Fecha de Creacion'),
        ('date_approved', 'Fecha de Aprobacion'),
        ('date_last_updated', 'Fecha de Actualizacion'),
        ('money_release_date', 'Fecha de Liberacion'),
    ], string='Filtrar por Fecha', default='date_created', required=True,
       help='Campo de fecha a utilizar para filtrar los pagos')
    date_from = fields.Date(
        string='Desde',
        default=lambda self: fields.Date.today() - timedelta(days=30)
    )
    date_to = fields.Date(
        string='Hasta',
        default=lambda self: fields.Date.today()
    )
    payment_direction_filter = fields.Selection([
        ('all', 'Todos los Pagos'),
        ('incoming', 'Solo Recibidos (Ingresos)'),
        ('outgoing', 'Solo Realizados (Egresos)'),
    ], string='Direccion', default='all', required=True,
       help='Filtrar por direccion del pago: recibidos (eres el vendedor) o realizados (eres el comprador)')

    status_filter = fields.Selection([
        ('all', 'Todos los Estados'),
        ('approved', 'Solo Aprobados'),
        ('in_mediation', 'En Mediacion'),
        ('pending', 'Pendientes'),
        ('in_process', 'En Proceso'),
        ('rejected', 'Rechazados'),
        ('refunded', 'Reembolsados'),
        ('cancelled', 'Cancelados'),
        ('charged_back', 'Contracargos'),
    ], string='Filtrar por Estado', default='all', required=True,
       help='Filtrar pagos por su estado en MercadoPago')

    only_released = fields.Boolean(
        string='Solo Dinero Liberado',
        default=False,
        help='Sincronizar solo pagos con dinero ya liberado en MercadoPago (solo aplica a pagos recibidos)'
    )
    only_approved = fields.Boolean(
        string='Solo Aprobados',
        default=False,
        help='Sincronizar solo pagos con estado aprobado'
    )
    limit = fields.Integer(
        string='Limite',
        default=100,
        help='Numero maximo de pagos a sincronizar'
    )

    @api.onchange('payment_direction_filter')
    def _onchange_payment_direction_filter(self):
        """Ajusta valores por defecto segun la direccion seleccionada"""
        if self.payment_direction_filter == 'incoming':
            # Para pagos recibidos: usar fecha de liberacion, solo liberados y aprobados
            self.date_field = 'money_release_date'
            self.only_released = True
            self.only_approved = True
            self.status_filter = 'approved'
        elif self.payment_direction_filter == 'outgoing':
            # Para pagos realizados: usar fecha de actualizacion, sin filtros de liberacion/aprobado
            self.date_field = 'date_last_updated'
            self.only_released = False
            self.only_approved = False
            self.status_filter = 'all'
        else:
            # Todos: usar fecha de creacion, sin filtros
            self.date_field = 'date_created'
            self.only_released = False
            self.only_approved = False
            self.status_filter = 'all'

    @api.onchange('status_filter')
    def _onchange_status_filter(self):
        """Ajusta valores por defecto segun el estado seleccionado"""
        if self.status_filter == 'in_mediation':
            # Para pagos en mediacion: el dinero esta congelado, usar fecha de actualizacion
            self.date_field = 'date_last_updated'
            self.only_released = False
            self.only_approved = False
        elif self.status_filter == 'approved':
            # Para pagos aprobados: usar fecha de aprobacion
            self.date_field = 'date_approved'
            self.only_approved = True
        elif self.status_filter in ('pending', 'in_process'):
            # Para pagos pendientes/en proceso: usar fecha de creacion
            self.date_field = 'date_created'
            self.only_released = False
            self.only_approved = False
        elif self.status_filter in ('rejected', 'cancelled', 'refunded', 'charged_back'):
            # Para pagos rechazados/cancelados/reembolsados/contracargos: usar fecha de actualizacion
            self.date_field = 'date_last_updated'
            self.only_released = False
            self.only_approved = False
        elif self.status_filter == 'all':
            # Para todos: mantener configuracion actual o usar fecha de creacion
            if not self.date_field:
                self.date_field = 'date_created'

    # Results
    sync_count = fields.Integer(
        string='Pagos Sincronizados',
        readonly=True
    )
    created_count = fields.Integer(
        string='Nuevos',
        readonly=True,
        help='Pagos nuevos creados'
    )
    updated_count = fields.Integer(
        string='Actualizados',
        readonly=True,
        help='Pagos existentes actualizados'
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
        """Ejecuta la sincronizacion de pagos"""
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise ValidationError(_('La cuenta no tiene un token valido.'))

        _logger.info('='*60)
        _logger.info('INICIANDO SINCRONIZACION DE PAGOS')
        _logger.info('='*60)
        _logger.info('Cuenta: %s', self.account_id.name)
        _logger.info('Periodo: %s a %s', self.date_from, self.date_to)
        _logger.info('Filtro estado: %s', self.status_filter)
        _logger.info('Solo liberados: %s', self.only_released)
        _logger.info('Solo aprobados: %s', self.only_approved)
        _logger.info('Limite: %d', self.limit)

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append('       SINCRONIZACION DE PAGOS MERCADOPAGO')
        log_lines.append('=' * 50)
        log_lines.append('')
        # Mapeo de campos de fecha para mostrar en el log
        date_field_labels = {
            'date_created': 'Fecha de Creacion',
            'date_approved': 'Fecha de Aprobacion',
            'date_last_updated': 'Fecha de Actualizacion',
            'money_release_date': 'Fecha de Liberacion',
        }
        date_field_label = date_field_labels.get(self.date_field, self.date_field)

        # Formatear fechas en formato mexicano
        def format_date_mx(d):
            if not d:
                return 'N/A'
            meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                     'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            return f'{d.day:02d}/{meses[d.month-1]}/{d.year}'

        # Obtener offset actual de Mexico City
        now_mx = datetime.now(MEXICO_TZ)
        tz_offset = now_mx.strftime('%z')
        tz_offset_formatted = f'{tz_offset[:-2]}:{tz_offset[-2:]}'
        tz_name = 'CST' if now_mx.dst() == timedelta(0) else 'CDT'

        # Mapeo de direccion para mostrar en el log
        direction_labels = {
            'all': 'Todos los Pagos',
            'incoming': 'Solo Recibidos (Ingresos)',
            'outgoing': 'Solo Realizados (Egresos)',
        }
        direction_label = direction_labels.get(self.payment_direction_filter, 'Todos')

        # Mapeo de estados para mostrar en el log
        status_labels = {
            'all': 'Todos los Estados',
            'approved': 'Solo Aprobados',
            'in_mediation': 'En Mediacion',
            'pending': 'Pendientes',
            'in_process': 'En Proceso',
            'rejected': 'Rechazados',
            'refunded': 'Reembolsados',
            'cancelled': 'Cancelados',
            'charged_back': 'Contracargos',
        }
        status_label = status_labels.get(self.status_filter, 'Todos')

        log_lines.append(f'  Cuenta:          {self.account_id.name}')
        log_lines.append(f'  Direccion:       {direction_label}')
        log_lines.append(f'  Estado:          {status_label}')
        log_lines.append(f'  Filtrar por:     {date_field_label}')
        log_lines.append(f'  Periodo:         {format_date_mx(self.date_from)} a {format_date_mx(self.date_to)}')
        log_lines.append(f'  Zona horaria:    America/Mexico_City ({tz_name} UTC{tz_offset_formatted})')
        log_lines.append(f'  Solo liberados:  {"Si" if self.only_released else "No"}')
        log_lines.append(f'  Solo aprobados:  {"Si" if self.only_approved else "No"}')
        log_lines.append(f'  Limite:          {self.limit}')
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
            'sort': self.date_field,  # Ordenar por el campo de fecha seleccionado
            'criteria': 'desc',
            'limit': self.limit,
            'range': self.date_field,  # Filtrar por el campo de fecha seleccionado
        }

        if self.date_from:
            # Crear datetime al inicio del dia en Mexico City
            dt_from = datetime.combine(self.date_from, datetime.min.time())
            dt_from_mx = MEXICO_TZ.localize(dt_from)
            params['begin_date'] = dt_from_mx.strftime('%Y-%m-%dT%H:%M:%S.000%z')
            # Insertar ':' en el offset (formato ISO 8601)
            params['begin_date'] = params['begin_date'][:-2] + ':' + params['begin_date'][-2:]

        if self.date_to:
            # Crear datetime al final del dia en Mexico City
            dt_to = datetime.combine(self.date_to, datetime.max.time().replace(microsecond=999000))
            dt_to_mx = MEXICO_TZ.localize(dt_to)
            params['end_date'] = dt_to_mx.strftime('%Y-%m-%dT%H:%M:%S.999%z')
            # Insertar ':' en el offset (formato ISO 8601)
            params['end_date'] = params['end_date'][:-2] + ':' + params['end_date'][-2:]

        # Filtrar por estado especifico si no es 'all'
        # status_filter tiene prioridad sobre only_approved
        if self.status_filter and self.status_filter != 'all':
            params['status'] = self.status_filter
        elif self.only_approved:
            params['status'] = 'approved'

        # Flag para indicar si necesitamos filtrar localmente por estado
        # (para estados que la API no soporta o cuando queremos filtrar adicional)
        filter_status_locally = self.status_filter and self.status_filter != 'all'

        # Nota: MercadoPago API no soporta filtrar por collector_id ni payer_id
        # Descargamos todos los pagos y filtramos localmente por direccion
        account_user_id = self.account_id.ml_user_id
        filter_direction_locally = self.payment_direction_filter in ('incoming', 'outgoing')

        url = 'https://api.mercadopago.com/v1/payments/search'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        _logger.info('URL: %s', url)
        _logger.info('Params: %s', params)

        # Registrar en mercadolibre.log
        LogModel = self.env['mercadolibre.log'].sudo()
        headers_log = {k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()}

        start_time = time.time()

        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)
            duration = time.time() - start_time
            _logger.info('Response Code: %d', response.status_code)

            # Guardar log en mercadolibre.log
            response_body_log = response.text[:10000] if response.text else ''
            LogModel.create({
                'log_type': 'api_request',
                'level': 'success' if response.status_code == 200 else 'error',
                'account_id': self.account_id.id,
                'message': f'Payment Sync: GET /v1/payments/search - {response.status_code}',
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
                _logger.error(error_msg)
                log_lines.append(f'ERROR: {error_msg}')
                self.write({
                    'state': 'error',
                    'sync_log': '\n'.join(log_lines),
                })
                raise ValidationError(error_msg)

            data = response.json()

        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            _logger.error('Error de conexion: %s', str(e))

            # Guardar log de error
            LogModel.create({
                'log_type': 'api_request',
                'level': 'error',
                'account_id': self.account_id.id,
                'message': f'Payment Sync: GET /v1/payments/search - Error',
                'request_url': url,
                'request_method': 'GET',
                'request_headers': json.dumps(headers_log, indent=2),
                'request_body': json.dumps(params, indent=2),
                'error_details': str(e),
                'duration': duration,
            })

            log_lines.append(f'ERROR de conexion: {str(e)}')
            self.write({
                'state': 'error',
                'sync_log': '\n'.join(log_lines),
            })
            raise ValidationError(_(f'Error de conexion: {str(e)}'))

        results = data.get('results', [])
        paging = data.get('paging', {})
        total = paging.get('total', len(results))
        total_before_filter = len(results)

        # Filtrar localmente por direccion si es necesario (para pagos outgoing)
        if filter_direction_locally and account_user_id:
            filtered_results = []
            for payment_data in results:
                # Obtener payer_id del pago
                payer = payment_data.get('payer', {}) or {}
                payer_id = str(payer.get('id', '')) if payer.get('id') else str(payment_data.get('payer_id', ''))

                # Obtener collector_id del pago
                collector = payment_data.get('collector', {}) or {}
                collector_id = str(payment_data.get('collector_id', '')) if payment_data.get('collector_id') else str(collector.get('id', ''))

                # Filtrar segun direccion
                if self.payment_direction_filter == 'outgoing' and payer_id == account_user_id:
                    filtered_results.append(payment_data)
                elif self.payment_direction_filter == 'incoming' and collector_id == account_user_id:
                    filtered_results.append(payment_data)

            results = filtered_results

        # Filtrar localmente por estado si es necesario (respaldo para asegurar precision)
        if filter_status_locally:
            status_filtered_results = []
            for payment_data in results:
                payment_status = payment_data.get('status', '')
                if payment_status == self.status_filter:
                    status_filtered_results.append(payment_data)
            results = status_filtered_results

        log_lines.append('-' * 50)
        log_lines.append('  RESULTADOS DE BUSQUEDA')
        log_lines.append('-' * 50)
        log_lines.append(f'  Total en MercadoPago:  {total}')
        log_lines.append(f'  Obtenidos:             {total_before_filter}')
        if filter_direction_locally or filter_status_locally:
            log_lines.append(f'  Despues de filtros:    {len(results)}')
        log_lines.append('')
        log_lines.append('-' * 50)
        log_lines.append('  DETALLE DE PAGOS')
        log_lines.append('-' * 50)

        _logger.info('Total encontrados: %d', total)
        _logger.info('Resultados en pagina: %d', len(results))

        PaymentModel = self.env['mercadolibre.payment']
        sync_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0
        skipped_count = 0

        for payment_data in results:
            mp_id = payment_data.get('id')
            status = payment_data.get('status')
            release_status = payment_data.get('money_release_status')
            amount = payment_data.get('transaction_amount', 0)

            # Filtrar por dinero liberado
            if self.only_released and release_status != 'released':
                _logger.debug('Saltando pago %s - dinero no liberado: %s',
                             mp_id, release_status)
                skipped_count += 1
                continue

            try:
                payment, is_new = PaymentModel.create_from_mp_data(payment_data, self.account_id)
                sync_count += 1
                if is_new:
                    created_count += 1
                    action_label = 'NUEVO'
                else:
                    updated_count += 1
                    action_label = 'ACTUALIZADO'
                log_lines.append(f'  [{action_label:^11}]  #{mp_id}  ${amount:>12,.2f}  {status}')
                _logger.info('Sincronizado pago %s - $%.2f (%s)', mp_id, amount, action_label)

            except Exception as e:
                error_count += 1
                log_lines.append(f'  [ERROR      ]  #{mp_id}  {str(e)}')
                _logger.error('Error procesando pago %s: %s', mp_id, str(e))

        log_lines.append('')
        log_lines.append('=' * 50)
        log_lines.append('  RESUMEN')
        log_lines.append('=' * 50)
        log_lines.append(f'  Total sincronizados:     {sync_count}')
        log_lines.append(f'    - Nuevos:              {created_count}')
        log_lines.append(f'    - Actualizados:        {updated_count}')
        log_lines.append(f'  Saltados (no liberados): {skipped_count}')
        log_lines.append(f'  Errores:                 {error_count}')
        log_lines.append('=' * 50)

        _logger.info('='*60)
        _logger.info('SINCRONIZACION COMPLETADA')
        _logger.info('Sincronizados: %d (Nuevos: %d, Actualizados: %d) | Saltados: %d | Errores: %d',
                    sync_count, created_count, updated_count, skipped_count, error_count)
        _logger.info('='*60)

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
            'name': _('Sincronizacion de Pagos'),
            'res_model': 'mercadolibre.payment.sync',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_payments(self):
        """Abre la vista de pagos sincronizados"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pagos Sincronizados'),
            'res_model': 'mercadolibre.payment',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.account_id.id)],
            'context': {'default_account_id': self.account_id.id},
        }

    def action_new_sync(self):
        """Inicia una nueva sincronizacion"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizar Pagos'),
            'res_model': 'mercadolibre.payment.sync',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_account_id': self.account_id.id},
        }
