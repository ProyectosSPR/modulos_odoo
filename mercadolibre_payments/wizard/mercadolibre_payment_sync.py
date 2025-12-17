# -*- coding: utf-8 -*-

import json
import time
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MercadolibrePaymentSync(models.TransientModel):
    _name = 'mercadolibre.payment.sync'
    _description = 'Asistente de Sincronizacion de Pagos'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]"
    )
    date_from = fields.Date(
        string='Desde',
        default=lambda self: fields.Date.today() - timedelta(days=30)
    )
    date_to = fields.Date(
        string='Hasta',
        default=lambda self: fields.Date.today()
    )
    only_released = fields.Boolean(
        string='Solo Dinero Liberado',
        default=True,
        help='Sincronizar solo pagos con dinero ya liberado en MercadoPago'
    )
    only_approved = fields.Boolean(
        string='Solo Aprobados',
        default=True,
        help='Sincronizar solo pagos con estado aprobado'
    )
    limit = fields.Integer(
        string='Limite',
        default=100,
        help='Numero maximo de pagos a sincronizar'
    )

    # Results
    sync_count = fields.Integer(
        string='Pagos Sincronizados',
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
        """Ejecuta la sincronizacion de pagos"""
        self.ensure_one()

        if not self.account_id.has_valid_token:
            raise ValidationError(_('La cuenta no tiene un token valido.'))

        _logger.info('='*60)
        _logger.info('INICIANDO SINCRONIZACION DE PAGOS')
        _logger.info('='*60)
        _logger.info('Cuenta: %s', self.account_id.name)
        _logger.info('Periodo: %s a %s', self.date_from, self.date_to)
        _logger.info('Solo liberados: %s', self.only_released)
        _logger.info('Solo aprobados: %s', self.only_approved)
        _logger.info('Limite: %d', self.limit)

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append('       SINCRONIZACION DE PAGOS MERCADOPAGO')
        log_lines.append('=' * 50)
        log_lines.append('')
        log_lines.append(f'  Cuenta:          {self.account_id.name}')
        log_lines.append(f'  Periodo:         {self.date_from} a {self.date_to}')
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
            'sort': 'date_approved',
            'criteria': 'desc',
            'limit': self.limit,
        }

        if self.date_from:
            params['begin_date'] = f'{self.date_from}T00:00:00.000-00:00'
        if self.date_to:
            params['end_date'] = f'{self.date_to}T23:59:59.999-00:00'

        if self.only_approved:
            params['status'] = 'approved'

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

        log_lines.append('-' * 50)
        log_lines.append('  RESULTADOS DE BUSQUEDA')
        log_lines.append('-' * 50)
        log_lines.append(f'  Total en MercadoPago:  {total}')
        log_lines.append(f'  Obtenidos:             {len(results)}')
        log_lines.append('')
        log_lines.append('-' * 50)
        log_lines.append('  DETALLE DE PAGOS')
        log_lines.append('-' * 50)

        _logger.info('Total encontrados: %d', total)
        _logger.info('Resultados en pagina: %d', len(results))

        PaymentModel = self.env['mercadolibre.payment']
        sync_count = 0
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
                PaymentModel.create_from_mp_data(payment_data, self.account_id)
                sync_count += 1
                log_lines.append(f'  [OK]    #{mp_id}  ${amount:>12,.2f}  {status}')
                _logger.info('Sincronizado pago %s - $%.2f', mp_id, amount)

            except Exception as e:
                error_count += 1
                log_lines.append(f'  [ERROR] #{mp_id}  {str(e)}')
                _logger.error('Error procesando pago %s: %s', mp_id, str(e))

        log_lines.append('')
        log_lines.append('=' * 50)
        log_lines.append('  RESUMEN')
        log_lines.append('=' * 50)
        log_lines.append(f'  Sincronizados:           {sync_count}')
        log_lines.append(f'  Saltados (no liberados): {skipped_count}')
        log_lines.append(f'  Errores:                 {error_count}')
        log_lines.append('=' * 50)

        _logger.info('='*60)
        _logger.info('SINCRONIZACION COMPLETADA')
        _logger.info('Sincronizados: %d | Saltados: %d | Errores: %d',
                    sync_count, skipped_count, error_count)
        _logger.info('='*60)

        self.write({
            'state': 'done',
            'sync_count': sync_count,
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
