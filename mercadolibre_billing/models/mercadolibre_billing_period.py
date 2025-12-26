# -*- coding: utf-8 -*-

import json
import logging
import time
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
        self.env.cr.commit()

        log_lines = []
        total_synced = 0

        try:
            # Obtener token válido
            token = self.account_id.get_valid_token()

            limit = 50
            last_id = None  # Para paginación basada en cursor
            batch_number = 0
            consecutive_errors = 0
            max_consecutive_errors = 5  # Máximo de errores consecutivos antes de abortar
            base_delay = 0.5  # Delay base entre requests (segundos)

            log_lines.append(f'[INFO] Iniciando sincronización para periodo {self.period_key}')
            log_lines.append(f'[INFO] Grupo: {self.billing_group}')

            while True:
                try:
                    batch_number += 1

                    # Delay entre requests para evitar rate limiting
                    if batch_number > 1:
                        time.sleep(base_delay)

                    results, new_last_id, total = self._sync_billing_details_batch(
                        token, limit, last_id
                    )

                    # Reset contador de errores consecutivos en éxito
                    consecutive_errors = 0

                    synced_in_batch = len(results)
                    total_synced += synced_in_batch

                    log_lines.append(
                        f'[INFO] Lote {batch_number}: {synced_in_batch} detalles procesados (total API: {total}, last_id: {new_last_id})'
                    )

                    # Commit después de cada lote exitoso
                    self.env.cr.commit()

                    # Condiciones para terminar la paginación:
                    # 1. No hay resultados
                    # 2. Menos resultados que el límite (última página)
                    # 3. No hay new_last_id (no más páginas)
                    if not results or synced_in_batch < limit or not new_last_id:
                        log_lines.append(f'[INFO] Paginación completada - Total sincronizado: {total_synced}')
                        break

                    # Actualizar last_id para siguiente página
                    last_id = new_last_id

                except requests.exceptions.HTTPError as e:
                    # Rollback en caso de error
                    self.env.cr.rollback()
                    consecutive_errors += 1

                    # Manejar rate limiting (429 Too Many Requests)
                    if e.response is not None and e.response.status_code == 429:
                        # Backoff exponencial: 2, 4, 8, 16, 32 segundos
                        wait_time = min(2 ** consecutive_errors, 60)
                        log_lines.append(
                            f'[WARNING] Rate limit alcanzado (lote {batch_number}). '
                            f'Esperando {wait_time}s... (intento {consecutive_errors}/{max_consecutive_errors})'
                        )
                        _logger.warning(
                            f'Rate limit 429 en periodo {self.id}, esperando {wait_time}s'
                        )
                        time.sleep(wait_time)

                        if consecutive_errors >= max_consecutive_errors:
                            log_lines.append(
                                f'[ERROR] Máximo de reintentos alcanzado. Sincronización parcial: {total_synced} detalles'
                            )
                            break
                        continue
                    else:
                        # Otro error HTTP
                        log_lines.append(f'[ERROR] Error HTTP en lote {batch_number}: {str(e)}')
                        _logger.error(f'Error HTTP sincronizando periodo {self.id} lote {batch_number}: {e}')

                        if consecutive_errors >= max_consecutive_errors:
                            break
                        if last_id:
                            time.sleep(2)  # Esperar antes de reintentar
                            continue
                        else:
                            break

                except Exception as e:
                    # Rollback en caso de error
                    self.env.cr.rollback()
                    consecutive_errors += 1

                    log_lines.append(f'[ERROR] Error en lote {batch_number}: {str(e)}')
                    _logger.error(f'Error sincronizando periodo {self.id} lote {batch_number}: {e}')

                    if consecutive_errors >= max_consecutive_errors:
                        log_lines.append(f'[ERROR] Máximo de errores alcanzado. Abortando.')
                        break

                    # Si hay error, intentar continuar si tenemos last_id
                    if last_id:
                        time.sleep(2)  # Esperar antes de reintentar
                        continue
                    else:
                        break

            log_lines.append(f'[SUCCESS] Sincronización de detalles completada: {total_synced} detalles')

            # Sincronizar file_ids de documentos PDF
            try:
                log_lines.append(f'[INFO] Sincronizando file_ids de PDFs...')
                pdf_count = self._sync_document_files(token)
                log_lines.append(f'[SUCCESS] {pdf_count} file_ids de PDF actualizados')
            except Exception as e:
                log_lines.append(f'[WARNING] Error sincronizando PDFs: {str(e)}')
                _logger.warning(f'Error sincronizando PDFs para periodo {self.id}: {e}')

            self.write({
                'state': 'synced',
                'sync_date': fields.Datetime.now(),
                'sync_log': '\n'.join(log_lines),
                'last_offset': 0
            })
            self.env.cr.commit()

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
            # Rollback en caso de error fatal
            self.env.cr.rollback()

            error_msg = str(e)
            _logger.error(f'Error fatal en sincronización periodo {self.id}: {e}', exc_info=True)

            try:
                self.write({
                    'state': 'error',
                    'error_message': error_msg,
                    'sync_log': '\n'.join(log_lines) if log_lines else error_msg
                })
                self.env.cr.commit()

                # Crear log en mercadolibre.log
                self.env['mercadolibre.log'].sudo().create({
                    'log_type': 'api_request',
                    'level': 'error',
                    'account_id': self.account_id.id,
                    'message': f'Error sincronizando periodo {self.name}: {error_msg}',
                })
                self.env.cr.commit()
            except:
                pass

            raise UserError(_(
                'Error al sincronizar el periodo:\n%s'
            ) % error_msg)

    def _sync_billing_details_batch(self, token, limit, last_id=None):
        """
        Sincroniza un lote de detalles de facturación usando paginación basada en cursor (last_id)

        Args:
            token: Token de acceso válido
            limit: Cantidad de registros por lote
            last_id: ID del último registro del lote anterior (para paginación)

        Returns:
            tuple: (results, last_id, total)
        """
        self.ensure_one()

        # Construir URL según el grupo (ML o MP)
        period_key_str = self.period_key.strftime('%Y-%m-%d')
        url = f'https://api.mercadolibre.com/billing/integration/periods/key/{period_key_str}/group/{self.billing_group}/details'

        params = {
            'document_type': 'BILL',
            'limit': limit,
        }

        # Usar last_id para paginación basada en cursor
        if last_id:
            params['last_id'] = last_id

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
            total = data.get('total', 0)

            # Intentar obtener last_id del último elemento en results
            # ya que el last_id top-level puede ser estático
            new_last_id = None
            if results:
                last_result = results[-1]
                # El detail_id del último resultado es el cursor para la siguiente página
                charge_info = last_result.get('charge_info', {})
                new_last_id = charge_info.get('detail_id')

                # Log para debug: mostrar rango de IDs en este lote
                first_id = results[0].get('charge_info', {}).get('detail_id')
                _logger.info(
                    f'Lote recibido: {len(results)} resultados, total={total}, '
                    f'IDs: {first_id} -> {new_last_id}'
                )
            else:
                _logger.info(f'Lote recibido: 0 resultados, total={total}')

            # Procesar cada detalle
            Detail = self.env['mercadolibre.billing.detail']
            for result_data in results:
                try:
                    with self.env.cr.savepoint():
                        Detail.create_from_api_data(result_data, self)
                except Exception as e:
                    _logger.warning(f'Error procesando detalle: {e}')
                    continue

            return results, new_last_id, total

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

    def _sync_document_files(self, token):
        """
        Sincroniza los file_ids de PDF desde el endpoint /documents
        Este endpoint es diferente al de details y contiene los archivos PDF/XML

        Args:
            token: Token de acceso válido

        Returns:
            int: Cantidad de documentos actualizados con file_id
        """
        self.ensure_one()

        period_key_str = self.period_key.strftime('%Y-%m-%d')
        url = f'https://api.mercadolibre.com/billing/integration/periods/key/{period_key_str}/documents'

        params = {
            'group': self.billing_group,
        }

        headers = {
            'Authorization': f'Bearer {token}'
        }

        group_name = 'MercadoLibre' if self.billing_group == 'ML' else 'MercadoPago'
        _logger.info(f'Sincronizando documentos PDF de {group_name} desde: {url}?group={self.billing_group}')

        response = requests.get(url, headers=headers, params=params, timeout=60)

        if response.status_code != 200:
            _logger.error(f'Error obteniendo documentos: {response.status_code} - {response.text[:500]}')
            raise UserError(_(
                'Error al obtener documentos de MercadoLibre.\n'
                'Status: %s'
            ) % response.status_code)

        data = response.json()
        results = data.get('results', [])

        _logger.info(f'Documentos recibidos: {len(results)}')

        updated_count = 0
        Invoice = self.env['mercadolibre.billing.invoice']

        for doc in results:
            try:
                # Buscar el archivo PDF en la lista de files
                files = doc.get('files', [])
                pdf_file_id = None
                reference_number = None

                for f in files:
                    # El primer archivo suele ser el PDF
                    if f.get('file_id'):
                        pdf_file_id = str(f.get('file_id'))
                        reference_number = f.get('reference_number')
                        break

                if not pdf_file_id:
                    _logger.debug(f'Documento sin file_id: {doc.get("id")}')
                    continue

                # El reference_number es el número de factura legal (ej: A76257467)
                # También puede venir como associated_document_id para credit notes
                legal_doc_number = reference_number

                if not legal_doc_number:
                    _logger.debug(f'Documento sin reference_number: {doc.get("id")}')
                    continue

                # Buscar el invoice_group correspondiente
                invoice_group = Invoice.search([
                    ('period_id', '=', self.id),
                    ('legal_document_number', '=', legal_doc_number)
                ], limit=1)

                if invoice_group and not invoice_group.ml_pdf_file_id:
                    invoice_group.ml_pdf_file_id = pdf_file_id
                    updated_count += 1
                    _logger.info(f'PDF file_id actualizado para {legal_doc_number}: {pdf_file_id}')

            except Exception as e:
                _logger.warning(f'Error procesando documento {doc.get("id")}: {e}')
                continue

        return updated_count

    def action_create_purchase_orders(self):
        """
        Crea 1 orden de compra por cada detalle de facturación pendiente
        """
        self.ensure_one()

        details_pending = self.detail_ids.filtered(lambda d: d.state == 'draft')

        if not details_pending:
            raise UserError(_('No hay detalles pendientes para crear órdenes de compra.'))

        created_pos = self.env['purchase.order']
        errors = []

        for detail in details_pending:
            try:
                # Propagar contexto (ej: force_vendor_id) al detalle
                po = detail.with_context(self.env.context).action_create_purchase_order()
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

    def action_create_grouped_invoices(self):
        """
        Crea facturas de proveedor agrupadas por documento legal
        Este método procesa todos los invoice_groups del periodo
        """
        self.ensure_one()

        # Obtener configuración
        config = self.env['mercadolibre.billing.sync.config'].sudo().search([
            ('account_id', '=', self.account_id.id)
        ], limit=1)

        if not config:
            raise UserError(_(
                'No existe configuración de sincronización para esta cuenta.\n'
                'Por favor cree una configuración primero.'
            ))

        # Obtener todos los invoice_groups del periodo
        invoice_groups = self.env['mercadolibre.billing.invoice'].search([
            ('period_id', '=', self.id),
            ('state', '!=', 'done')
        ])

        if not invoice_groups:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Documentos'),
                    'message': _('No hay documentos legales pendientes de procesar en este periodo.'),
                    'type': 'warning',
                }
            }

        created_invoices = []
        skipped = []
        errors = []

        for invoice_group in invoice_groups:
            try:
                # Verificar que todos los detalles tengan PO
                details_without_po = invoice_group.detail_ids.filtered(
                    lambda d: not d.purchase_order_id
                )

                if details_without_po:
                    error_msg = _(
                        'Documento %s: Faltan %d órdenes de compra'
                    ) % (invoice_group.legal_document_number, len(details_without_po))
                    errors.append(error_msg)
                    _logger.warning(error_msg)
                    continue

                # Validar que todas las POs estén confirmadas
                purchase_orders = invoice_group.detail_ids.mapped('purchase_order_id')
                draft_pos = purchase_orders.filtered(
                    lambda po: po.state in ('draft', 'sent', 'to approve')
                )

                if draft_pos:
                    error_msg = _(
                        'Documento %s: %d POs sin confirmar'
                    ) % (invoice_group.legal_document_number, len(draft_pos))
                    errors.append(error_msg)
                    _logger.warning(error_msg)
                    continue

                # Verificar si ya existe factura
                if config.skip_if_invoice_exists:
                    existing = self.env['account.move'].search([
                        ('ref', '=', invoice_group.legal_document_number),
                        ('move_type', '=', 'in_invoice'),
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)

                    if existing:
                        invoice_group.write({
                            'vendor_bill_id': existing.id,
                            'state': 'done'
                        })
                        skipped.append(invoice_group.legal_document_number)
                        continue

                # Crear factura agrupada
                invoice = invoice_group.action_create_grouped_invoice()
                created_invoices.append(invoice)

            except Exception as e:
                error_msg = f'Documento {invoice_group.legal_document_number}: {str(e)}'
                errors.append(error_msg)
                _logger.error(f'Error creando factura: {error_msg}', exc_info=True)
                continue

        # Preparar mensaje de resultado
        message_parts = []
        if created_invoices:
            message_parts.append(f'✓ {len(created_invoices)} facturas creadas')
        if skipped:
            message_parts.append(f'⊘ {len(skipped)} documentos omitidos (ya existen)')
        if errors:
            message_parts.append(f'✗ {len(errors)} errores')

        message = '\n'.join(message_parts)

        if errors:
            message += '\n\nErrores:\n' + '\n'.join(errors[:5])
            if len(errors) > 5:
                message += f'\n... y {len(errors) - 5} más'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Proceso de Facturación Completado'),
                'message': message,
                'type': 'danger' if (errors and not created_invoices) else 'warning' if errors else 'success',
                'sticky': bool(errors),
            }
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
