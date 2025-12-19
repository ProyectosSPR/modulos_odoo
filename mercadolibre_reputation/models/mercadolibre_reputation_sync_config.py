# -*- coding: utf-8 -*-

import json
import time
import logging
import requests
import pytz
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

MEXICO_TZ = pytz.timezone('America/Mexico_City')


class MercadolibreReputationSyncConfig(models.Model):
    _name = 'mercadolibre.reputation.sync.config'
    _description = 'Configuración de Sincronización de Reputación'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo para identificar esta sincronización'
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
        help='Cuenta de MercadoLibre a sincronizar'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # =====================================================
    # CONFIGURACION DE SINCRONIZACION
    # =====================================================

    # Qué sincronizar
    sync_seller_reputation = fields.Boolean(
        string='Sincronizar Reputación Vendedor',
        default=True,
        help='Sincronizar la reputación global del vendedor'
    )
    sync_item_experience = fields.Boolean(
        string='Sincronizar Experiencia por Ítem',
        default=True,
        help='Sincronizar la experiencia de compra de cada publicación'
    )

    # Filtros para ítems
    item_source = fields.Selection([
        ('orders', 'Desde Órdenes Sincronizadas'),
        ('api', 'Desde API de Items'),
        ('manual', 'Solo Manual'),
    ], string='Fuente de Ítems', default='orders',
        help='De dónde obtener la lista de ítems a sincronizar')

    items_limit = fields.Integer(
        string='Límite de Ítems',
        default=50,
        help='Número máximo de ítems a sincronizar por ejecución'
    )

    # Programación
    interval_number = fields.Integer(
        string='Ejecutar cada',
        default=6,
        required=True
    )
    interval_type = fields.Selection([
        ('minutes', 'Minutos'),
        ('hours', 'Horas'),
        ('days', 'Días'),
    ], string='Tipo Intervalo', default='hours', required=True)

    next_run = fields.Datetime(
        string='Próxima Ejecución'
    )
    last_run = fields.Datetime(
        string='Última Ejecución',
        readonly=True
    )

    # Estado
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

    # =====================================================
    # ESTADISTICAS
    # =====================================================
    last_sync_log = fields.Text(
        string='Log Última Ejecución',
        readonly=True
    )
    last_sync_reputation_ok = fields.Boolean(
        string='Última Rep. OK',
        readonly=True
    )
    last_sync_items_count = fields.Integer(
        string='Últimos Ítems Sincronizados',
        readonly=True
    )
    last_sync_items_errors = fields.Integer(
        string='Últimos Errores Ítems',
        readonly=True
    )

    total_syncs = fields.Integer(
        string='Total Ejecuciones',
        readonly=True,
        default=0
    )

    # =====================================================
    # ALERTAS
    # =====================================================
    alert_on_danger = fields.Boolean(
        string='Alertar en Peligro',
        default=True,
        help='Crear actividad cuando una métrica supere el límite'
    )
    alert_on_warning = fields.Boolean(
        string='Alertar en Advertencia',
        default=False,
        help='Crear actividad cuando una métrica se acerque al límite'
    )
    alert_user_id = fields.Many2one(
        'res.users',
        string='Usuario a Alertar',
        help='Usuario que recibirá las alertas'
    )

    # =====================================================
    # RELACION CON REPUTACION
    # =====================================================
    reputation_id = fields.Many2one(
        'mercadolibre.seller.reputation',
        string='Reputación',
        readonly=True,
        help='Registro de reputación asociado'
    )

    # =====================================================
    # METODOS DE CICLO DE VIDA
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

    # =====================================================
    # ACCIONES DE CONTROL
    # =====================================================

    def action_activate(self):
        """Activa la sincronización automática"""
        for record in self:
            if not record.account_id.has_valid_token:
                raise ValidationError(_('La cuenta %s no tiene un token válido.') % record.account_id.name)

            # Crear o obtener reputación
            reputation = self.env['mercadolibre.seller.reputation'].get_or_create_for_account(record.account_id)
            record.reputation_id = reputation.id

            record._create_or_update_cron()

            if not record.next_run:
                record.next_run = fields.Datetime.now()

            record.state = 'active'

    def action_pause(self):
        """Pausa la sincronización"""
        for record in self:
            if record.cron_id:
                record.cron_id.active = False
            record.state = 'paused'

    def action_resume(self):
        """Reanuda la sincronización"""
        for record in self:
            if not record.account_id.has_valid_token:
                raise ValidationError(_('La cuenta %s no tiene un token válido.') % record.account_id.name)

            if record.cron_id:
                record.cron_id.active = True
            else:
                record._create_or_update_cron()

            record.state = 'active'

    def action_run_now(self):
        """Ejecuta la sincronización manualmente"""
        self.ensure_one()
        return self._execute_sync()

    def _create_or_update_cron(self):
        """Crea o actualiza el cron job"""
        self.ensure_one()

        cron_vals = {
            'name': f'Sync Reputación ML: {self.name}',
            'model_id': self.env['ir.model']._get('mercadolibre.reputation.sync.config').id,
            'state': 'code',
            'code': f'model.browse({self.id})._execute_sync()',
            'interval_number': self.interval_number,
            'interval_type': self.interval_type,
            'numbercall': -1,
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

    # =====================================================
    # EJECUCION DE SINCRONIZACION
    # =====================================================

    def _execute_sync(self):
        """Ejecuta la sincronización de reputación"""
        self.ensure_one()

        _logger.info('=' * 60)
        _logger.info('SYNC REPUTACIÓN ML: Iniciando "%s"', self.name)
        _logger.info('=' * 60)

        if not self.account_id.has_valid_token:
            _logger.error('Cuenta %s sin token válido', self.account_id.name)
            self.write({
                'last_run': fields.Datetime.now(),
                'last_sync_log': 'ERROR: Cuenta sin token válido',
            })
            return False

        log_lines = []
        log_lines.append('=' * 50)
        log_lines.append(f'  SYNC REPUTACIÓN ML: {self.name}')
        log_lines.append('=' * 50)

        now_mexico = datetime.now(MEXICO_TZ)
        log_lines.append(f'  Fecha (Mexico): {now_mexico.strftime("%d/%m/%Y %H:%M:%S")}')
        log_lines.append(f'  Cuenta: {self.account_id.name}')
        log_lines.append('')

        reputation_ok = False
        items_synced = 0
        items_errors = 0

        # Asegurar que existe registro de reputación
        if not self.reputation_id:
            self.reputation_id = self.env['mercadolibre.seller.reputation'].get_or_create_for_account(self.account_id)

        # 1. Sincronizar reputación del vendedor
        if self.sync_seller_reputation:
            log_lines.append('-' * 50)
            log_lines.append('  REPUTACIÓN DEL VENDEDOR')
            log_lines.append('-' * 50)

            try:
                self.reputation_id._sync_from_api()
                reputation_ok = True
                log_lines.append(f'  Nivel: {self.reputation_id.level_id}')
                log_lines.append(f'  Power Seller: {self.reputation_id.power_seller_status}')
                log_lines.append(f'  Ventas: {self.reputation_id.sales_completed}')
                log_lines.append(f'  Reclamos: {self.reputation_id.claims_rate:.2f}%')
                log_lines.append(f'  Cancelaciones: {self.reputation_id.cancellations_rate:.2f}%')
                log_lines.append(f'  Despacho Tardío: {self.reputation_id.delayed_rate:.2f}%')
                log_lines.append('  [OK] Reputación sincronizada')

                # Verificar alertas
                self._check_and_create_alerts(log_lines)

            except Exception as e:
                log_lines.append(f'  [ERROR] {str(e)}')
                _logger.error('Error sincronizando reputación: %s', str(e))

        # 2. Sincronizar experiencia por ítem
        if self.sync_item_experience:
            log_lines.append('')
            log_lines.append('-' * 50)
            log_lines.append('  EXPERIENCIA POR ÍTEM')
            log_lines.append('-' * 50)

            items_to_sync = self._get_items_to_sync()
            log_lines.append(f'  Ítems a sincronizar: {len(items_to_sync)}')

            ExperienceModel = self.env['mercadolibre.item.experience']

            for item_data in items_to_sync[:self.items_limit]:
                ml_item_id = item_data.get('ml_item_id')
                title = item_data.get('title', '')

                try:
                    experience = ExperienceModel.create_or_update_for_item(
                        self.reputation_id,
                        ml_item_id,
                        title=title,
                        thumbnail=item_data.get('thumbnail')
                    )
                    experience._sync_from_api()
                    items_synced += 1

                except Exception as e:
                    items_errors += 1
                    _logger.warning('Error sincronizando ítem %s: %s', ml_item_id, str(e))

            log_lines.append(f'  Sincronizados: {items_synced}')
            log_lines.append(f'  Errores: {items_errors}')

        # Resumen final
        log_lines.append('')
        log_lines.append('=' * 50)
        log_lines.append('  RESUMEN')
        log_lines.append('=' * 50)
        log_lines.append(f'  Reputación: {"OK" if reputation_ok else "ERROR"}')
        log_lines.append(f'  Ítems sincronizados: {items_synced}')
        log_lines.append(f'  Ítems con error: {items_errors}')

        # Calcular próxima ejecución
        next_run = fields.Datetime.now()
        if self.interval_type == 'minutes':
            next_run += timedelta(minutes=self.interval_number)
        elif self.interval_type == 'hours':
            next_run += timedelta(hours=self.interval_number)
        elif self.interval_type == 'days':
            next_run += timedelta(days=self.interval_number)

        self.write({
            'last_run': fields.Datetime.now(),
            'next_run': next_run,
            'last_sync_log': '\n'.join(log_lines),
            'last_sync_reputation_ok': reputation_ok,
            'last_sync_items_count': items_synced,
            'last_sync_items_errors': items_errors,
            'total_syncs': self.total_syncs + 1,
        })

        _logger.info('SYNC REPUTACIÓN "%s" completada', self.name)
        return True

    def _get_items_to_sync(self):
        """Obtiene la lista de ítems a sincronizar según la configuración"""
        items = []

        if self.item_source == 'orders':
            # Obtener ítems únicos desde órdenes de ML
            # Verificar si existe el modelo de órdenes
            if 'mercadolibre.order' in self.env:
                orders = self.env['mercadolibre.order'].search([
                    ('account_id', '=', self.account_id.id),
                ], limit=500, order='date_closed desc')

                seen_items = set()
                for order in orders:
                    for item in order.item_ids:
                        if item.ml_item_id and item.ml_item_id not in seen_items:
                            seen_items.add(item.ml_item_id)
                            items.append({
                                'ml_item_id': item.ml_item_id,
                                'title': item.title,
                                'thumbnail': '',
                            })

        elif self.item_source == 'api':
            # Obtener ítems desde la API de MercadoLibre
            items = self._fetch_items_from_api()

        return items

    def _fetch_items_from_api(self):
        """Obtiene ítems activos desde la API de ML"""
        items = []

        try:
            access_token = self.account_id.get_valid_token_with_retry()
            if not access_token:
                return items

            user_id = self.account_id.ml_user_id
            url = f'https://api.mercadolibre.com/users/{user_id}/items/search'
            params = {
                'status': 'active',
                'limit': self.items_limit,
            }
            headers = {
                'Authorization': f'Bearer {access_token}',
            }

            response = requests.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                item_ids = data.get('results', [])

                # Obtener detalles de cada ítem
                for item_id in item_ids[:self.items_limit]:
                    items.append({
                        'ml_item_id': item_id,
                        'title': '',
                        'thumbnail': '',
                    })

        except Exception as e:
            _logger.error('Error obteniendo ítems desde API: %s', str(e))

        return items

    def _check_and_create_alerts(self, log_lines):
        """Verifica métricas y crea alertas si es necesario"""
        if not self.alert_on_danger and not self.alert_on_warning:
            return

        if not self.alert_user_id:
            return

        rep = self.reputation_id
        alerts = []

        # Verificar cada métrica
        if rep.claims_status == 'danger' and self.alert_on_danger:
            alerts.append(f'Reclamos en PELIGRO: {rep.claims_rate:.2f}% (límite: {rep.claims_limit_green}%)')
        elif rep.claims_status == 'warning' and self.alert_on_warning:
            alerts.append(f'Reclamos en ADVERTENCIA: {rep.claims_rate:.2f}%')

        if rep.cancellations_status == 'danger' and self.alert_on_danger:
            alerts.append(f'Cancelaciones en PELIGRO: {rep.cancellations_rate:.2f}% (límite: {rep.cancellations_limit_green}%)')
        elif rep.cancellations_status == 'warning' and self.alert_on_warning:
            alerts.append(f'Cancelaciones en ADVERTENCIA: {rep.cancellations_rate:.2f}%')

        if rep.delayed_status == 'danger' and self.alert_on_danger:
            alerts.append(f'Despacho en PELIGRO: {rep.delayed_rate:.2f}% (límite: {rep.delayed_limit_green}%)')
        elif rep.delayed_status == 'warning' and self.alert_on_warning:
            alerts.append(f'Despacho en ADVERTENCIA: {rep.delayed_rate:.2f}%')

        if alerts:
            log_lines.append('')
            log_lines.append('  ⚠️ ALERTAS:')
            for alert in alerts:
                log_lines.append(f'    - {alert}')

            # Crear actividad
            activity_type = self.env.ref('mail.mail_activity_data_warning', raise_if_not_found=False)
            if activity_type:
                rep.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary='Alerta de Reputación MercadoLibre',
                    note='\n'.join(alerts),
                    user_id=self.alert_user_id.id,
                )

    # =====================================================
    # CRON GLOBAL
    # =====================================================

    @api.model
    def _cron_sync_all(self):
        """Cron para sincronizar todas las configuraciones activas"""
        configs = self.search([('state', '=', 'active')])
        for config in configs:
            try:
                config._execute_sync()
            except Exception as e:
                _logger.error('Error en sync de reputación %s: %s', config.name, str(e))
