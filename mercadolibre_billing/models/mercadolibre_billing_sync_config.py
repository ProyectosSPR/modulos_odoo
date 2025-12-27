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

    # Configuración de Periodo
    sync_period_type = fields.Selection([
        ('current_month', 'Solo Mes Actual'),
        ('last_month', 'Solo Mes Anterior'),
        ('last_2_months', 'Últimos 2 Meses'),
        ('last_3_months', 'Últimos 3 Meses'),
        ('last_6_months', 'Últimos 6 Meses'),
        ('custom', 'Personalizado'),
    ], string='Periodo a Sincronizar', default='current_month', required=True,
       help='Define qué meses se sincronizarán')

    sync_mode = fields.Selection([
        ('smart', 'Inteligente (Recomendado)'),
        ('full', 'Completo (Re-descarga todo)'),
        ('pending_only', 'Solo Pendientes'),
    ], string='Modo de Sincronización', default='smart', required=True,
       help='Inteligente: Solo re-sincroniza mes actual y pendientes.\n'
            'Completo: Re-descarga todos los periodos del rango.\n'
            'Solo Pendientes: Solo sincroniza periodos nunca descargados.')

    skip_synced_periods = fields.Boolean(
        string='Omitir Meses Ya Sincronizados',
        default=True,
        help='Si está activo, no re-descarga meses anteriores que ya están sincronizados. '
             'El mes actual siempre se actualiza.'
    )

    sync_last_n_periods = fields.Integer(
        string='Cantidad de Meses',
        default=3,
        help='Número de meses hacia atrás (solo para periodo personalizado)'
    )

    # Campos computados para mostrar el rango de fechas
    period_from_date = fields.Date(
        string='Desde',
        compute='_compute_period_range',
        help='Primer día del periodo a sincronizar'
    )
    period_to_date = fields.Date(
        string='Hasta',
        compute='_compute_period_range',
        help='Último día del periodo a sincronizar'
    )
    sync_period_display = fields.Char(
        string='Rango de Periodos',
        compute='_compute_period_range',
        help='Descripción del rango de meses a sincronizar'
    )

    document_types = fields.Selection([
        ('bill', 'Solo Facturas'),
        ('credit_note', 'Solo Notas de Crédito'),
        ('both', 'Ambos')
    ], string='Tipos de Documentos', default='both', required=True,
       help='Tipos de documentos a sincronizar')

    @api.depends('sync_period_type', 'sync_last_n_periods')
    def _compute_period_range(self):
        """Calcula el rango de fechas según el tipo de periodo seleccionado"""
        for record in self:
            today = fields.Date.today()
            current_month_start = today.replace(day=1)

            if record.sync_period_type == 'current_month':
                period_from = current_month_start
                period_to = today
                months_back = 1
            elif record.sync_period_type == 'last_month':
                period_from = (current_month_start - relativedelta(months=1))
                period_to = current_month_start - relativedelta(days=1)
                months_back = 1
            elif record.sync_period_type == 'last_2_months':
                period_from = (current_month_start - relativedelta(months=1))
                period_to = today
                months_back = 2
            elif record.sync_period_type == 'last_3_months':
                period_from = (current_month_start - relativedelta(months=2))
                period_to = today
                months_back = 3
            elif record.sync_period_type == 'last_6_months':
                period_from = (current_month_start - relativedelta(months=5))
                period_to = today
                months_back = 6
            else:  # custom
                months_back = record.sync_last_n_periods or 3
                period_from = (current_month_start - relativedelta(months=months_back - 1))
                period_to = today

            record.period_from_date = period_from
            record.period_to_date = period_to

            # Generar texto descriptivo
            from_month = period_from.strftime('%B %Y')
            to_month = period_to.strftime('%B %Y')
            if from_month == to_month:
                record.sync_period_display = f'{from_month}'
            else:
                record.sync_period_display = f'{from_month} → {to_month}'

    interval_number = fields.Integer(
        string='Intervalo',
        default=60,
        help='Número de intervalos entre sincronizaciones automáticas'
    )
    interval_type = fields.Selection([
        ('minutes', 'Minutos'),
        ('hours', 'Horas'),
        ('days', 'Días')
    ], string='Tipo de Intervalo', default='minutes', required=True)

    # Estado y programación
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('paused', 'Pausado'),
    ], string='Estado', default='draft', readonly=True, tracking=True)

    cron_id = fields.Many2one(
        'ir.cron',
        string='Tarea Programada',
        readonly=True,
        ondelete='set null'
    )

    next_run = fields.Datetime(
        string='Próxima Ejecución',
        help='Fecha y hora de la próxima ejecución programada'
    )
    last_sync_date = fields.Datetime(
        string='Última Sincronización',
        readonly=True
    )

    # Estadísticas
    total_syncs = fields.Integer(
        string='Total Ejecuciones',
        readonly=True,
        default=0
    )
    last_sync_count = fields.Integer(
        string='Últimos Sincronizados',
        readonly=True,
        help='Cantidad de detalles sincronizados en la última ejecución'
    )
    last_sync_errors = fields.Integer(
        string='Últimos Errores',
        readonly=True
    )
    total_details_synced = fields.Integer(
        string='Total Detalles Sincronizados',
        readonly=True,
        default=0
    )
    last_sync_log = fields.Text(
        string='Log Última Ejecución',
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
        string='Proveedor por Defecto',
        domain=[('supplier_rank', '>', 0)],
        help='Proveedor para las órdenes de compra (ej: Deremate.com de Mexico). '
             'Si no se especifica, se creará automáticamente según el billing_group.'
    )
    commission_product_id = fields.Many2one(
        'product.product',
        string='Producto por Defecto (Fallback)',
        domain=[('purchase_ok', '=', True)],
        help='Producto a usar SOLO cuando no existe mapeo de cargos para el tipo de cargo. '
             'La prioridad es: 1) Mapeo de Cargos, 2) Este producto, 3) Producto del módulo. '
             'Se recomienda configurar el Mapeo de Cargos en su lugar.'
    )
    purchase_tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto de Compra',
        domain=[('type_tax_use', '=', 'purchase')],
        help='Impuesto a aplicar en las líneas de las órdenes de compra (ej: IVA 21%). '
             'Este impuesto se aplicará a todas las líneas de PO.'
    )
    expense_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Gastos',
        domain=[('account_type', '=', 'expense')],
        help='Cuenta contable para los gastos de comisiones en las facturas de proveedor. '
             'Si no se especifica, se usará la cuenta del producto.'
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario de Compras',
        domain=[('type', '=', 'purchase')],
        help='Diario para las facturas de proveedor. Si no se especifica, se usará el diario por defecto.'
    )

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Ya existe una configuración con este nombre en esta compañía.')
    ]

    # =====================================================
    # MÉTODOS DE CONTROL DE ESTADO
    # =====================================================

    def write(self, vals):
        result = super().write(vals)
        # Si se desactiva, pausar el cron
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
        """Activa la sincronización automática"""
        for record in self:
            if not record.account_id:
                raise ValidationError(_('Debe seleccionar una cuenta ML/MP.'))

            # Crear o actualizar cron individual
            record._create_or_update_cron()

            # Establecer próxima ejecución si no existe
            if not record.next_run:
                record.next_run = fields.Datetime.now()

            record.state = 'active'
            record.message_post(body=_('Sincronización automática activada.'))

    def action_pause(self):
        """Pausa la sincronización automática"""
        for record in self:
            if record.cron_id:
                record.cron_id.active = False
            record.state = 'paused'
            record.message_post(body=_('Sincronización automática pausada.'))

    def action_resume(self):
        """Reanuda la sincronización automática"""
        for record in self:
            if record.cron_id:
                record.cron_id.active = True
            else:
                record._create_or_update_cron()

            record.state = 'active'
            record.message_post(body=_('Sincronización automática reanudada.'))

    def _create_or_update_cron(self):
        """Crea o actualiza el cron job individual para esta configuración"""
        self.ensure_one()

        _logger.info(f'[BILLING SYNC] Creando/actualizando cron para config {self.name}')

        cron_vals = {
            'name': f'Billing Sync: {self.name}',
            'model_id': self.env['ir.model']._get('mercadolibre.billing.sync.config').id,
            'state': 'code',
            'code': f'model.browse({self.id})._execute_sync()',
            'interval_number': self.interval_number,
            'interval_type': self.interval_type,
            'numbercall': -1,  # Infinito
            'active': True,
            'doall': False,
            'priority': 10,
        }

        if self.next_run:
            cron_vals['nextcall'] = self.next_run
        else:
            cron_vals['nextcall'] = fields.Datetime.now()

        _logger.info(f'[BILLING SYNC] Cron vals: interval={self.interval_number} {self.interval_type}, nextcall={cron_vals["nextcall"]}')

        if self.cron_id:
            self.cron_id.write(cron_vals)
            _logger.info(f'[BILLING SYNC] Cron actualizado: ID={self.cron_id.id}')
        else:
            cron = self.env['ir.cron'].sudo().create(cron_vals)
            self.cron_id = cron
            _logger.info(f'[BILLING SYNC] Nuevo cron creado: ID={cron.id}')

    def _calculate_next_run(self):
        """Calcula la próxima ejecución basada en el intervalo"""
        now = fields.Datetime.now()
        if self.interval_type == 'minutes':
            return now + relativedelta(minutes=self.interval_number)
        elif self.interval_type == 'hours':
            return now + relativedelta(hours=self.interval_number)
        else:  # days
            return now + relativedelta(days=self.interval_number)

    # =====================================================
    # MÉTODO PRINCIPAL DE SINCRONIZACIÓN
    # =====================================================

    def _execute_sync(self, force=False, force_current_month=False):
        """
        Ejecuta la sincronización para esta configuración

        Args:
            force: Si True, ignora la verificación de estado (para sync manual)
            force_current_month: Si True, solo sincroniza el mes actual forzando re-descarga
        """
        self.ensure_one()

        _logger.info('=' * 60)
        _logger.info(f'[BILLING SYNC] INICIO - Config: {self.name} (ID: {self.id})')
        _logger.info(f'[BILLING SYNC] force={force}, force_current_month={force_current_month}')
        _logger.info(f'[BILLING SYNC] active={self.active}, state={self.state}')
        _logger.info('=' * 60)

        if not force and (not self.active or self.state != 'active'):
            _logger.warning(f'[BILLING SYNC] SKIP - Config no activa. active={self.active}, state={self.state}')
            return

        _logger.info(f'[BILLING SYNC] Ejecutando sincronización automática para config {self.name}')

        today = fields.Date.today()
        current_month_start = today.replace(day=1)

        # Si force_current_month, solo sincronizar el mes actual
        if force_current_month:
            start_date = current_month_start
            end_date = today
            _logger.info(f'Forzando sync solo del mes actual: {start_date} - {end_date}')
        else:
            # Usar fechas calculadas del campo computado
            start_date = self.period_from_date
            end_date = self.period_to_date

        _logger.info(f'[BILLING SYNC] Periodo a sincronizar: {start_date} - {end_date} ({self.sync_period_display})')

        period_keys = self.env['mercadolibre.billing.period']._generate_period_keys(
            start_date, end_date
        )
        _logger.info(f'[BILLING SYNC] Period keys generados: {period_keys}')

        # Determinar qué grupos sincronizar
        groups_to_sync = []
        if self.billing_group == 'both':
            groups_to_sync = ['ML', 'MP']
        else:
            groups_to_sync = [self.billing_group]

        _logger.info(f'[BILLING SYNC] Grupos a sincronizar: {groups_to_sync}')

        periods_synced = 0
        periods_skipped = 0
        errors = []
        # current_month_key ya está definido arriba como current_month_start

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

                    # Determinar si es el mes actual
                    is_current_month = (period_key == current_month_start)

                    # Determinar si sincronizar según el modo
                    should_sync = False
                    skip_reason = None

                    if force_current_month and is_current_month:
                        # Forzar re-sync del mes actual
                        should_sync = True
                    elif self.sync_mode == 'full':
                        # Modo completo: siempre sincroniza todo
                        should_sync = True
                    elif self.sync_mode == 'pending_only':
                        # Solo pendientes: solo periodos no sincronizados
                        should_sync = period.state in ('draft', 'error')
                        if not should_sync:
                            skip_reason = 'ya sincronizado'
                    else:  # smart (inteligente)
                        # Inteligente: mes actual siempre, otros solo si pendientes
                        if is_current_month:
                            should_sync = True  # Siempre actualizar mes actual
                        elif self.skip_synced_periods and period.state == 'synced':
                            should_sync = False
                            skip_reason = 'mes anterior ya sincronizado'
                        else:
                            should_sync = period.state in ('draft', 'error')
                            if not should_sync:
                                skip_reason = 'ya sincronizado'

                    if not should_sync:
                        periods_skipped += 1
                        _logger.info(f'Omitiendo {period_key} ({group}): {skip_reason}')
                        continue

                    # Resetear estado si es necesario para re-sincronizar
                    if period.state == 'synced' and (
                        self.sync_mode == 'full' or
                        is_current_month or
                        (force_current_month and is_current_month)
                    ):
                        period.write({'state': 'draft'})

                    # Sincronizar
                    if period.state in ('draft', 'error'):
                        _logger.info(f'Sincronizando {period_key} ({group})...')
                        period.with_context(
                            sync_document_types=self.document_types,
                            sync_attach_pdf=self.attach_ml_pdf
                        ).action_sync_details()
                        periods_synced += 1

                        # Crear POs si está configurado (solo para facturas, NO notas de crédito)
                        _logger.info(f'[BILLING SYNC] auto_create_purchase_orders={self.auto_create_purchase_orders}')
                        if self.auto_create_purchase_orders:
                            try:
                                _logger.info(f'[BILLING SYNC] Creando POs para periodo {period_key}...')
                                period.with_context(
                                    force_vendor_id=self.vendor_id.id if self.vendor_id else False,
                                ).action_create_purchase_orders()
                                _logger.info(f'[BILLING SYNC] POs creadas exitosamente')
                            except Exception as po_error:
                                _logger.warning(f'[BILLING SYNC] Error creando POs: {po_error}', exc_info=True)

                        # Crear facturas/notas de crédito si está configurado
                        _logger.info(f'[BILLING SYNC] auto_create_invoices={self.auto_create_invoices}')
                        if self.auto_create_invoices:
                            try:
                                _logger.info(f'[BILLING SYNC] Creando facturas para periodo {period_key}...')
                                # Pasar el sync_config_id en contexto para que use esta configuración
                                result = period.with_context(
                                    sync_config_id=self.id
                                ).action_create_grouped_invoices()
                                _logger.info(f'[BILLING SYNC] Resultado creación facturas: {result}')
                            except Exception as inv_error:
                                _logger.warning(f'[BILLING SYNC] Error creando facturas: {inv_error}', exc_info=True)

                        # Descargar PDFs si está configurado
                        if self.attach_ml_pdf and period.state == 'synced':
                            try:
                                period.action_download_pending_pdfs()
                            except Exception as pdf_error:
                                _logger.warning(f'Error descargando PDFs: {pdf_error}')

                except Exception as e:
                    error_msg = f'Periodo {period_key} ({group}): {str(e)}'
                    errors.append(error_msg)
                    _logger.error(f'[BILLING SYNC] ERROR sincronizando periodo: {error_msg}', exc_info=True)
                    continue

        # Construir log
        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append(f'  SYNC: {self.name}')
        log_lines.append('=' * 50)
        log_lines.append(f'  Fecha ejecución: {fields.Datetime.now()}')
        log_lines.append(f'  Grupo: {self.billing_group}')
        log_lines.append(f'  Rango: {self.sync_period_display}')
        log_lines.append(f'  Desde: {start_date} | Hasta: {end_date}')
        log_lines.append('')
        log_lines.append(f'  Periodos sincronizados: {periods_synced}')
        log_lines.append(f'  Errores: {len(errors)}')
        if errors:
            log_lines.append('')
            log_lines.append('  ERRORES:')
            for err in errors:
                log_lines.append(f'    - {err}')
        log_lines.append('=' * 50)

        # Actualizar estadísticas
        update_vals = {
            'last_sync_date': fields.Datetime.now(),
            'next_run': self._calculate_next_run(),
            'total_syncs': self.total_syncs + 1,
            'last_sync_count': periods_synced,
            'last_sync_errors': len(errors),
            'last_sync_log': '\n'.join(log_lines),
        }

        # Actualizar cron con próxima ejecución
        if self.cron_id:
            self.cron_id.nextcall = update_vals['next_run']

        self.write(update_vals)

        # Log de resultado
        if periods_synced > 0:
            self.message_post(
                body=_(f'Sincronización completada: {periods_synced} periodos procesados.')
            )

        if errors:
            self.message_post(
                body=_('Errores en sincronización:\n') + '\n'.join(errors)
            )

        _logger.info('=' * 60)
        _logger.info(f'[BILLING SYNC] FIN - Config: {self.name}')
        _logger.info(f'[BILLING SYNC] Periodos sincronizados: {periods_synced}')
        _logger.info(f'[BILLING SYNC] Periodos omitidos: {periods_skipped}')
        _logger.info(f'[BILLING SYNC] Errores: {len(errors)}')
        _logger.info(f'[BILLING SYNC] Próxima ejecución: {update_vals.get("next_run")}')
        _logger.info('=' * 60)

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

    def action_force_current_month_sync(self):
        """
        Fuerza la re-sincronización del mes actual solamente.
        Útil cuando se quiere actualizar el mes actual sin afectar meses anteriores.
        """
        self.ensure_one()

        try:
            # Ejecutar sync solo del mes actual forzando re-descarga
            self._execute_sync(force=True, force_current_month=True)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Mes Actual Completado'),
                    'message': _('El mes actual ha sido re-sincronizado.'),
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
