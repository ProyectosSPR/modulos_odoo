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
    description = fields.Text(
        string='Descripcion',
        readonly=True,
        help='Descripcion del pago en MercadoPago'
    )

    # Payment Direction (incoming = received, outgoing = made by us)
    payment_direction = fields.Selection([
        ('incoming', 'Recibido'),
        ('outgoing', 'Realizado'),
        ('unknown', 'Desconocido'),
    ], string='Direccion', readonly=True, index=True, default='unknown',
       help='Indica si el pago fue recibido (incoming) o realizado por nosotros (outgoing)')

    is_incoming = fields.Boolean(
        string='Es Ingreso',
        compute='_compute_is_incoming',
        store=True,
        help='True si es un pago que recibimos'
    )
    is_outgoing = fields.Boolean(
        string='Es Egreso',
        compute='_compute_is_incoming',
        store=True,
        help='True si es un pago que realizamos'
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

    # =====================================================
    # CAMPOS PARA PAGOS ODOO (account.payment)
    # =====================================================
    odoo_payment_id = fields.Many2one(
        'account.payment',
        string='Pago Odoo',
        readonly=True,
        tracking=True,
        help='Pago registrado en Odoo contabilidad'
    )
    commission_payment_id = fields.Many2one(
        'account.payment',
        string='Pago Comision Odoo',
        readonly=True,
        tracking=True,
        help='Pago de comision registrado en Odoo'
    )

    # Vendor matching para egresos
    matched_vendor_id = fields.Many2one(
        'mercadolibre.known.vendor',
        string='Proveedor Detectado',
        readonly=True,
        help='Proveedor conocido detectado por palabras clave'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner Asignado',
        tracking=True,
        help='Partner de Odoo asignado a este pago'
    )

    # Estado de creacion de pago Odoo
    odoo_payment_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('created', 'Creado'),
        ('error', 'Error'),
        ('skipped', 'Omitido'),
    ], string='Estado Pago Odoo', default='pending', tracking=True)

    odoo_payment_error = fields.Text(
        string='Error Pago Odoo',
        readonly=True
    )

    has_odoo_payment = fields.Boolean(
        string='Tiene Pago Odoo',
        compute='_compute_has_odoo_payment',
        store=True
    )
    has_commission_payment = fields.Boolean(
        string='Tiene Pago Comision',
        compute='_compute_has_odoo_payment',
        store=True
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

    @api.depends('payment_direction')
    def _compute_is_incoming(self):
        for record in self:
            record.is_incoming = record.payment_direction == 'incoming'
            record.is_outgoing = record.payment_direction == 'outgoing'

    @api.depends('charge_ids.amount')
    def _compute_total_charges(self):
        for record in self:
            record.total_charges = sum(record.charge_ids.mapped('amount'))

    @api.depends('odoo_payment_id', 'commission_payment_id')
    def _compute_has_odoo_payment(self):
        for record in self:
            record.has_odoo_payment = bool(record.odoo_payment_id)
            record.has_commission_payment = bool(record.commission_payment_id)

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

        # Parse payer info (can be in 'payer' object or at root level)
        payer = data.get('payer', {}) or {}
        payer_identification = payer.get('identification', {}) or {}

        # Parse fee details for charges (can be in fee_details or charges_details)
        fee_details = data.get('fee_details', []) or []
        charges_details = data.get('charges_details', []) or []

        # Extract payer_id (can be in payer.id or root payer_id)
        payer_id = str(payer.get('id', '')) if payer.get('id') else str(data.get('payer_id', ''))

        # Extract collector_id (can be at root or in collector.id)
        collector = data.get('collector', {}) or {}
        collector_id = str(data.get('collector_id', '')) if data.get('collector_id') else str(collector.get('id', ''))

        # Determine payment direction (incoming = we received, outgoing = we paid)
        account_user_id = str(account.ml_user_id or '')

        _logger.debug('Payment direction check - Payment ID: %s, collector_id: %s, payer_id: %s, account_user_id: %s',
                     mp_payment_id, collector_id, payer_id, account_user_id)

        if collector_id and collector_id == account_user_id:
            payment_direction = 'incoming'  # We are the collector (received money)
        elif payer_id and payer_id == account_user_id:
            payment_direction = 'outgoing'  # We are the payer (sent money)
        else:
            payment_direction = 'unknown'

        vals = {
            'account_id': account.id,
            'mp_payment_id': mp_payment_id,
            'mp_order_id': str(data.get('order', {}).get('id', '')) if data.get('order') else '',
            'mp_external_reference': data.get('external_reference', ''),
            'description': data.get('description', ''),
            'payment_direction': payment_direction,
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
            'payer_id': payer_id,
            'payer_email': payer.get('email', ''),
            'payer_name': f"{payer.get('first_name', '')} {payer.get('last_name', '')}".strip(),
            'payer_identification_type': payer_identification.get('type', ''),
            'payer_identification_number': payer_identification.get('number', ''),
            'collector_id': collector_id,
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
        self._sync_charges(payment, fee_details, charges_details)

        return payment, is_new

    def _sync_charges(self, payment, fee_details, charges_details=None):
        """
        Sincroniza los cargos/comisiones del pago.

        IMPORTANTE: La API de MercadoPago puede devolver la misma comision en
        fee_details Y charges_details. Para evitar duplicados, usamos SOLO UNA fuente:
        - Si charges_details tiene datos, usamos eso (mas detallado)
        - Si no, usamos fee_details
        """
        ChargeModel = self.env['mercadolibre.payment.charge']

        # Eliminar cargos existentes
        payment.charge_ids.unlink()

        # Usar charges_details si tiene datos (mas detallado), sino fee_details
        # NO procesar ambos para evitar duplicados
        if charges_details:
            # Process charges_details (formato detallado con mas info)
            for charge in charges_details:
                amounts = charge.get('amounts', {}) or {}
                accounts = charge.get('accounts', {}) or {}
                amount = amounts.get('original', 0.0)
                if amount > 0:  # Solo crear si hay monto
                    ChargeModel.create({
                        'payment_id': payment.id,
                        'charge_type': charge.get('name', '') or charge.get('type', ''),
                        'fee_payer': accounts.get('from', ''),
                        'amount': amount,
                    })
        elif fee_details:
            # Process fee_details (formato estandar, fallback)
            for fee in fee_details:
                amount = fee.get('amount', 0.0)
                if amount > 0:  # Solo crear si hay monto
                    ChargeModel.create({
                        'payment_id': payment.id,
                        'charge_type': fee.get('type', ''),
                        'fee_payer': fee.get('fee_payer', ''),
                        'amount': amount,
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
            # Crear datetime al inicio del dia en Mexico City
            dt_from = datetime.combine(date_from, datetime.min.time())
            dt_from_mx = MEXICO_TZ.localize(dt_from)
            begin_date = dt_from_mx.strftime('%Y-%m-%dT%H:%M:%S.000%z')
            params['begin_date'] = begin_date[:-2] + ':' + begin_date[-2:]

        if date_to:
            # Crear datetime al final del dia en Mexico City
            dt_to = datetime.combine(date_to, datetime.max.time().replace(microsecond=999000))
            dt_to_mx = MEXICO_TZ.localize(dt_to)
            end_date = dt_to_mx.strftime('%Y-%m-%dT%H:%M:%S.999%z')
            params['end_date'] = end_date[:-2] + ':' + end_date[-2:]

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

    # =====================================================
    # METODOS PARA CREACION DE PAGOS ODOO
    # =====================================================

    def action_create_odoo_payment(self):
        """Accion manual para crear pago en Odoo desde la vista"""
        self.ensure_one()
        return self._create_odoo_payment_wizard()

    def _create_odoo_payment_wizard(self):
        """Abre wizard para crear pago manualmente"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Crear Pago Odoo'),
            'res_model': 'mercadolibre.payment.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ml_payment_id': self.id,
                'default_payment_direction': self.payment_direction,
                'default_amount': self.transaction_amount,
                'default_description': self.description,
            },
        }

    def _detect_vendor(self):
        """
        Detecta el proveedor conocido basandose en la descripcion del pago.
        Solo aplica para pagos de tipo egreso (outgoing).

        Returns:
            mercadolibre.known.vendor record o False
        """
        self.ensure_one()

        if self.payment_direction != 'outgoing':
            return False

        if not self.description:
            return False

        KnownVendor = self.env['mercadolibre.known.vendor']
        vendor = KnownVendor.find_vendor_by_description(self.description)

        if vendor:
            self.matched_vendor_id = vendor.id
            self.partner_id = vendor.partner_id.id
            _logger.info('Pago %s: Proveedor detectado: %s -> %s',
                        self.mp_payment_id, vendor.name, vendor.partner_id.name)

        return vendor

    def _create_odoo_payment(self, config):
        """
        Crea el pago en Odoo (account.payment) basandose en la configuracion.

        Args:
            config: mercadolibre.payment.sync.config record con la configuracion de journals y partners

        Returns:
            dict con resultados: {'payment': account.payment, 'commission_payment': account.payment or False}
        """
        self.ensure_one()

        result = {
            'payment': False,
            'commission_payment': False,
            'error': False,
        }

        # Validar que no tenga ya un pago creado
        if self.odoo_payment_id:
            _logger.info('Pago %s ya tiene pago Odoo: %s', self.mp_payment_id, self.odoo_payment_id.name)
            return result

        # Validar estado del pago ML
        if self.status != 'approved':
            self.write({
                'odoo_payment_state': 'skipped',
                'odoo_payment_error': f'Pago no aprobado (estado: {self.status})',
            })
            return result

        try:
            # Detectar proveedor para egresos
            if self.payment_direction == 'outgoing' and not self.matched_vendor_id:
                self._detect_vendor()

            # Determinar tipo de pago y journal
            if self.payment_direction == 'incoming':
                payment_type = 'inbound'
                partner_type = 'customer'
                journal = config.incoming_journal_id
                partner = self.partner_id or config.default_customer_id

                if not journal:
                    raise ValidationError(_('No hay diario de ingresos configurado'))
                if not partner:
                    raise ValidationError(_('No hay cliente configurado para pagos entrantes'))

            elif self.payment_direction == 'outgoing':
                payment_type = 'outbound'
                partner_type = 'supplier'
                journal = config.outgoing_journal_id

                # Usar el partner del proveedor detectado o el default
                if self.matched_vendor_id:
                    partner = self.matched_vendor_id.partner_id
                else:
                    partner = self.partner_id or config.default_vendor_id

                if not journal:
                    raise ValidationError(_('No hay diario de egresos configurado'))
                if not partner:
                    raise ValidationError(_('No hay proveedor configurado para pagos salientes'))
            else:
                self.write({
                    'odoo_payment_state': 'skipped',
                    'odoo_payment_error': 'Direccion de pago desconocida',
                })
                return result

            # Determinar fecha del pago
            payment_date = self.date_approved or self.date_created or fields.Datetime.now()
            if isinstance(payment_date, datetime):
                payment_date = payment_date.date()

            # Crear el pago principal usando el metodo extendido
            payment_vals = {
                'payment_type': payment_type,
                'partner_type': partner_type,
                'partner_id': partner.id,
                'amount': abs(self.transaction_amount),
                'currency_id': self.currency_id.id or config.company_id.currency_id.id,
                'journal_id': journal.id,
                'date': payment_date,
            }

            # Usar metodo extendido que construye el ref con formato correcto
            # [Orden Venta] - [pack_id o order_id] - [payment_id]
            payment = self.env['account.payment'].create_from_ml_payment(self, payment_vals)
            result['payment'] = payment

            _logger.info('Pago Odoo creado: %s (ref: %s) para ML pago %s',
                        payment.name, payment.ref, self.mp_payment_id)

            # Confirmar pago automaticamente si esta configurado
            if config.auto_confirm_payment:
                try:
                    payment.action_post()
                    _logger.info('Pago %s confirmado automaticamente', payment.name)
                except Exception as e:
                    _logger.warning('Error al confirmar pago %s: %s', payment.name, str(e))
                    # No lanzar excepcion, el pago ya fue creado

            # Crear pago de comision si corresponde
            commission_payment = False
            if config.create_commission_payments and self.total_charges > 0:
                commission_payment = self._create_commission_payment(config, payment_date)
                result['commission_payment'] = commission_payment

                # Confirmar comision automaticamente si esta configurado
                if commission_payment and config.auto_confirm_payment:
                    try:
                        commission_payment.action_post()
                        _logger.info('Comision %s confirmada automaticamente', commission_payment.name)
                    except Exception as e:
                        _logger.warning('Error al confirmar comision %s: %s', commission_payment.name, str(e))

            # Actualizar el registro ML payment
            update_vals = {
                'odoo_payment_id': payment.id,
                'odoo_payment_state': 'created',
                'odoo_payment_error': False,
                'partner_id': partner.id,
            }
            if commission_payment:
                update_vals['commission_payment_id'] = commission_payment.id

            self.write(update_vals)

        except Exception as e:
            error_msg = str(e)
            _logger.error('Error creando pago Odoo para %s: %s', self.mp_payment_id, error_msg)
            self.write({
                'odoo_payment_state': 'error',
                'odoo_payment_error': error_msg,
            })
            result['error'] = error_msg

        return result

    def _create_commission_payment(self, config, payment_date):
        """
        Crea el pago de comision como pago separado.

        Args:
            config: mercadolibre.payment.sync.config con configuracion
            payment_date: fecha del pago

        Returns:
            account.payment record
        """
        self.ensure_one()

        # Proteccion contra duplicados: verificar si ya existe comision
        if self.commission_payment_id:
            _logger.info('Comision ya existe para pago %s: %s',
                        self.mp_payment_id, self.commission_payment_id.name)
            return self.commission_payment_id

        if not config.commission_journal_id:
            _logger.warning('No hay diario de comisiones configurado')
            return False

        if not config.commission_partner_id:
            _logger.warning('No hay partner de comisiones configurado')
            return False

        commission_vals = {
            'payment_type': 'outbound',  # Siempre es egreso (pagamos comision)
            'partner_type': 'supplier',
            'partner_id': config.commission_partner_id.id,
            'amount': abs(self.total_charges),
            'currency_id': self.currency_id.id or config.company_id.currency_id.id,
            'journal_id': config.commission_journal_id.id,
            'date': payment_date,
            'ref': f'ML-COM-{self.mp_payment_id}',
        }

        commission_payment = self.env['account.payment'].create(commission_vals)
        _logger.info('Pago comision creado: %s para ML pago %s', commission_payment.name, self.mp_payment_id)

        return commission_payment

    def action_view_odoo_payment(self):
        """Abre el pago de Odoo asociado"""
        self.ensure_one()
        if not self.odoo_payment_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pago Odoo'),
            'res_model': 'account.payment',
            'res_id': self.odoo_payment_id.id,
            'view_mode': 'form',
        }

    def action_view_commission_payment(self):
        """Abre el pago de comision asociado"""
        self.ensure_one()
        if not self.commission_payment_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pago Comision'),
            'res_model': 'account.payment',
            'res_id': self.commission_payment_id.id,
            'view_mode': 'form',
        }

    def action_retry_odoo_payment(self):
        """Reintenta la creacion del pago Odoo"""
        self.ensure_one()
        self.write({
            'odoo_payment_state': 'pending',
            'odoo_payment_error': False,
        })
        return True
