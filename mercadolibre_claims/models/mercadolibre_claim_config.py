# -*- coding: utf-8 -*-

import json
import time
import logging
import requests
import pytz
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

MEXICO_TZ = pytz.timezone('America/Mexico_City')


class MercadolibreClaimConfig(models.Model):
    _name = 'mercadolibre.claim.config'
    _description = 'Configuracion de Reclamos MercadoLibre'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo para identificar esta configuracion'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]",
        help='Cuenta de MercadoLibre a monitorear'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # =====================================================
    # SINCRONIZACION
    # =====================================================
    sync_claims = fields.Boolean(
        string='Sincronizar Reclamos',
        default=True,
        help='Si esta activo, sincronizara reclamos automaticamente'
    )
    sync_interval_number = fields.Integer(
        string='Intervalo',
        default=1,
        required=True
    )
    sync_interval_type = fields.Selection([
        ('hours', 'Horas'),
        ('days', 'Dias'),
    ], string='Tipo Intervalo', default='hours', required=True)

    sync_status_filter = fields.Selection([
        ('all', 'Todos'),
        ('opened', 'Solo Abiertos'),
        ('closed', 'Solo Cerrados'),
    ], string='Filtrar por Estado', default='opened')

    sync_type_filter = fields.Selection([
        ('all', 'Todos los Tipos'),
        ('mediations', 'Solo Mediaciones'),
        ('returns', 'Solo Devoluciones'),
    ], string='Filtrar por Tipo', default='all')

    # =====================================================
    # ACCIONES AUTOMATICAS PARA PAGOS EN MEDIACION
    # =====================================================
    auto_process_mediation = fields.Boolean(
        string='Procesar Pagos en Mediacion',
        default=False,
        help='Ejecutar acciones automaticas cuando un pago entre en estado in_mediation'
    )

    mediation_action = fields.Selection([
        ('none', 'No hacer nada'),
        ('cancel_payment', 'Cancelar Pago Odoo'),
        ('create_cancelled', 'Crear Pago como Cancelado'),
        ('reverse_payment', 'Revertir Pago (Contraasiento)'),
        ('notify_only', 'Solo Notificar'),
    ], string='Accion para Mediacion', default='notify_only',
       help='''Accion a ejecutar cuando un pago entra en mediacion:
       - No hacer nada: Sin accion automatica
       - Cancelar Pago: Si existe pago Odoo, lo cancela
       - Crear Cancelado: Si no existe pago, crea uno en estado cancelado para registro
       - Revertir Pago: Crea asiento de reversion
       - Solo Notificar: Crea actividad para revision manual
       ''')

    # =====================================================
    # ACCIONES POR RESOLUCION
    # =====================================================
    resolution_buyer_action = fields.Selection([
        ('none', 'No hacer nada'),
        ('cancel_payment', 'Cancelar Pago'),
        ('create_refund', 'Crear Nota de Credito'),
        ('notify', 'Solo Notificar'),
    ], string='Resolucion a Favor Comprador', default='notify',
       help='Accion cuando el claim se resuelve a favor del comprador')

    resolution_seller_action = fields.Selection([
        ('none', 'No hacer nada'),
        ('confirm_payment', 'Confirmar Pago'),
        ('notify', 'Solo Notificar'),
    ], string='Resolucion a Favor Vendedor', default='notify',
       help='Accion cuando el claim se resuelve a favor del vendedor')

    # =====================================================
    # NOTIFICACIONES
    # =====================================================
    notify_new_claim = fields.Boolean(
        string='Notificar Nuevos Reclamos',
        default=True
    )
    notify_stage_change = fields.Boolean(
        string='Notificar Cambio de Etapa',
        default=True,
        help='Notificar cuando un reclamo pasa a mediacion/disputa'
    )
    notify_resolution = fields.Boolean(
        string='Notificar Resolucion',
        default=True
    )

    notify_user_ids = fields.Many2many(
        'res.users',
        'mercadolibre_claim_config_notify_users_rel',
        'config_id',
        'user_id',
        string='Usuarios a Notificar'
    )

    create_activity = fields.Boolean(
        string='Crear Actividad',
        default=True,
        help='Crear actividad pendiente cuando hay un nuevo reclamo o requiere accion'
    )
    activity_user_id = fields.Many2one(
        'res.users',
        string='Usuario para Actividades',
        help='Usuario al que se asignaran las actividades'
    )

    # =====================================================
    # DIARIOS PARA OPERACIONES CONTABLES
    # =====================================================
    reversal_journal_id = fields.Many2one(
        'account.journal',
        string='Diario para Reversiones',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help='Diario a usar para asientos de reversion'
    )

    default_customer_id = fields.Many2one(
        'res.partner',
        string='Cliente por Defecto',
        help='Cliente a usar cuando no se puede identificar al comprador'
    )

    # =====================================================
    # CRON Y ESTADO
    # =====================================================
    cron_id = fields.Many2one(
        'ir.cron',
        string='Tarea Programada',
        readonly=True,
        ondelete='set null'
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('paused', 'Pausado'),
    ], string='Estado', default='draft', readonly=True)

    # =====================================================
    # ESTADISTICAS
    # =====================================================
    last_sync = fields.Datetime(
        string='Ultima Sincronizacion',
        readonly=True
    )
    next_sync = fields.Datetime(
        string='Proxima Sincronizacion',
        readonly=True
    )
    last_sync_count = fields.Integer(
        string='Ultimos Sincronizados',
        readonly=True
    )
    last_sync_log = fields.Text(
        string='Log Ultima Sincronizacion',
        readonly=True
    )
    total_syncs = fields.Integer(
        string='Total Sincronizaciones',
        readonly=True,
        default=0
    )
    total_claims_synced = fields.Integer(
        string='Total Claims Sincronizados',
        readonly=True,
        default=0
    )

    # =====================================================
    # METODOS DE ESTADO
    # =====================================================

    def action_activate(self):
        """Activa la sincronizacion automatica"""
        for record in self:
            if not record.account_id.has_valid_token:
                raise ValidationError(_('La cuenta %s no tiene un token valido.') % record.account_id.name)

            record._create_or_update_cron()

            if not record.next_sync:
                record.next_sync = fields.Datetime.now()

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
            'name': f'Sync Claims ML: {self.name}',
            'model_id': self.env['ir.model']._get('mercadolibre.claim.config').id,
            'state': 'code',
            'code': f'model.browse({self.id})._execute_sync()',
            'interval_number': self.sync_interval_number,
            'interval_type': self.sync_interval_type,
            'numbercall': -1,
            'active': True,
            'doall': False,
        }

        if self.next_sync:
            cron_vals['nextcall'] = self.next_sync
        else:
            cron_vals['nextcall'] = fields.Datetime.now()

        if self.cron_id:
            self.cron_id.write(cron_vals)
        else:
            cron = self.env['ir.cron'].sudo().create(cron_vals)
            self.cron_id = cron

    # =====================================================
    # SINCRONIZACION
    # =====================================================

    def _execute_sync(self):
        """Ejecuta la sincronizacion de claims"""
        self.ensure_one()

        _logger.info('=' * 60)
        _logger.info('SYNC CLAIMS: Iniciando "%s"', self.name)
        _logger.info('=' * 60)

        if not self.account_id.has_valid_token:
            _logger.error('La cuenta %s no tiene token valido', self.account_id.name)
            self.write({
                'last_sync': fields.Datetime.now(),
                'last_sync_log': 'ERROR: La cuenta no tiene un token valido',
            })
            return False

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append(f'  SYNC CLAIMS: {self.name}')
        log_lines.append('=' * 50)

        now_mexico = datetime.now(MEXICO_TZ)
        log_lines.append(f'  Fecha (Mexico): {now_mexico.strftime("%d/%m/%Y %H:%M:%S")}')
        log_lines.append(f'  Cuenta: {self.account_id.name}')
        log_lines.append('')

        access_token = self.account_id.get_valid_token_with_retry(max_retries=2)
        if not access_token:
            log_lines.append('ERROR: No se pudo obtener token valido')
            self.write({
                'last_sync': fields.Datetime.now(),
                'last_sync_log': '\n'.join(log_lines),
            })
            return False

        # Construir parametros de busqueda
        params = {
            'limit': 50,
        }

        if self.sync_status_filter and self.sync_status_filter != 'all':
            params['status'] = self.sync_status_filter

        if self.sync_type_filter and self.sync_type_filter != 'all':
            params['type'] = self.sync_type_filter

        url = 'https://api.mercadolibre.com/post-purchase/v1/claims/search'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        LogModel = self.env['mercadolibre.log'].sudo()
        start_time = time.time()

        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)
            duration = time.time() - start_time

            headers_log = {k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()}
            LogModel.create({
                'log_type': 'api_request',
                'level': 'success' if response.status_code == 200 else 'error',
                'account_id': self.account_id.id,
                'message': f'Sync Claims "{self.name}": GET /post-purchase/v1/claims/search - {response.status_code}',
                'request_url': response.url,
                'request_method': 'GET',
                'request_headers': json.dumps(headers_log, indent=2),
                'request_body': json.dumps(params, indent=2),
                'response_code': response.status_code,
                'response_body': response.text[:10000] if response.text else '',
                'duration': duration,
            })

            if response.status_code != 200:
                log_lines.append(f'ERROR API: {response.status_code}')
                log_lines.append(response.text[:500])
                self.write({
                    'last_sync': fields.Datetime.now(),
                    'last_sync_log': '\n'.join(log_lines),
                })
                return False

            data = response.json()

        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexion: %s', str(e))
            log_lines.append(f'ERROR: {str(e)}')
            self.write({
                'last_sync': fields.Datetime.now(),
                'last_sync_log': '\n'.join(log_lines),
            })
            return False

        results = data.get('data', [])
        paging = data.get('paging', {})
        total = paging.get('total', len(results))

        log_lines.append(f'  Total en ML: {total}')
        log_lines.append(f'  A procesar: {len(results)}')
        log_lines.append('')

        ClaimModel = self.env['mercadolibre.claim']
        sync_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0

        for claim_data in results:
            try:
                claim, is_new = ClaimModel.create_from_ml_data(claim_data, self.account_id)
                sync_count += 1

                if is_new:
                    created_count += 1
                    # Notificar nuevo claim
                    if self.notify_new_claim:
                        self._notify_new_claim(claim)
                else:
                    updated_count += 1
                    # Verificar cambios de estado
                    self._check_claim_changes(claim, claim_data)

            except Exception as e:
                error_count += 1
                _logger.error('Error procesando claim %s: %s', claim_data.get('id'), str(e))

        log_lines.append('-' * 50)
        log_lines.append('  RESUMEN')
        log_lines.append('-' * 50)
        log_lines.append(f'  Sincronizados: {sync_count}')
        log_lines.append(f'    Nuevos: {created_count}')
        log_lines.append(f'    Actualizados: {updated_count}')
        log_lines.append(f'  Errores: {error_count}')
        log_lines.append('=' * 50)

        # Calcular proxima ejecucion
        next_sync = fields.Datetime.now()
        if self.sync_interval_type == 'hours':
            next_sync += timedelta(hours=self.sync_interval_number)
        elif self.sync_interval_type == 'days':
            next_sync += timedelta(days=self.sync_interval_number)

        self.write({
            'last_sync': fields.Datetime.now(),
            'last_sync_count': sync_count,
            'last_sync_log': '\n'.join(log_lines),
            'next_sync': next_sync,
            'total_syncs': self.total_syncs + 1,
            'total_claims_synced': self.total_claims_synced + sync_count,
        })

        _logger.info('SYNC CLAIMS "%s" completada: %d sincronizados', self.name, sync_count)

        return True

    def _notify_new_claim(self, claim):
        """Notifica sobre un nuevo claim"""
        self.ensure_one()

        # Crear actividad
        if self.create_activity and self.activity_user_id:
            claim.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.activity_user_id.id,
                summary=f'Nuevo Reclamo: {claim.name}',
                note=f'''
                <p>Se ha recibido un nuevo reclamo:</p>
                <ul>
                    <li><strong>Tipo:</strong> {claim.type}</li>
                    <li><strong>Motivo:</strong> {claim.reason_id}</li>
                    <li><strong>Estado:</strong> {claim.status}</li>
                    <li><strong>Etapa:</strong> {claim.stage}</li>
                </ul>
                '''
            )

        # Notificar por chatter
        if self.notify_user_ids:
            partner_ids = self.notify_user_ids.mapped('partner_id').ids
            claim.message_post(
                body=f'Nuevo reclamo recibido. Tipo: {claim.type}, Motivo: {claim.reason_id}',
                message_type='notification',
                partner_ids=partner_ids,
            )

    def _check_claim_changes(self, claim, new_data):
        """Verifica cambios importantes en el claim"""
        self.ensure_one()

        # Verificar si paso a disputa/mediacion
        new_stage = new_data.get('stage', '')
        if new_stage == 'dispute' and claim.stage != 'dispute':
            if self.notify_stage_change:
                self._notify_stage_change(claim, 'dispute')

        # Verificar resolucion
        resolution = new_data.get('resolution', {})
        if resolution and new_data.get('status') == 'closed':
            if self.notify_resolution:
                self._notify_resolution(claim, resolution)

            # Ejecutar acciones segun resolucion
            self._process_resolution(claim, resolution)

    def _notify_stage_change(self, claim, new_stage):
        """Notifica cambio de etapa"""
        if self.create_activity and self.activity_user_id:
            claim.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.activity_user_id.id,
                summary=f'Reclamo en Mediacion: {claim.name}',
                note='El reclamo ha escalado a mediacion con MercadoLibre.',
            )

    def _notify_resolution(self, claim, resolution):
        """Notifica resolucion del claim"""
        benefited = resolution.get('benefited', [])
        reason = resolution.get('reason', '')

        if self.create_activity and self.activity_user_id:
            claim.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.activity_user_id.id,
                summary=f'Reclamo Resuelto: {claim.name}',
                note=f'Resolucion: {reason}. Beneficiado: {", ".join(benefited)}',
            )

    def _process_resolution(self, claim, resolution):
        """Procesa acciones segun la resolucion"""
        self.ensure_one()

        benefited = resolution.get('benefited', [])

        if 'complainant' in benefited:
            # Resolucion a favor del comprador
            self._execute_resolution_buyer_action(claim)
        elif 'respondent' in benefited:
            # Resolucion a favor del vendedor
            self._execute_resolution_seller_action(claim)

    def _execute_resolution_buyer_action(self, claim):
        """Ejecuta accion cuando resolucion favorece al comprador"""
        self.ensure_one()

        if self.resolution_buyer_action == 'cancel_payment':
            if claim.ml_payment_id and claim.ml_payment_id.odoo_payment_id:
                payment = claim.ml_payment_id.odoo_payment_id
                if payment.state not in ('cancelled', 'cancel'):
                    try:
                        payment.action_cancel()
                        claim._log_action('cancel_payment_resolution',
                                         'Pago cancelado por resolucion a favor del comprador')
                    except Exception as e:
                        _logger.error('Error cancelando pago: %s', str(e))

        elif self.resolution_buyer_action == 'notify':
            if self.create_activity and self.activity_user_id:
                claim.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=self.activity_user_id.id,
                    summary=f'Accion Requerida: {claim.name}',
                    note='Resolucion a favor del comprador. Revisar si se requiere cancelar/revertir pago.',
                )

    def _execute_resolution_seller_action(self, claim):
        """Ejecuta accion cuando resolucion favorece al vendedor"""
        self.ensure_one()

        if self.resolution_seller_action == 'confirm_payment':
            if claim.ml_payment_id and claim.ml_payment_id.odoo_payment_id:
                payment = claim.ml_payment_id.odoo_payment_id
                if payment.state == 'draft':
                    try:
                        payment.action_post()
                        claim._log_action('confirm_payment_resolution',
                                         'Pago confirmado por resolucion a favor del vendedor')
                    except Exception as e:
                        _logger.error('Error confirmando pago: %s', str(e))

        elif self.resolution_seller_action == 'notify':
            if self.create_activity and self.activity_user_id:
                claim.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=self.activity_user_id.id,
                    summary=f'Resolucion Favorable: {claim.name}',
                    note='Resolucion a favor del vendedor. El pago puede confirmarse.',
                )

    # =====================================================
    # PROCESAMIENTO DE PAGOS EN MEDIACION
    # =====================================================

    def process_payment_in_mediation(self, payment):
        """
        Procesa un pago que entro en estado de mediacion.
        Llamado desde mercadolibre.payment cuando detecta status = 'in_mediation'
        """
        self.ensure_one()

        if not self.auto_process_mediation:
            return

        _logger.info('Procesando pago en mediacion: %s', payment.mp_payment_id)

        action = self.mediation_action

        if action == 'none':
            return

        elif action == 'cancel_payment':
            self._action_cancel_odoo_payment(payment)

        elif action == 'create_cancelled':
            self._action_create_cancelled_payment(payment)

        elif action == 'reverse_payment':
            self._action_reverse_payment(payment)

        elif action == 'notify_only':
            self._action_notify_mediation(payment)

    def _action_cancel_odoo_payment(self, payment):
        """Cancela el pago Odoo si existe"""
        if payment.odoo_payment_id and payment.odoo_payment_id.state not in ('cancelled', 'cancel'):
            try:
                payment.odoo_payment_id.action_cancel()
                payment.write({
                    'mediation_action_taken': 'payment_cancelled',
                })
                _logger.info('Pago %s cancelado por mediacion', payment.odoo_payment_id.name)
            except Exception as e:
                _logger.error('Error cancelando pago: %s', str(e))

    def _action_create_cancelled_payment(self, payment):
        """Crea un pago en estado borrador/cancelado para registro"""
        if payment.odoo_payment_id:
            return  # Ya existe

        # Buscar config de pagos para obtener journals
        PaymentSyncConfig = self.env['mercadolibre.payment.sync.config']
        pay_config = PaymentSyncConfig.search([
            ('account_id', '=', payment.account_id.id),
            ('state', '=', 'active'),
        ], limit=1)

        if not pay_config:
            _logger.warning('No hay config de pagos para crear pago cancelado')
            return

        # Crear pago pero no confirmarlo
        try:
            result = payment._create_odoo_payment(pay_config)
            if result.get('payment'):
                # Mantenerlo en draft (no confirmar)
                payment.write({
                    'mediation_action_taken': 'payment_created_cancelled',
                })
                _logger.info('Pago creado en borrador para mediacion: %s', result['payment'].name)
        except Exception as e:
            _logger.error('Error creando pago cancelado: %s', str(e))

    def _action_reverse_payment(self, payment):
        """Crea asiento de reversion del pago"""
        if not payment.odoo_payment_id:
            return

        if not self.reversal_journal_id:
            _logger.warning('No hay diario de reversiones configurado')
            return

        try:
            # Crear asiento de reversion
            # Esto dependera de la estructura contable especifica
            payment.write({
                'mediation_action_taken': 'payment_reversed',
            })
            _logger.info('Pago revertido por mediacion: %s', payment.mp_payment_id)
        except Exception as e:
            _logger.error('Error revirtiendo pago: %s', str(e))

    def _action_notify_mediation(self, payment):
        """Crea notificacion/actividad para revision manual"""
        if self.create_activity and self.activity_user_id:
            payment.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.activity_user_id.id,
                summary=f'Pago en Mediacion: {payment.mp_payment_id}',
                note=f'''
                <p>El pago <strong>{payment.name}</strong> ha entrado en mediacion.</p>
                <p>Requiere revision manual para determinar la accion a tomar.</p>
                <ul>
                    <li><strong>Monto:</strong> {payment.transaction_amount}</li>
                    <li><strong>Order:</strong> {payment.mp_order_id or 'N/A'}</li>
                </ul>
                ''',
            )

        payment.write({
            'mediation_action_taken': 'pending_review',
        })

    # =====================================================
    # LIFECYCLE
    # =====================================================

    def write(self, vals):
        result = super().write(vals)
        if 'active' in vals:
            for record in self:
                if record.cron_id:
                    record.cron_id.active = vals['active'] and record.state == 'active'
        return result

    def unlink(self):
        for record in self:
            if record.cron_id:
                record.cron_id.unlink()
        return super().unlink()
