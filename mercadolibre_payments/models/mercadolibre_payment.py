# -*- coding: utf-8 -*-

import json
import time
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MercadolibrePayment(models.Model):
    _name = 'mercadolibre.payment'
    _description = 'Pago MercadoPago'
    _order = 'date_approved desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # MercadoPago IDs
    mp_payment_id = fields.Char(
        string='Payment ID',
        required=True,
        readonly=True,
        index=True,
        help='ID del pago en MercadoPago'
    )
    mp_order_id = fields.Char(
        string='Order ID',
        readonly=True,
        index=True,
        help='ID de la orden en MercadoLibre'
    )
    mp_external_reference = fields.Char(
        string='Referencia Externa',
        readonly=True,
        help='Referencia externa del pago'
    )

    # Payment Status
    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('authorized', 'Autorizado'),
        ('in_process', 'En Proceso'),
        ('in_mediation', 'En Mediacion'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Cancelado'),
        ('refunded', 'Reembolsado'),
        ('charged_back', 'Contracargo'),
    ], string='Estado MP', readonly=True, tracking=True, index=True)

    status_detail = fields.Char(
        string='Detalle Estado',
        readonly=True
    )

    # Money Release Status
    money_release_status = fields.Selection([
        ('released', 'Liberado'),
        ('pending', 'Pendiente'),
        ('not_released', 'No Liberado'),
        ('unavailable', 'No Disponible'),
    ], string='Estado Liberacion', readonly=True, tracking=True, index=True,
       help='Estado de liberacion del dinero en MercadoPago')

    money_release_date = fields.Datetime(
        string='Fecha Liberacion',
        readonly=True
    )

    # Sync Status with Odoo
    sync_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('synced', 'Sincronizado'),
        ('error', 'Error'),
        ('ignored', 'Ignorado'),
    ], string='Estado Sync', default='pending', tracking=True)

    sync_error = fields.Text(
        string='Error Sincronizacion',
        readonly=True
    )
    last_sync_date = fields.Datetime(
        string='Ultima Sincronizacion',
        readonly=True
    )

    # Amounts
    transaction_amount = fields.Float(
        string='Monto Total',
        readonly=True,
        digits=(16, 2)
    )
    net_received_amount = fields.Float(
        string='Monto Neto Recibido',
        readonly=True,
        digits=(16, 2),
        help='Monto recibido despues de comisiones'
    )
    total_paid_amount = fields.Float(
        string='Monto Pagado por Cliente',
        readonly=True,
        digits=(16, 2)
    )
    shipping_cost = fields.Float(
        string='Costo de Envio',
        readonly=True,
        digits=(16, 2)
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        readonly=True
    )
    mp_currency = fields.Char(
        string='Moneda MP',
        readonly=True,
        help='Codigo de moneda en MercadoPago'
    )

    # Dates
    date_created = fields.Datetime(
        string='Fecha Creacion',
        readonly=True
    )
    date_approved = fields.Datetime(
        string='Fecha Aprobacion',
        readonly=True,
        index=True
    )
    date_last_updated = fields.Datetime(
        string='Ultima Actualizacion MP',
        readonly=True
    )

    # Payment Method
    payment_method_id = fields.Char(
        string='Metodo Pago ID',
        readonly=True
    )
    payment_method_name = fields.Char(
        string='Metodo de Pago',
        readonly=True
    )
    payment_type = fields.Selection([
        ('credit_card', 'Tarjeta de Credito'),
        ('debit_card', 'Tarjeta de Debito'),
        ('bank_transfer', 'Transferencia Bancaria'),
        ('atm', 'ATM'),
        ('ticket', 'Ticket'),
        ('account_money', 'Dinero en Cuenta'),
        ('digital_currency', 'Moneda Digital'),
        ('digital_wallet', 'Billetera Digital'),
        ('voucher_card', 'Voucher'),
        ('crypto_transfer', 'Cripto'),
        ('other', 'Otro'),
    ], string='Tipo de Pago', readonly=True)

    installments = fields.Integer(
        string='Cuotas',
        readonly=True
    )

    # Payer Info
    payer_id = fields.Char(
        string='Payer ID',
        readonly=True
    )
    payer_email = fields.Char(
        string='Email Pagador',
        readonly=True
    )
    payer_name = fields.Char(
        string='Nombre Pagador',
        readonly=True
    )
    payer_identification_type = fields.Char(
        string='Tipo Doc. Pagador',
        readonly=True
    )
    payer_identification_number = fields.Char(
        string='Num. Doc. Pagador',
        readonly=True
    )

    # Collector Info
    collector_id = fields.Char(
        string='Collector ID',
        readonly=True
    )

    # Operation Type
    operation_type = fields.Char(
        string='Tipo Operacion',
        readonly=True
    )

    # Charges
    charge_ids = fields.One2many(
        'mercadolibre.payment.charge',
        'payment_id',
        string='Cargos'
    )
    total_charges = fields.Float(
        string='Total Cargos',
        compute='_compute_total_charges',
        store=True,
        digits=(16, 2)
    )

    # Raw Data
    raw_data = fields.Text(
        string='Datos Crudos',
        readonly=True,
        help='JSON completo del pago desde MercadoPago'
    )

    # Odoo Accounting Link
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        tracking=True
    )
    payment_move_id = fields.Many2one(
        'account.move',
        string='Asiento de Pago',
        tracking=True
    )

    notes = fields.Text(
        string='Notas'
    )

    _sql_constraints = [
        ('mp_payment_id_uniq', 'unique(mp_payment_id, account_id)',
         'Este pago ya existe para esta cuenta.')
    ]

    @api.depends('mp_payment_id', 'payer_email')
    def _compute_name(self):
        for record in self:
            if record.mp_payment_id:
                record.name = f'PAY-{record.mp_payment_id}'
            else:
                record.name = 'Nuevo Pago'

    @api.depends('charge_ids.amount')
    def _compute_total_charges(self):
        for record in self:
            record.total_charges = sum(record.charge_ids.mapped('amount'))

    @api.model
    def create_from_mp_data(self, data, account):
        """
        Crea o actualiza un pago desde los datos de MercadoPago

        Args:
            data: dict con los datos del pago desde la API
            account: mercadolibre.account record

        Returns:
            mercadolibre.payment record
        """
        mp_payment_id = str(data.get('id', ''))

        if not mp_payment_id:
            _logger.error('No se encontro ID de pago en los datos')
            return False

        # Buscar pago existente
        existing = self.search([
            ('mp_payment_id', '=', mp_payment_id),
            ('account_id', '=', account.id)
        ], limit=1)

        # Preparar valores
        currency = self._get_currency(data.get('currency_id', 'MXN'))

        # Parse payer info
        payer = data.get('payer', {})
        payer_identification = payer.get('identification', {}) or {}

        # Parse fee details for charges
        fee_details = data.get('fee_details', []) or []

        vals = {
            'account_id': account.id,
            'mp_payment_id': mp_payment_id,
            'mp_order_id': str(data.get('order', {}).get('id', '')) if data.get('order') else '',
            'mp_external_reference': data.get('external_reference', ''),
            'status': data.get('status', ''),
            'status_detail': data.get('status_detail', ''),
            'money_release_status': data.get('money_release_status', ''),
            'money_release_date': self._parse_datetime(data.get('money_release_date')),
            'transaction_amount': data.get('transaction_amount', 0.0),
            'net_received_amount': data.get('transaction_details', {}).get('net_received_amount', 0.0),
            'total_paid_amount': data.get('transaction_details', {}).get('total_paid_amount', 0.0),
            'shipping_cost': data.get('shipping_amount', 0.0),
            'currency_id': currency.id if currency else False,
            'mp_currency': data.get('currency_id', ''),
            'date_created': self._parse_datetime(data.get('date_created')),
            'date_approved': self._parse_datetime(data.get('date_approved')),
            'date_last_updated': self._parse_datetime(data.get('date_last_updated')),
            'payment_method_id': data.get('payment_method_id', ''),
            'payment_method_name': data.get('payment_method', {}).get('name', '') if isinstance(data.get('payment_method'), dict) else '',
            'payment_type': self._map_payment_type(data.get('payment_type_id', '')),
            'installments': data.get('installments', 1),
            'payer_id': str(payer.get('id', '')),
            'payer_email': payer.get('email', ''),
            'payer_name': f"{payer.get('first_name', '')} {payer.get('last_name', '')}".strip(),
            'payer_identification_type': payer_identification.get('type', ''),
            'payer_identification_number': payer_identification.get('number', ''),
            'collector_id': str(data.get('collector_id', '')),
            'operation_type': data.get('operation_type', ''),
            'raw_data': json.dumps(data, indent=2, ensure_ascii=False),
            'last_sync_date': fields.Datetime.now(),
        }

        if existing:
            _logger.info('Actualizando pago existente: %s', mp_payment_id)
            existing.write(vals)
            payment = existing
            is_new = False
        else:
            _logger.info('Creando nuevo pago: %s', mp_payment_id)
            payment = self.create(vals)
            is_new = True

        # Crear/actualizar cargos
        self._sync_charges(payment, fee_details)

        return payment, is_new

    def _sync_charges(self, payment, fee_details):
        """Sincroniza los cargos/comisiones del pago"""
        ChargeModel = self.env['mercadolibre.payment.charge']

        # Eliminar cargos existentes
        payment.charge_ids.unlink()

        for fee in fee_details:
            ChargeModel.create({
                'payment_id': payment.id,
                'charge_type': fee.get('type', ''),
                'fee_payer': fee.get('fee_payer', ''),
                'amount': fee.get('amount', 0.0),
            })

    def _get_currency(self, currency_code):
        """Obtiene la moneda de Odoo por codigo"""
        if not currency_code:
            return False

        currency = self.env['res.currency'].search([
            ('name', '=', currency_code)
        ], limit=1)

        return currency

    def _map_payment_type(self, mp_type):
        """Mapea el tipo de pago de MP a la seleccion de Odoo"""
        mapping = {
            'credit_card': 'credit_card',
            'debit_card': 'debit_card',
            'bank_transfer': 'bank_transfer',
            'atm': 'atm',
            'ticket': 'ticket',
            'account_money': 'account_money',
            'digital_currency': 'digital_currency',
            'digital_wallet': 'digital_wallet',
            'voucher_card': 'voucher_card',
            'crypto_transfer': 'crypto_transfer',
        }
        return mapping.get(mp_type, 'other')

    def _parse_datetime(self, dt_string):
        """Parsea fecha/hora de MercadoPago"""
        if not dt_string:
            return False

        try:
            # Formato ISO 8601 con timezone
            if 'T' in dt_string:
                # Remover timezone info para simplificar
                dt_string = dt_string.split('.')[0].replace('T', ' ')
                if '+' in dt_string:
                    dt_string = dt_string.split('+')[0]
                if '-' in dt_string and dt_string.count('-') > 2:
                    parts = dt_string.rsplit('-', 1)
                    dt_string = parts[0]
                return datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
            return datetime.strptime(dt_string, '%Y-%m-%d')
        except (ValueError, TypeError) as e:
            _logger.warning('Error parseando fecha %s: %s', dt_string, str(e))
            return False

    def action_view_raw_data(self):
        """Muestra los datos crudos del pago"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Datos Crudos - {self.name}',
            'res_model': 'mercadolibre.payment',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('mercadolibre_payments.view_mercadolibre_payment_raw_form').id,
            'target': 'new',
        }

    def action_mark_synced(self):
        """Marca el pago como sincronizado"""
        self.write({
            'sync_status': 'synced',
            'sync_error': False,
        })

    def action_mark_ignored(self):
        """Marca el pago como ignorado"""
        self.write({
            'sync_status': 'ignored',
        })

    def action_retry_sync(self):
        """Reintenta la sincronizacion del pago"""
        self.write({
            'sync_status': 'pending',
            'sync_error': False,
        })

    @api.model
    def cron_sync_payments(self):
        """Cron job para sincronizar pagos automaticamente"""
        _logger.info('Iniciando sincronizacion automatica de pagos')

        # Buscar cuentas activas
        accounts = self.env['mercadolibre.account'].search([
            ('state', '=', 'connected'),
            ('has_valid_token', '=', True)
        ])

        for account in accounts:
            try:
                self._sync_account_payments(account)
            except Exception as e:
                _logger.error('Error sincronizando pagos de cuenta %s: %s',
                             account.name, str(e))

        _logger.info('Sincronizacion automatica de pagos finalizada')

    def _sync_account_payments(self, account, date_from=None, date_to=None,
                                only_released=True, limit=50):
        """
        Sincroniza pagos de una cuenta

        Args:
            account: mercadolibre.account record
            date_from: fecha inicio (opcional)
            date_to: fecha fin (opcional)
            only_released: solo pagos con dinero liberado
            limit: limite de registros
        """
        _logger.info('Sincronizando pagos de cuenta: %s', account.name)

        try:
            access_token = account.get_valid_token()
        except Exception as e:
            _logger.error('No se pudo obtener token: %s', str(e))
            return 0

        # Construir parametros de busqueda
        params = {
            'sort': 'date_approved',
            'criteria': 'desc',
            'limit': limit,
        }

        if date_from:
            params['begin_date'] = date_from.strftime('%Y-%m-%dT00:00:00.000-00:00')
        if date_to:
            params['end_date'] = date_to.strftime('%Y-%m-%dT23:59:59.999-00:00')

        # Filtrar por estado aprobado
        params['status'] = 'approved'

        # Llamar a la API
        import requests

        url = 'https://api.mercadopago.com/v1/payments/search'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        _logger.info('Consultando pagos: %s', url)
        _logger.info('Params: %s', params)

        # Preparar para log
        LogModel = self.env['mercadolibre.log'].sudo()
        headers_log = {k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()}
        start_time = time.time()

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            duration = time.time() - start_time

            # Guardar log en mercadolibre.log
            response_body_log = response.text[:10000] if response.text else ''
            LogModel.create({
                'log_type': 'api_request',
                'level': 'success' if response.status_code == 200 else 'error',
                'account_id': account.id,
                'message': f'Cron Payment Sync: GET /v1/payments/search - {response.status_code}',
                'request_url': response.url,
                'request_method': 'GET',
                'request_headers': json.dumps(headers_log, indent=2),
                'request_body': json.dumps(params, indent=2),
                'response_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers), indent=2),
                'response_body': response_body_log,
                'duration': duration,
            })

            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            _logger.error('Error consultando pagos: %s', str(e))

            # Guardar log de error
            LogModel.create({
                'log_type': 'api_request',
                'level': 'error',
                'account_id': account.id,
                'message': f'Cron Payment Sync: GET /v1/payments/search - Error',
                'request_url': url,
                'request_method': 'GET',
                'request_headers': json.dumps(headers_log, indent=2),
                'request_body': json.dumps(params, indent=2),
                'error_details': str(e),
                'duration': duration,
            })
            return 0

        results = data.get('results', [])
        _logger.info('Encontrados %d pagos', len(results))

        synced_count = 0
        created_count = 0
        updated_count = 0
        for payment_data in results:
            # Filtrar por dinero liberado si es requerido
            if only_released:
                if payment_data.get('money_release_status') != 'released':
                    continue

            try:
                payment, is_new = self.create_from_mp_data(payment_data, account)
                synced_count += 1
                if is_new:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                _logger.error('Error procesando pago %s: %s',
                             payment_data.get('id'), str(e))

        _logger.info('Sincronizados %d pagos para cuenta %s (Nuevos: %d, Actualizados: %d)',
                    synced_count, account.name, created_count, updated_count)
        return synced_count
