# -*- coding: utf-8 -*-

import json
import logging
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MercadoliBillingPeriod(models.Model):
    _name = 'mercadolibre.billing.period'
    _description = 'Periodo de Facturación MercadoLibre/MercadoPago'
    _order = 'period_key desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML/MP',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='account_id.company_id',
        store=True,
        readonly=True
    )
    period_key = fields.Date(
        string='Period Key',
        required=True,
        help='Primer día del mes del periodo (ej: 2025-01-01)'
    )
    billing_group = fields.Selection([
        ('ML', 'MercadoLibre'),
        ('MP', 'MercadoPago')
    ], string='Grupo', required=True, default='ML', tracking=True,
       help='ML para MercadoLibre, MP para MercadoPago')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('syncing', 'Sincronizando'),
        ('synced', 'Sincronizado'),
        ('processed', 'Procesado'),
        ('error', 'Error')
    ], string='Estado', default='draft', required=True, tracking=True)

    # Relaciones
    detail_ids = fields.One2many(
        'mercadolibre.billing.detail',
        'period_id',
        string='Detalles de Facturación'
    )
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'ml_billing_period_id',
        string='Órdenes de Compra'
    )

    # Contadores
    synced_count = fields.Integer(
        string='Detalles Sincronizados',
        compute='_compute_counts',
        store=True
    )
    bill_count = fields.Integer(
        string='Facturas',
        compute='_compute_counts',
        store=True
    )
    credit_note_count = fields.Integer(
        string='Notas de Crédito',
        compute='_compute_counts',
        store=True
    )
    purchase_order_count = fields.Integer(
        string='Órdenes de Compra',
        compute='_compute_counts',
        store=True
    )

    # Totales
    total_charges = fields.Monetary(
        string='Total Cargos',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    total_credit_notes = fields.Monetary(
        string='Total Notas de Crédito',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    net_amount = fields.Monetary(
        string='Monto Neto',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Total Cargos - Total Notas de Crédito'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )

    # Metadata
    sync_date = fields.Datetime(
        string='Fecha de Sincronización',
        readonly=True
    )
    last_offset = fields.Integer(
        string='Último Offset',
        default=0,
        help='Usado para paginación durante la sincronización'
    )
    sync_log = fields.Text(
        string='Log de Sincronización',
        readonly=True
    )
    error_message = fields.Text(
        string='Mensaje de Error',
        readonly=True
    )
    notes = fields.Text(
        string='Notas'
    )

    _sql_constraints = [
        ('period_key_account_group_uniq',
         'unique(period_key, account_id, billing_group)',
         'Ya existe un periodo con esta fecha, cuenta y grupo.')
    ]

    @api.depends('period_key', 'billing_group')
    def _compute_name(self):
        for record in self:
            if record.period_key:
                month_name = record.period_key.strftime('%B %Y')
                group_name = dict(record._fields['billing_group'].selection).get(record.billing_group, '')
                record.name = f'{group_name} - {month_name}'
            else:
                record.name = 'Nuevo Periodo'

    @api.depends('detail_ids', 'detail_ids.state', 'purchase_order_ids')
    def _compute_counts(self):
        for record in self:
            record.synced_count = len(record.detail_ids)
            record.bill_count = len(record.detail_ids.filtered(lambda d: not d.is_credit_note))
            record.credit_note_count = len(record.detail_ids.filtered(lambda d: d.is_credit_note))
            record.purchase_order_count = len(record.purchase_order_ids)

    @api.depends('detail_ids', 'detail_ids.detail_amount', 'detail_ids.is_credit_note')
    def _compute_totals(self):
        for record in self:
            bills = record.detail_ids.filtered(lambda d: not d.is_credit_note)
            credit_notes = record.detail_ids.filtered(lambda d: d.is_credit_note)

            record.total_charges = sum(bills.mapped('detail_amount'))
            record.total_credit_notes = sum(credit_notes.mapped('detail_amount'))
            record.net_amount = record.total_charges - record.total_credit_notes

    def action_sync_details(self):
        """
        Sincroniza los detalles de facturación desde la API de MercadoLibre/MercadoPago
        """
        self.ensure_one()

        if self.state == 'syncing':
            raise UserError(_('La sincronización ya está en curso.'))

        self.write({
            'state': 'syncing',
            'last_offset': 0,
            'sync_log': '',
            'error_message': ''
        })

        try:
            # Obtener token válido
            token = self.account_id.get_valid_token()

            offset = 0
            limit = 50
            display = None
            total_synced = 0
            log_lines = []

            log_lines.append(f'[INFO] Iniciando sincronización para periodo {self.period_key}')
            log_lines.append(f'[INFO] Grupo: {self.billing_group}')

            while display != 'complete':
                try:
                    results, display, total = self._sync_billing_details_batch(
                        token, offset, limit
                    )

                    synced_in_batch = len(results)
                    total_synced += synced_in_batch

                    log_lines.append(
                        f'[INFO] Offset {offset}: {synced_in_batch} detalles procesados'
                    )

                    offset += limit
                    self.last_offset = offset

                    # Commit parcial cada 5 lotes para evitar perder progreso
                    if offset % (limit * 5) == 0:
                        self.env.cr.commit()

                except Exception as e:
                    log_lines.append(f'[ERROR] Error en offset {offset}: {str(e)}')
                    _logger.error(f'Error sincronizando periodo {self.id} offset {offset}: {e}')
                    # Continuar con siguiente lote
                    offset += limit
                    continue

            log_lines.append(f'[SUCCESS] Sincronización completada: {total_synced} detalles')

            self.write({
                'state': 'synced',
                'sync_date': fields.Datetime.now(),
                'sync_log': '\n'.join(log_lines),
                'last_offset': 0
            })

            self.message_post(
                body=_(f'Sincronización completada: {total_synced} detalles procesados.')
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Exitosa'),
                    'message': _(f'{total_synced} detalles sincronizados correctamente.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Error fatal en sincronización periodo {self.id}: {e}', exc_info=True)

            self.write({
                'state': 'error',
                'error_message': error_msg,
                'sync_log': '\n'.join(log_lines) if log_lines else error_msg
            })

            # Crear log en mercadolibre.log
            self.env['mercadolibre.log'].sudo().create({
                'log_type': 'api_request',
                'level': 'error',
                'account_id': self.account_id.id,
                'message': f'Error sincronizando periodo {self.name}: {error_msg}',
            })

            raise UserError(_(
                'Error al sincronizar el periodo:\n%s'
            ) % error_msg)

    def _sync_billing_details_batch(self, token, offset, limit):
        """
        Sincroniza un lote de detalles de facturación

        Returns:
            tuple: (results, display, total)
        """
        self.ensure_one()

        # Construir URL según el grupo (ML o MP)
        period_key_str = self.period_key.strftime('%Y-%m-%d')
        url = f'https://api.mercadolibre.com/billing/integration/periods/key/{period_key_str}/group/{self.billing_group}/details'

        params = {
            'document_type': 'BILL',
            'limit': limit,
            'offset': offset
        }

        headers = {
            'Authorization': f'Bearer {token}'
        }

        # Registrar llamada API
        log_model = self.env['mercadolibre.log'].sudo()
        start_time = datetime.now()

        try:
            response = requests.get(url, headers=headers, params=params, timeout=60)
            duration = (datetime.now() - start_time).total_seconds()

            # Log de la llamada
            log_model.create({
                'log_type': 'api_request',
                'level': 'success' if response.status_code == 200 else 'error',
                'account_id': self.account_id.id,
                'message': f'Billing Sync: GET {url} - Status {response.status_code}',
                'request_url': url,
                'request_headers': json.dumps({'Authorization': 'Bearer ***'}),
                'request_body': json.dumps(params),
                'response_code': response.status_code,
                'response_body': response.text[:10000] if response.text else '',
                'duration': duration,
            })

            response.raise_for_status()
            data = response.json()

            results = data.get('results', [])
            display = data.get('display', 'complete')
            total = data.get('total', 0)

            # Procesar cada detalle
            Detail = self.env['mercadolibre.billing.detail']
            for result_data in results:
                try:
                    Detail.create_from_api_data(result_data, self)
                except Exception as e:
                    _logger.warning(f'Error procesando detalle: {e}')
                    continue

            return results, display, total

        except requests.exceptions.RequestException as e:
            duration = (datetime.now() - start_time).total_seconds()

            log_model.create({
                'log_type': 'api_request',
                'level': 'error',
                'account_id': self.account_id.id,
                'message': f'Error en billing sync: {str(e)}',
                'request_url': url,
                'request_headers': json.dumps({'Authorization': 'Bearer ***'}),
                'request_body': json.dumps(params),
                'response_code': getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                'response_body': e.response.text[:10000] if hasattr(e, 'response') and e.response else str(e),
                'duration': duration,
                'error_details': str(e),
            })

            raise

    def action_create_purchase_orders(self):
        """
        Crea órdenes de compra desde los detalles de facturación pendientes
        """
        self.ensure_one()

        details_pending = self.detail_ids.filtered(lambda d: d.state == 'draft')

        if not details_pending:
            raise UserError(_('No hay detalles pendientes para crear órdenes de compra.'))

        created_pos = self.env['purchase.order']
        errors = []

        for detail in details_pending:
            try:
                po = detail.action_create_purchase_order()
                if po:
                    created_pos |= po
            except Exception as e:
                errors.append(f'Detalle {detail.ml_detail_id}: {str(e)}')
                _logger.error(f'Error creando PO para detalle {detail.id}: {e}')

        if created_pos:
            self.state = 'processed'
            self.message_post(
                body=_(f'{len(created_pos)} órdenes de compra creadas.')
            )

        message = _(f'{len(created_pos)} órdenes de compra creadas.')
        if errors:
            message += '\n\nErrores:\n' + '\n'.join(errors)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Órdenes de Compra Creadas'),
                'message': message,
                'type': 'warning' if errors else 'success',
                'sticky': bool(errors),
            }
        }

    def action_view_purchase_orders(self):
        """Smart button para ver órdenes de compra"""
        self.ensure_one()

        action = self.env['ir.actions.actions']._for_xml_id(
            'purchase.purchase_rfq'
        )

        if len(self.purchase_order_ids) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.purchase_order_ids.id
        else:
            action['domain'] = [('id', 'in', self.purchase_order_ids.ids)]

        return action

    def action_view_details(self):
        """Smart button para ver detalles"""
        self.ensure_one()

        return {
            'name': _('Detalles de Facturación'),
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.billing.detail',
            'view_mode': 'tree,form',
            'domain': [('period_id', '=', self.id)],
            'context': {'default_period_id': self.id}
        }

    @api.model
    def _generate_period_keys(self, date_from, date_to):
        """
        Genera lista de period_keys entre dos fechas

        Args:
            date_from: fecha inicio
            date_to: fecha fin

        Returns:
            list: Lista de objetos date (primer día de cada mes)
        """
        period_keys = []
        current_date = date_from.replace(day=1)
        end_date = date_to.replace(day=1)

        while current_date <= end_date:
            period_keys.append(current_date)
            current_date = current_date + relativedelta(months=1)

        return period_keys
