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


class MercadolibrePaymentSyncConfig(models.Model):
    _name = 'mercadolibre.payment.sync.config'
    _description = 'Configuracion de Sincronizacion Automatica de Pagos'
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
        default=True,
        help='Si esta desactivado, la sincronizacion no se ejecutara'
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
    payment_direction_filter = fields.Selection([
        ('all', 'Todos los Pagos'),
        ('incoming', 'Solo Recibidos (Ingresos)'),
        ('outgoing', 'Solo Realizados (Egresos)'),
    ], string='Direccion', default='all', required=True)

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
    ], string='Filtrar por Estado', default='all', required=True)

    date_field = fields.Selection([
        ('date_created', 'Fecha de Creacion'),
        ('date_approved', 'Fecha de Aprobacion'),
        ('date_last_updated', 'Fecha de Actualizacion'),
        ('money_release_date', 'Fecha de Liberacion'),
    ], string='Campo de Fecha', default='date_created', required=True)

    period = fields.Selection([
        ('today', 'Hoy'),
        ('yesterday', 'Ayer'),
        ('last_3_days', 'Ultimos 3 dias'),
        ('last_7_days', 'Ultimos 7 dias'),
        ('last_15_days', 'Ultimos 15 dias'),
        ('last_30_days', 'Ultimos 30 dias'),
    ], string='Periodo', default='today', required=True,
       help='Periodo de fechas a sincronizar')

    only_released = fields.Boolean(
        string='Solo Dinero Liberado',
        default=False
    )
    only_approved = fields.Boolean(
        string='Solo Aprobados',
        default=False
    )
    limit = fields.Integer(
        string='Limite',
        default=100,
        help='Numero maximo de pagos a sincronizar por ejecucion'
    )

    # Programacion
    interval_number = fields.Integer(
        string='Ejecutar cada',
        default=6,
        required=True,
        help='Frecuencia de ejecucion'
    )
    interval_type = fields.Selection([
        ('minutes', 'Minutos'),
        ('hours', 'Horas'),
        ('days', 'Dias'),
    ], string='Tipo Intervalo', default='hours', required=True)

    next_run = fields.Datetime(
        string='Proxima Ejecucion',
        help='Fecha y hora de la proxima ejecucion programada'
    )
    last_run = fields.Datetime(
        string='Ultima Ejecucion',
        readonly=True
    )
    last_sync_count = fields.Integer(
        string='Ultimos Sincronizados',
        readonly=True,
        help='Cantidad de pagos sincronizados en la ultima ejecucion'
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
    total_payments_synced = fields.Integer(
        string='Total Pagos Sincronizados',
        readonly=True,
        default=0
    )

    # =====================================================
    # CONFIGURACION DE CREACION DE PAGOS ODOO
    # =====================================================
    create_odoo_payments = fields.Boolean(
        string='Crear Pagos en Odoo',
        default=False,
        help='Si esta activo, creara registros account.payment en Odoo automaticamente'
    )

    # Diarios
    incoming_journal_id = fields.Many2one(
        'account.journal',
        string='Diario Ingresos',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help='Diario para registrar pagos recibidos (ingresos de clientes)'
    )
    outgoing_journal_id = fields.Many2one(
        'account.journal',
        string='Diario Egresos',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help='Diario para registrar pagos realizados (pagos a proveedores)'
    )
    commission_journal_id = fields.Many2one(
        'account.journal',
        string='Diario Comisiones',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help='Diario para registrar comisiones de MercadoPago'
    )

    # Partners por defecto
    default_customer_id = fields.Many2one(
        'res.partner',
        string='Cliente por Defecto',
        help='Cliente a usar cuando no se puede identificar al pagador (ingresos)'
    )
    default_vendor_id = fields.Many2one(
        'res.partner',
        string='Proveedor por Defecto',
        help='Proveedor a usar cuando no se encuentra coincidencia con proveedores conocidos (egresos)'
    )

    # Comisiones
    create_commission_payments = fields.Boolean(
        string='Crear Pagos de Comisiones',
        default=True,
        help='Crear pagos separados para las comisiones de MercadoPago'
    )
    commission_partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor Comisiones',
        help='Proveedor para registrar las comisiones (ej: MercadoPago/MercadoLibre)'
    )

    # Confirmacion automatica
    auto_confirm_payment = fields.Boolean(
        string='Confirmar Pagos Automaticamente',
        default=False,
        help='Si esta activo, los pagos se confirmaran automaticamente (action_post) al crearse'
    )

    # Estadisticas de pagos Odoo
    last_odoo_payments_created = fields.Integer(
        string='Ultimos Pagos Odoo Creados',
        readonly=True
    )
    total_odoo_payments_created = fields.Integer(
        string='Total Pagos Odoo Creados',
        readonly=True,
        default=0
    )

    def write(self, vals):
        result = super().write(vals)
        # Si se activa, asegurar que el cron este activo
        if 'active' in vals:
            for record in self:
                if record.cron_id:
                    record.cron_id.active = vals['active'] and record.state == 'active'
        return result

    def unlink(self):
        # Eliminar crons asociados
        for record in self:
            if record.cron_id:
                record.cron_id.unlink()
        return super().unlink()

    def action_activate(self):
        """Activa la sincronizacion automatica"""
        for record in self:
            if not record.account_id.has_valid_token:
                raise ValidationError(_('La cuenta %s no tiene un token valido.') % record.account_id.name)

            # Crear o actualizar cron
            record._create_or_update_cron()

            # Establecer proxima ejecucion si no existe
            if not record.next_run:
                record.next_run = fields.Datetime.now()

            record.state = 'active'

    def action_pause(self):
        """Pausa la sincronizacion automatica"""
        for record in self:
            if record.cron_id:
                record.cron_id.active = False
            record.state = 'paused'

    def action_resume(self):
        """Reanuda la sincronizacion automatica"""
        for record in self:
            if not record.account_id.has_valid_token:
                raise ValidationError(_('La cuenta %s no tiene un token valido.') % record.account_id.name)

            if record.cron_id:
                record.cron_id.active = True
            else:
                record._create_or_update_cron()

            record.state = 'active'

    def action_run_now(self):
        """Ejecuta la sincronizacion manualmente ahora"""
        self.ensure_one()
        return self._execute_sync()

    def _create_or_update_cron(self):
        """Crea o actualiza el cron job para esta configuracion"""
        self.ensure_one()

        cron_vals = {
            'name': f'Sync Pagos ML: {self.name}',
            'model_id': self.env['ir.model']._get('mercadolibre.payment.sync.config').id,
            'state': 'code',
            'code': f'model.browse({self.id})._execute_sync()',
            'interval_number': self.interval_number,
            'interval_type': self.interval_type,
            'numbercall': -1,  # Infinito
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
        """Calcula el rango de fechas segun el periodo configurado (en zona horaria Mexico)"""
        # Obtener la fecha actual en Mexico (no UTC)
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
        """Ejecuta la sincronizacion de pagos"""
        self.ensure_one()

        _logger.info('='*60)
        _logger.info('SYNC AUTO: Iniciando "%s"', self.name)
        _logger.info('='*60)

        if not self.account_id.has_valid_token:
            _logger.error('La cuenta %s no tiene token valido', self.account_id.name)
            self.write({
                'last_run': fields.Datetime.now(),
                'last_sync_log': 'ERROR: La cuenta no tiene un token valido',
                'last_sync_errors': 1,
            })
            return False

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append(f'  SYNC AUTO: {self.name}')
        log_lines.append('=' * 50)

        # Mostrar hora de Mexico para claridad
        now_mexico = datetime.now(MEXICO_TZ)
        log_lines.append(f'  Fecha (Mexico): {now_mexico.strftime("%d/%m/%Y %H:%M:%S")}')
        log_lines.append('')

        # Obtener rango de fechas
        date_from, date_to = self._get_date_range()

        # Labels para el log
        direction_labels = {
            'all': 'Todos',
            'incoming': 'Recibidos',
            'outgoing': 'Realizados',
        }
        status_labels = {
            'all': 'Todos',
            'approved': 'Aprobados',
            'in_mediation': 'En Mediacion',
            'pending': 'Pendientes',
            'in_process': 'En Proceso',
            'rejected': 'Rechazados',
            'refunded': 'Reembolsados',
            'cancelled': 'Cancelados',
            'charged_back': 'Contracargos',
        }
        period_labels = {
            'today': 'Hoy',
            'yesterday': 'Ayer',
            'last_3_days': 'Ultimos 3 dias',
            'last_7_days': 'Ultimos 7 dias',
            'last_15_days': 'Ultimos 15 dias',
            'last_30_days': 'Ultimos 30 dias',
        }

        # Formatear fechas
        date_from_str = date_from.strftime('%d/%m/%Y') if date_from else 'N/A'
        date_to_str = date_to.strftime('%d/%m/%Y') if date_to else 'N/A'

        log_lines.append(f'  Cuenta:    {self.account_id.name}')
        log_lines.append(f'  Direccion: {direction_labels.get(self.payment_direction_filter)}')
        log_lines.append(f'  Estado:    {status_labels.get(self.status_filter)}')
        log_lines.append(f'  Periodo:   {period_labels.get(self.period)}')
        log_lines.append(f'  Fechas:    {date_from_str} a {date_to_str}')
        log_lines.append('')

        # Obtener token con reintentos automáticos
        access_token = self.account_id.get_valid_token_with_retry(max_retries=2)
        if not access_token:
            _logger.error('No se pudo obtener token válido')
            log_lines.append('ERROR: No se pudo obtener token válido.')
            log_lines.append('Por favor reconecte la cuenta desde MercadoLibre > Cuentas')
            self.write({
                'last_run': fields.Datetime.now(),
                'last_sync_log': '\n'.join(log_lines),
                'last_sync_errors': 1,
            })
            return False

        import requests

        # Construir parametros
        params = {
            'sort': self.date_field,
            'criteria': 'desc',
            'limit': self.limit,
            'range': self.date_field,
        }

        # Fechas
        if date_from:
            dt_from = datetime.combine(date_from, datetime.min.time())
            dt_from_mx = MEXICO_TZ.localize(dt_from)
            params['begin_date'] = dt_from_mx.strftime('%Y-%m-%dT%H:%M:%S.000%z')
            params['begin_date'] = params['begin_date'][:-2] + ':' + params['begin_date'][-2:]

        if date_to:
            dt_to = datetime.combine(date_to, datetime.max.time().replace(microsecond=999000))
            dt_to_mx = MEXICO_TZ.localize(dt_to)
            params['end_date'] = dt_to_mx.strftime('%Y-%m-%dT%H:%M:%S.999%z')
            params['end_date'] = params['end_date'][:-2] + ':' + params['end_date'][-2:]

        # Filtro de estado
        if self.status_filter and self.status_filter != 'all':
            params['status'] = self.status_filter
        elif self.only_approved:
            params['status'] = 'approved'

        filter_status_locally = self.status_filter and self.status_filter != 'all'
        account_user_id = self.account_id.ml_user_id
        filter_direction_locally = self.payment_direction_filter in ('incoming', 'outgoing')

        url = 'https://api.mercadopago.com/v1/payments/search'
        LogModel = self.env['mercadolibre.log'].sudo()

        # Función para hacer la llamada con retry en caso de 401
        def make_api_call(token, retry_count=0):
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }
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
                    'message': f'Auto Sync "{self.name}": GET /v1/payments/search - {response.status_code}',
                    'request_url': response.url,
                    'request_method': 'GET',
                    'request_headers': json.dumps(headers_log, indent=2),
                    'request_body': json.dumps(params, indent=2),
                    'response_code': response.status_code,
                    'response_headers': json.dumps(dict(response.headers), indent=2),
                    'response_body': response_body_log,
                    'duration': duration,
                })

                # Si es error 401, intentar refrescar token y reintentar
                if response.status_code == 401 and retry_count < 2:
                    _logger.warning('Token expirado (401), intentando refrescar...')
                    log_lines.append(f'  Token expirado, refrescando... (intento {retry_count + 1})')

                    new_token = self.account_id.get_valid_token_with_retry(max_retries=1)
                    if new_token:
                        return make_api_call(new_token, retry_count + 1)
                    else:
                        return None, 'No se pudo refrescar el token'

                if response.status_code != 200:
                    return None, f'Error API: {response.status_code}'

                return response.json(), None

            except requests.exceptions.RequestException as e:
                _logger.error('Error de conexion: %s', str(e))
                return None, str(e)

        # Ejecutar llamada con retry automático
        data, error = make_api_call(access_token)

        if error:
            log_lines.append(f'ERROR: {error}')
            self.write({
                'last_run': fields.Datetime.now(),
                'last_sync_log': '\n'.join(log_lines),
                'last_sync_errors': 1,
            })
            return False

        results = data.get('results', [])
        total = data.get('paging', {}).get('total', len(results))

        # Filtrar por direccion
        if filter_direction_locally and account_user_id:
            filtered_results = []
            for payment_data in results:
                payer = payment_data.get('payer', {}) or {}
                payer_id = str(payer.get('id', '')) if payer.get('id') else str(payment_data.get('payer_id', ''))
                collector = payment_data.get('collector', {}) or {}
                collector_id = str(payment_data.get('collector_id', '')) if payment_data.get('collector_id') else str(collector.get('id', ''))

                if self.payment_direction_filter == 'outgoing' and payer_id == account_user_id:
                    filtered_results.append(payment_data)
                elif self.payment_direction_filter == 'incoming' and collector_id == account_user_id:
                    filtered_results.append(payment_data)
            results = filtered_results

        # Filtrar por estado
        if filter_status_locally:
            results = [p for p in results if p.get('status') == self.status_filter]

        log_lines.append(f'  Total en MP:  {total}')
        log_lines.append(f'  A procesar:   {len(results)}')
        log_lines.append('')

        PaymentModel = self.env['mercadolibre.payment']
        sync_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0
        skipped_count = 0

        # Contadores para pagos Odoo
        odoo_payments_created = 0
        odoo_payments_errors = 0
        odoo_commissions_created = 0

        # Lista de pagos sincronizados para crear pagos Odoo despues
        synced_payments = []

        for payment_data in results:
            mp_id = payment_data.get('id')
            release_status = payment_data.get('money_release_status')

            if self.only_released and release_status != 'released':
                skipped_count += 1
                continue

            try:
                payment, is_new = PaymentModel.create_from_mp_data(payment_data, self.account_id)
                sync_count += 1
                if is_new:
                    created_count += 1
                else:
                    updated_count += 1

                # Agregar a la lista para crear pagos Odoo
                if payment:
                    synced_payments.append(payment)

            except Exception as e:
                error_count += 1
                _logger.error('Error procesando pago %s: %s', mp_id, str(e))

        # =====================================================
        # CREAR PAGOS EN ODOO SI ESTA CONFIGURADO
        # =====================================================
        if self.create_odoo_payments and synced_payments:
            log_lines.append('')
            log_lines.append('-' * 50)
            log_lines.append('  CREACION DE PAGOS ODOO')
            log_lines.append('-' * 50)

            for payment in synced_payments:
                # Solo procesar pagos aprobados sin pago Odoo existente
                if payment.status != 'approved':
                    continue
                if payment.odoo_payment_id:
                    continue
                # Validar direccion del pago vs configuracion
                if self.payment_direction_filter == 'incoming' and payment.payment_direction != 'incoming':
                    continue
                if self.payment_direction_filter == 'outgoing' and payment.payment_direction != 'outgoing':
                    continue

                try:
                    result = payment._create_odoo_payment(self)
                    if result.get('payment'):
                        odoo_payments_created += 1
                        log_lines.append(f'    [OK] Pago {payment.mp_payment_id}: {result["payment"].name}')
                    if result.get('commission_payment'):
                        odoo_commissions_created += 1
                    if result.get('error'):
                        odoo_payments_errors += 1
                        log_lines.append(f'    [ERROR] Pago {payment.mp_payment_id}: {result["error"]}')
                except Exception as e:
                    odoo_payments_errors += 1
                    _logger.error('Error creando pago Odoo para %s: %s', payment.mp_payment_id, str(e))
                    log_lines.append(f'    [ERROR] Pago {payment.mp_payment_id}: {str(e)}')

            log_lines.append(f'  Pagos Odoo creados:     {odoo_payments_created}')
            log_lines.append(f'  Comisiones creadas:     {odoo_commissions_created}')
            log_lines.append(f'  Errores pagos Odoo:     {odoo_payments_errors}')

        log_lines.append('')
        log_lines.append('-' * 50)
        log_lines.append('  RESUMEN SYNC')
        log_lines.append('-' * 50)
        log_lines.append(f'  Sincronizados: {sync_count}')
        log_lines.append(f'    Nuevos:      {created_count}')
        log_lines.append(f'    Actualizados:{updated_count}')
        log_lines.append(f'  Saltados:      {skipped_count}')
        log_lines.append(f'  Errores:       {error_count}')
        if self.create_odoo_payments:
            log_lines.append(f'  Pagos Odoo:    {odoo_payments_created} ({odoo_commissions_created} comisiones)')
        log_lines.append('=' * 50)

        # Calcular proxima ejecucion
        next_run = fields.Datetime.now()
        if self.interval_type == 'minutes':
            next_run += timedelta(minutes=self.interval_number)
        elif self.interval_type == 'hours':
            next_run += timedelta(hours=self.interval_number)
        elif self.interval_type == 'days':
            next_run += timedelta(days=self.interval_number)

        update_vals = {
            'last_run': fields.Datetime.now(),
            'last_sync_count': sync_count,
            'last_sync_created': created_count,
            'last_sync_updated': updated_count,
            'last_sync_errors': error_count,
            'last_sync_log': '\n'.join(log_lines),
            'next_run': next_run,
            'total_syncs': self.total_syncs + 1,
            'total_payments_synced': self.total_payments_synced + sync_count,
        }

        # Agregar estadisticas de pagos Odoo si aplica
        if self.create_odoo_payments:
            update_vals['last_odoo_payments_created'] = odoo_payments_created
            update_vals['total_odoo_payments_created'] = self.total_odoo_payments_created + odoo_payments_created

        self.write(update_vals)

        _logger.info('SYNC AUTO "%s" completada: %d sincronizados', self.name, sync_count)

        return True

    @api.onchange('payment_direction_filter')
    def _onchange_payment_direction_filter(self):
        if self.payment_direction_filter == 'incoming':
            self.date_field = 'money_release_date'
            self.only_released = True
            self.only_approved = True
            self.status_filter = 'approved'
        elif self.payment_direction_filter == 'outgoing':
            self.date_field = 'date_last_updated'
            self.only_released = False
            self.only_approved = False
            self.status_filter = 'all'
        else:
            self.date_field = 'date_created'
            self.only_released = False
            self.only_approved = False
            self.status_filter = 'all'

    @api.onchange('status_filter')
    def _onchange_status_filter(self):
        if self.status_filter == 'in_mediation':
            self.date_field = 'date_last_updated'
            self.only_released = False
            self.only_approved = False
        elif self.status_filter == 'approved':
            self.date_field = 'date_approved'
            self.only_approved = True
        elif self.status_filter in ('pending', 'in_process'):
            self.date_field = 'date_created'
            self.only_released = False
            self.only_approved = False
        elif self.status_filter in ('rejected', 'cancelled', 'refunded', 'charged_back'):
            self.date_field = 'date_last_updated'
            self.only_released = False
            self.only_approved = False
