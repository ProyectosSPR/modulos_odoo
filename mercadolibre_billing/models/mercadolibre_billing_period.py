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
    invoice_group_ids = fields.One2many(
        'mercadolibre.billing.invoice',
        'period_id',
        string='Facturas ML'
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

    @api.depends('detail_ids', 'detail_ids.state', 'purchase_order_ids', 'invoice_group_ids', 'invoice_group_ids.detail_ids')
    def _compute_counts(self):
        for record in self:
            record.synced_count = len(record.detail_ids)
            # Contar facturas únicas (invoice_groups) en lugar de detalles
            # Una factura es nota de crédito si TODOS sus detalles son notas de crédito
            bills = 0
            credit_notes = 0
            for inv_group in record.invoice_group_ids:
                if inv_group.detail_ids:
                    # Es nota de crédito si todos los detalles son notas de crédito
                    all_credit_notes = all(d.is_credit_note for d in inv_group.detail_ids)
                    if all_credit_notes:
                        credit_notes += 1
                    else:
                        bills += 1
            record.bill_count = bills
            record.credit_note_count = credit_notes
            record.purchase_order_count = len(record.purchase_order_ids)

    @api.depends('detail_ids', 'detail_ids.detail_amount', 'detail_ids.is_credit_note')
    def _compute_totals(self):
        for record in self:
            bills = record.detail_ids.filtered(lambda d: not d.is_credit_note)
            credit_notes = record.detail_ids.filtered(lambda d: d.is_credit_note)

            record.total_charges = sum(bills.mapped('detail_amount'))
            record.total_credit_notes = sum(credit_notes.mapped('detail_amount'))
            record.net_amount = record.total_charges - record.total_credit_notes

    def _sync_document_type(self, token, document_type, log_lines):
        """
        Sincroniza un tipo específico de documento (BILL o CREDIT_NOTE)

        Args:
            token: Token de acceso válido
            document_type: 'BILL' o 'CREDIT_NOTE'
            log_lines: Lista para agregar logs

        Returns:
            int: Cantidad de detalles sincronizados
        """
        limit = 50
        offset = 0
        batch_number = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        base_delay = 1.0
        total_synced = 0

        doc_type_name = 'Facturas' if document_type == 'BILL' else 'Notas de Crédito'
        log_lines.append(f'[INFO] Sincronizando {doc_type_name}...')

        while True:
            try:
                batch_number += 1

                if batch_number > 1:
                    time.sleep(base_delay)

                results, display, total = self._sync_billing_details_batch(
                    token, offset, limit, document_type=document_type
                )

                consecutive_errors = 0
                synced_in_batch = len(results)
                total_synced += synced_in_batch

                log_lines.append(
                    f'[INFO] {doc_type_name} Lote {batch_number}: offset={offset}, '
                    f'{synced_in_batch} detalles (total API: {total}, display: {display})'
                )

                self.env.cr.commit()

                is_last_page = (
                    display == 'complete' or
                    not results or
                    synced_in_batch < limit or
                    (offset + limit) >= total
                )

                if is_last_page:
                    log_lines.append(f'[INFO] {doc_type_name} completado: {total_synced} detalles')
                    break

                offset += limit

            except requests.exceptions.HTTPError as e:
                self.env.cr.rollback()
                consecutive_errors += 1

                if e.response is not None and e.response.status_code == 429:
                    wait_time = min(2 ** consecutive_errors, 60)
                    log_lines.append(
                        f'[WARNING] Rate limit {doc_type_name} (lote {batch_number}). '
                        f'Esperando {wait_time}s... ({consecutive_errors}/{max_consecutive_errors})'
                    )
                    time.sleep(wait_time)

                    if consecutive_errors >= max_consecutive_errors:
                        log_lines.append(f'[ERROR] Máximo reintentos {doc_type_name}. Parcial: {total_synced}')
                        break
                    continue
                else:
                    log_lines.append(f'[ERROR] Error HTTP {doc_type_name} lote {batch_number}: {str(e)}')
                    if consecutive_errors >= max_consecutive_errors:
                        break
                    time.sleep(2)
                    continue

            except Exception as e:
                self.env.cr.rollback()
                consecutive_errors += 1
                log_lines.append(f'[ERROR] Error {doc_type_name} lote {batch_number}: {str(e)}')

                if consecutive_errors >= max_consecutive_errors:
                    break
                time.sleep(2)
                continue

        return total_synced

    def action_sync_details(self):
        """
        Sincroniza los detalles de facturación desde la API de MercadoLibre/MercadoPago
        Soporta sincronización de facturas, notas de crédito o ambos según configuración
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

            log_lines.append(f'[INFO] Iniciando sincronización para periodo {self.period_key}')
            log_lines.append(f'[INFO] Grupo: {self.billing_group}')

            # Obtener configuración de document_types del contexto
            # Por defecto sincroniza solo facturas (BILL) para compatibilidad
            sync_document_types = self.env.context.get('sync_document_types', 'bill')

            # Determinar qué tipos de documento sincronizar
            doc_types_to_sync = []
            if sync_document_types == 'bill':
                doc_types_to_sync = ['BILL']
            elif sync_document_types == 'credit_note':
                doc_types_to_sync = ['CREDIT_NOTE']
            elif sync_document_types == 'both':
                doc_types_to_sync = ['BILL', 'CREDIT_NOTE']
            else:
                doc_types_to_sync = ['BILL']  # Default

            log_lines.append(f'[INFO] Tipos de documento a sincronizar: {doc_types_to_sync}')

            # Sincronizar cada tipo de documento
            for doc_type in doc_types_to_sync:
                synced = self._sync_document_type(token, doc_type, log_lines)
                total_synced += synced

                # Pausa entre tipos de documento para evitar rate limit
                if len(doc_types_to_sync) > 1 and doc_type != doc_types_to_sync[-1]:
                    log_lines.append('[INFO] Pausa de 5s antes de siguiente tipo...')
                    time.sleep(5)

            log_lines.append(f'[SUCCESS] Sincronización de detalles completada: {total_synced} detalles')

            # Sincronizar file_ids de documentos PDF
            # Esperar antes de llamar para evitar rate limit
            log_lines.append(f'[INFO] Esperando 10s antes de sincronizar PDFs...')
            time.sleep(10)

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

    def _sync_billing_details_batch(self, token, offset, limit, document_type='BILL'):
        """
        Sincroniza un lote de detalles de facturación usando paginación con offset

        Args:
            token: Token de acceso válido
            offset: Posición desde donde empezar
            limit: Cantidad de registros por lote
            document_type: Tipo de documento ('BILL' o 'CREDIT_NOTE')

        Returns:
            tuple: (results, display, total)
            - display: 'complete' cuando es la última página
        """
        self.ensure_one()

        # Construir URL según el grupo (ML o MP)
        period_key_str = self.period_key.strftime('%Y-%m-%d')
        url = f'https://api.mercadolibre.com/billing/integration/periods/key/{period_key_str}/group/{self.billing_group}/details'

        params = {
            'document_type': document_type,
            'limit': limit,
            'offset': offset,
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
            total = data.get('total', 0)
            display = data.get('display')  # None si no viene, 'complete' en última página

            _logger.info(
                f'Lote recibido: offset={offset}, {len(results)} resultados, '
                f'total={total}, display={display}'
            )

            # Procesar cada detalle
            Detail = self.env['mercadolibre.billing.detail']
            for result_data in results:
                try:
                    with self.env.cr.savepoint():
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

        # Retry con backoff para manejar rate limiting
        max_retries = 3
        for attempt in range(max_retries):
            response = requests.get(url, headers=headers, params=params, timeout=60)

            if response.status_code == 200:
                break
            elif response.status_code == 429:
                wait_time = 2 ** (attempt + 1)  # 2, 4, 8 segundos
                _logger.warning(f'Rate limit 429 en documents, esperando {wait_time}s (intento {attempt + 1}/{max_retries})')
                time.sleep(wait_time)
            else:
                _logger.error(f'Error obteniendo documentos: {response.status_code} - {response.text[:500]}')
                raise UserError(_(
                    'Error al obtener documentos de MercadoLibre.\n'
                    'Status: %s'
                ) % response.status_code)
        else:
            # Si agotamos los reintentos
            raise UserError(_('Error al obtener documentos: Rate limit persistente (429)'))

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

    def action_download_pending_pdfs(self):
        """
        Descarga y adjunta PDFs pendientes para todas las facturas del periodo
        que tienen ml_pdf_file_id pero no tienen el PDF adjunto
        """
        self.ensure_one()

        Invoice = self.env['mercadolibre.billing.invoice']
        Attachment = self.env['ir.attachment']

        # Buscar facturas con file_id que tengan vendor_bill_id
        invoices_to_process = Invoice.search([
            ('period_id', '=', self.id),
            ('ml_pdf_file_id', '!=', False),
            ('vendor_bill_id', '!=', False),
        ])

        downloaded = 0
        errors = []

        for inv in invoices_to_process:
            # Verificar si ya tiene el PDF adjunto
            existing_attachment = Attachment.search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', inv.vendor_bill_id.id),
                ('name', 'ilike', f'%{inv.legal_document_number}%')
            ], limit=1)

            if existing_attachment:
                continue  # Ya tiene el PDF

            try:
                # Esperar para evitar rate limit
                time.sleep(0.5)
                inv._download_and_attach_pdf(inv.vendor_bill_id)
                downloaded += 1
                _logger.info(f'PDF descargado para {inv.legal_document_number}')
            except Exception as e:
                errors.append(f'{inv.legal_document_number}: {str(e)}')
                _logger.warning(f'Error descargando PDF para {inv.legal_document_number}: {e}')

        message = f'{downloaded} PDFs descargados.'
        if errors:
            message += f'\n\n{len(errors)} errores:\n' + '\n'.join(errors[:5])

        self.message_post(body=message)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Descarga de PDFs'),
                'message': message,
                'type': 'warning' if errors else 'success',
                'sticky': bool(errors),
            }
        }

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
