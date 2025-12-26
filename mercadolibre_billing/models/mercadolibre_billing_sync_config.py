# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MercadoliBillingSyncConfig(models.Model):
    _name = 'mercadolibre.billing.sync.config'
    _description = 'Configuración de Sincronización de Facturación'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True
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
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True
    )

    # Configuración de Sincronización
    billing_group = fields.Selection([
        ('ML', 'MercadoLibre'),
        ('MP', 'MercadoPago'),
        ('both', 'Ambos')
    ], string='Grupo de Facturación', required=True, default='ML', tracking=True)

    auto_sync = fields.Boolean(
        string='Sincronización Automática',
        default=False,
        tracking=True,
        help='Activar sincronización automática vía cron'
    )
    sync_last_n_periods = fields.Integer(
        string='Períodos a Sincronizar',
        default=3,
        help='Número de meses hacia atrás a sincronizar'
    )
    document_types = fields.Selection([
        ('bill', 'Solo Facturas'),
        ('credit_note', 'Solo Notas de Crédito'),
        ('both', 'Ambos')
    ], string='Tipos de Documentos', default='both', required=True,
       help='Tipos de documentos a sincronizar')

    interval_number = fields.Integer(
        string='Intervalo',
        default=24,
        help='Número de intervalos entre sincronizaciones'
    )
    interval_type = fields.Selection([
        ('hours', 'Horas'),
        ('days', 'Días')
    ], string='Tipo de Intervalo', default='hours', required=True)

    last_sync_date = fields.Datetime(
        string='Última Sincronización',
        readonly=True
    )

    # Configuración de Purchase Orders
    auto_create_purchase_orders = fields.Boolean(
        string='Crear POs Automáticamente',
        default=False,
        tracking=True,
        help='Crear órdenes de compra automáticamente después de sincronizar'
    )
    auto_validate_purchase_orders = fields.Boolean(
        string='Confirmar POs Automáticamente',
        default=False,
        tracking=True,
        help='Confirmar órdenes de compra automáticamente al crearlas'
    )
    auto_create_invoices = fields.Boolean(
        string='Crear Facturas Automáticamente',
        default=False,
        tracking=True,
        help='Crear facturas de proveedor agrupadas por documento legal'
    )
    auto_post_invoices = fields.Boolean(
        string='Publicar Facturas Automáticamente',
        default=False,
        tracking=True,
        help='Publicar (validar) las facturas automáticamente al crearlas'
    )
    group_invoices_by_legal_document = fields.Boolean(
        string='Agrupar Facturas por Documento Legal',
        default=True,
        tracking=True,
        help='Crear una sola factura por cada número de documento legal de ML/MP'
    )
    skip_if_invoice_exists = fields.Boolean(
        string='Omitir si Factura Existe',
        default=True,
        tracking=True,
        help='No crear factura si ya existe una con la misma referencia'
    )
    attach_ml_pdf = fields.Boolean(
        string='Adjuntar PDF de MercadoLibre',
        default=False,
        tracking=True,
        help='Descargar y adjuntar el PDF de la factura legal de MercadoLibre'
    )

    # Configuración Contable
    vendor_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        domain=[('supplier_rank', '>', 0)],
        help='Proveedor para las órdenes de compra (si no se especifica, se creará automáticamente)'
    )
    commission_product_id = fields.Many2one(
        'product.product',
        string='Producto para Comisiones',
        domain=[('purchase_ok', '=', True)],
        help='Producto a usar en las líneas de las órdenes de compra'
    )
    purchase_tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto de Compra',
        domain=[('type_tax_use', '=', 'purchase')],
        help='Impuesto a aplicar en las líneas de las órdenes de compra (ej: IVA 16%)'
    )
    expense_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Gastos',
        domain=[('account_type', '=', 'expense')],
        help='Cuenta contable para los gastos de comisiones'
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario de Compras',
        domain=[('type', '=', 'purchase')],
        help='Diario para las facturas de proveedor'
    )

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Ya existe una configuración con este nombre en esta compañía.')
    ]

    def _should_sync_now(self):
        """
        Verifica si ha pasado suficiente tiempo desde la última sincronización
        según el intervalo configurado
        """
        self.ensure_one()

        if not self.last_sync_date:
            return True  # Nunca se ha sincronizado

        now = fields.Datetime.now()

        if self.interval_type == 'hours':
            next_sync = self.last_sync_date + relativedelta(hours=self.interval_number)
        else:  # days
            next_sync = self.last_sync_date + relativedelta(days=self.interval_number)

        return now >= next_sync

    @api.model
    def _cron_execute_all_syncs(self):
        """
        Método ejecutado por cron para procesar todas las configuraciones activas
        Respeta el intervalo configurado en cada config individual
        """
        configs = self.search([
            ('active', '=', True),
            ('auto_sync', '=', True)
        ])

        for config in configs:
            try:
                # Verificar si es tiempo de sincronizar según el intervalo de la config
                if not config._should_sync_now():
                    _logger.info(
                        f'Config {config.name}: Saltando sync, '
                        f'próxima en {config.interval_number} {config.interval_type} desde {config.last_sync_date}'
                    )
                    continue

                config._execute_sync()
            except Exception as e:
                _logger.error(f'Error en sync automático config {config.id}: {e}', exc_info=True)
                # Continuar con siguiente configuración
                continue

    def _execute_sync(self, force=False):
        """
        Ejecuta la sincronización para esta configuración

        Args:
            force: Si True, ignora la verificación de auto_sync (para sync manual)
        """
        self.ensure_one()

        if not force and (not self.active or not self.auto_sync):
            return

        _logger.info(f'Ejecutando sincronización automática para config {self.name}')

        # Generar periodos a sincronizar
        end_date = fields.Date.today()
        start_date = end_date - relativedelta(months=self.sync_last_n_periods - 1)

        period_keys = self.env['mercadolibre.billing.period']._generate_period_keys(
            start_date, end_date
        )

        # Determinar qué grupos sincronizar
        groups_to_sync = []
        if self.billing_group == 'both':
            groups_to_sync = ['ML', 'MP']
        else:
            groups_to_sync = [self.billing_group]

        periods_synced = 0
        errors = []

        for group in groups_to_sync:
            for period_key in period_keys:
                try:
                    # Buscar o crear periodo
                    period = self.env['mercadolibre.billing.period'].search([
                        ('period_key', '=', period_key),
                        ('account_id', '=', self.account_id.id),
                        ('billing_group', '=', group)
                    ], limit=1)

                    if not period:
                        period = self.env['mercadolibre.billing.period'].create({
                            'period_key': period_key,
                            'account_id': self.account_id.id,
                            'billing_group': group,
                        })

                    # Sincronizar solo si está en draft o error
                    if period.state in ('draft', 'error'):
                        # Pasar configuración de document_types al periodo
                        period.with_context(
                            sync_document_types=self.document_types,
                            sync_attach_pdf=self.attach_ml_pdf
                        ).action_sync_details()
                        periods_synced += 1

                        # Crear POs si está configurado
                        if self.auto_create_purchase_orders:
                            period.with_context(
                                force_vendor_id=self.vendor_id.id if self.vendor_id else False,
                                auto_validate_po=self.auto_validate_purchase_orders
                            ).action_create_purchase_orders()

                        # Crear facturas si está configurado
                        if self.auto_create_invoices:
                            period.action_create_grouped_invoices()

                        # Descargar PDFs si está configurado
                        if self.attach_ml_pdf and period.state == 'synced':
                            try:
                                period.action_download_pending_pdfs()
                            except Exception as pdf_error:
                                _logger.warning(f'Error descargando PDFs: {pdf_error}')

                except Exception as e:
                    error_msg = f'Periodo {period_key} ({group}): {str(e)}'
                    errors.append(error_msg)
                    _logger.error(f'Error sincronizando periodo: {error_msg}')
                    continue

        # Actualizar última fecha de sincronización
        self.last_sync_date = fields.Datetime.now()

        # Log de resultado
        if periods_synced > 0:
            self.message_post(
                body=_(f'Sincronización automática completada: {periods_synced} periodos procesados.')
            )

        if errors:
            self.message_post(
                body=_('Errores en sincronización:\n') + '\n'.join(errors)
            )

        _logger.info(
            f'Sync config {self.name} completado: '
            f'{periods_synced} periodos, {len(errors)} errores'
        )

    def action_sync_now(self):
        """
        Sincronización manual desde la configuración
        """
        self.ensure_one()

        try:
            # force=True para ejecutar aunque auto_sync esté desactivado
            self._execute_sync(force=True)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Completada'),
                    'message': _('La sincronización se ha ejecutado correctamente.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error en Sincronización'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    @api.onchange('commission_product_id')
    def _onchange_commission_product_id(self):
        """Actualizar cuenta de gastos según el producto"""
        if self.commission_product_id:
            # Intentar obtener la cuenta de gastos del producto
            account = self.commission_product_id.property_account_expense_id or \
                     self.commission_product_id.categ_id.property_account_expense_categ_id
            if account:
                self.expense_account_id = account

    @api.model
    def create(self, vals):
        """Al crear, establecer producto de comisión por defecto si no existe"""
        if 'commission_product_id' not in vals or not vals.get('commission_product_id'):
            default_product = self.env.ref(
                'mercadolibre_billing.product_ml_commission',
                raise_if_not_found=False
            )
            if default_product:
                vals['commission_product_id'] = default_product.id

        return super().create(vals)
