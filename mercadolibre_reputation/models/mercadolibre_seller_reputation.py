# -*- coding: utf-8 -*-

import json
import logging
import requests
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreSellerReputation(models.Model):
    _name = 'mercadolibre.seller.reputation'
    _description = 'Reputación del Vendedor MercadoLibre'
    _order = 'last_sync desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='cascade',
        index=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # === NIVEL DE REPUTACION ===
    level_id = fields.Selection([
        ('5_green', 'Verde (Excelente)'),
        ('4_light_green', 'Verde Claro (Muy Bueno)'),
        ('3_yellow', 'Amarillo (Bueno)'),
        ('2_orange', 'Naranja (Regular)'),
        ('1_red', 'Rojo (Malo)'),
        ('newbie', 'Sin Reputación'),
    ], string='Nivel de Reputación', tracking=True)

    level_color = fields.Char(
        string='Color',
        compute='_compute_level_color',
        store=True
    )

    power_seller_status = fields.Selection([
        ('platinum', 'MercadoLíder Platinum'),
        ('gold', 'MercadoLíder Gold'),
        ('silver', 'MercadoLíder Silver'),
        ('none', 'Sin Medalla'),
    ], string='Power Seller', default='none', tracking=True)

    # Protección (si aplica)
    is_protected = fields.Boolean(
        string='Está Protegido',
        default=False,
        help='Si el vendedor está en período de protección'
    )
    real_level = fields.Selection([
        ('5_green', 'Verde'),
        ('4_light_green', 'Verde Claro'),
        ('3_yellow', 'Amarillo'),
        ('2_orange', 'Naranja'),
        ('1_red', 'Rojo'),
    ], string='Nivel Real',
        help='Nivel real durante período de protección')

    protection_end_date = fields.Datetime(
        string='Fin de Protección',
        help='Fecha de fin del período de protección'
    )

    # === TRANSACCIONES ===
    transactions_total = fields.Integer(
        string='Total Transacciones',
        readonly=True
    )
    transactions_completed = fields.Integer(
        string='Transacciones Completadas',
        readonly=True
    )
    transactions_canceled = fields.Integer(
        string='Transacciones Canceladas',
        readonly=True
    )
    transactions_period = fields.Char(
        string='Período Transacciones',
        readonly=True
    )

    # Ratings
    rating_positive = fields.Float(
        string='% Positivas',
        readonly=True,
        digits=(5, 2)
    )
    rating_neutral = fields.Float(
        string='% Neutras',
        readonly=True,
        digits=(5, 2)
    )
    rating_negative = fields.Float(
        string='% Negativas',
        readonly=True,
        digits=(5, 2)
    )

    # === METRICAS DE CALIDAD (últimos 60 días) ===
    metrics_period = fields.Char(
        string='Período Métricas',
        readonly=True,
        default='60 days'
    )
    sales_completed = fields.Integer(
        string='Ventas Completadas',
        readonly=True
    )

    # Claims
    claims_rate = fields.Float(
        string='Tasa Reclamos (%)',
        readonly=True,
        digits=(5, 4),
        tracking=True
    )
    claims_value = fields.Integer(
        string='Cantidad Reclamos',
        readonly=True
    )
    claims_rate_excluded = fields.Float(
        string='Tasa Real Reclamos (%)',
        readonly=True,
        digits=(5, 4),
        help='Tasa real (si está protegido)'
    )
    claims_value_excluded = fields.Integer(
        string='Cantidad Real Reclamos',
        readonly=True
    )

    # Cancellations
    cancellations_rate = fields.Float(
        string='Tasa Cancelaciones (%)',
        readonly=True,
        digits=(5, 4),
        tracking=True
    )
    cancellations_value = fields.Integer(
        string='Cantidad Cancelaciones',
        readonly=True
    )
    cancellations_rate_excluded = fields.Float(
        string='Tasa Real Cancelaciones (%)',
        readonly=True,
        digits=(5, 4)
    )
    cancellations_value_excluded = fields.Integer(
        string='Cantidad Real Cancelaciones',
        readonly=True
    )

    # Delayed Handling Time
    delayed_rate = fields.Float(
        string='Tasa Despacho Tardío (%)',
        readonly=True,
        digits=(5, 4),
        tracking=True
    )
    delayed_value = fields.Integer(
        string='Cantidad Despachos Tardíos',
        readonly=True
    )
    delayed_rate_excluded = fields.Float(
        string='Tasa Real Despacho Tardío (%)',
        readonly=True,
        digits=(5, 4)
    )
    delayed_value_excluded = fields.Integer(
        string='Cantidad Real Despachos Tardíos',
        readonly=True
    )

    # === LIMITES POR SITE ===
    site_id = fields.Char(
        string='Site ID',
        readonly=True,
        help='MLM, MLA, MLB, etc.'
    )

    # Límites configurados (dependen del site)
    claims_limit_green = fields.Float(
        string='Límite Reclamos (Verde)',
        default=1.0,
        digits=(5, 2)
    )
    cancellations_limit_green = fields.Float(
        string='Límite Cancelaciones (Verde)',
        default=0.5,
        digits=(5, 2)
    )
    delayed_limit_green = fields.Float(
        string='Límite Despacho (Verde)',
        default=8.0,
        digits=(5, 2)
    )

    # === ESTADOS DE ALERTA ===
    claims_status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Advertencia'),
        ('danger', 'Peligro'),
    ], string='Estado Reclamos', compute='_compute_status', store=True)

    cancellations_status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Advertencia'),
        ('danger', 'Peligro'),
    ], string='Estado Cancelaciones', compute='_compute_status', store=True)

    delayed_status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Advertencia'),
        ('danger', 'Peligro'),
    ], string='Estado Despacho', compute='_compute_status', store=True)

    overall_status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Advertencia'),
        ('danger', 'Peligro'),
    ], string='Estado General', compute='_compute_status', store=True)

    # === EXPERIENCIA DE COMPRA (resumen) ===
    items_good_count = fields.Integer(
        string='Ítems Experiencia Buena',
        compute='_compute_items_summary',
        store=True
    )
    items_medium_count = fields.Integer(
        string='Ítems Experiencia Media',
        compute='_compute_items_summary',
        store=True
    )
    items_bad_count = fields.Integer(
        string='Ítems Experiencia Mala',
        compute='_compute_items_summary',
        store=True
    )
    items_no_data_count = fields.Integer(
        string='Ítems Sin Datos',
        compute='_compute_items_summary',
        store=True
    )

    # === RELACIONES ===
    item_experience_ids = fields.One2many(
        'mercadolibre.item.experience',
        'reputation_id',
        string='Experiencia por Ítem'
    )
    history_ids = fields.One2many(
        'mercadolibre.reputation.history',
        'reputation_id',
        string='Historial'
    )

    # === SINCRONIZACION ===
    last_sync = fields.Datetime(
        string='Última Sincronización',
        readonly=True
    )
    raw_data = fields.Text(
        string='Datos Crudos JSON',
        readonly=True
    )

    _sql_constraints = [
        ('account_uniq', 'unique(account_id)',
         'Ya existe un registro de reputación para esta cuenta.')
    ]

    # =====================================================
    # CAMPOS COMPUTADOS
    # =====================================================

    @api.depends('account_id', 'level_id')
    def _compute_name(self):
        for record in self:
            level_name = dict(self._fields['level_id'].selection).get(record.level_id, '')
            record.name = f'{record.account_id.name} - {level_name}' if record.account_id else 'Nueva Reputación'

    @api.depends('level_id')
    def _compute_level_color(self):
        color_map = {
            '5_green': '#00a650',
            '4_light_green': '#8bc34a',
            '3_yellow': '#fff159',
            '2_orange': '#ff7733',
            '1_red': '#f23d4f',
            'newbie': '#999999',
        }
        for record in self:
            record.level_color = color_map.get(record.level_id, '#999999')

    @api.depends('claims_rate', 'claims_limit_green',
                 'cancellations_rate', 'cancellations_limit_green',
                 'delayed_rate', 'delayed_limit_green')
    def _compute_status(self):
        for record in self:
            # Claims status
            if record.claims_rate >= record.claims_limit_green:
                record.claims_status = 'danger'
            elif record.claims_rate >= record.claims_limit_green * 0.8:
                record.claims_status = 'warning'
            else:
                record.claims_status = 'ok'

            # Cancellations status
            if record.cancellations_rate >= record.cancellations_limit_green:
                record.cancellations_status = 'danger'
            elif record.cancellations_rate >= record.cancellations_limit_green * 0.8:
                record.cancellations_status = 'warning'
            else:
                record.cancellations_status = 'ok'

            # Delayed status
            if record.delayed_rate >= record.delayed_limit_green:
                record.delayed_status = 'danger'
            elif record.delayed_rate >= record.delayed_limit_green * 0.8:
                record.delayed_status = 'warning'
            else:
                record.delayed_status = 'ok'

            # Overall status
            statuses = [record.claims_status, record.cancellations_status, record.delayed_status]
            if 'danger' in statuses:
                record.overall_status = 'danger'
            elif 'warning' in statuses:
                record.overall_status = 'warning'
            else:
                record.overall_status = 'ok'

    @api.depends('item_experience_ids', 'item_experience_ids.color')
    def _compute_items_summary(self):
        for record in self:
            experiences = record.item_experience_ids
            record.items_good_count = len(experiences.filtered(lambda x: x.color == 'green'))
            record.items_medium_count = len(experiences.filtered(lambda x: x.color == 'orange'))
            record.items_bad_count = len(experiences.filtered(lambda x: x.color == 'red'))
            record.items_no_data_count = len(experiences.filtered(lambda x: x.color == 'gray'))

    # =====================================================
    # METODOS DE SINCRONIZACION
    # =====================================================

    def action_sync_reputation(self):
        """Sincroniza la reputación desde MercadoLibre"""
        self.ensure_one()
        return self._sync_from_api()

    def _sync_from_api(self):
        """Obtiene datos de reputación desde la API"""
        self.ensure_one()

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token válido'))

        user_id = self.account_id.ml_user_id
        url = f'https://api.mercadolibre.com/users/{user_id}'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                raise UserError(_('Error al obtener reputación: %s') % response.text)

            data = response.json()
            self._process_reputation_data(data)

            return True

        except requests.exceptions.RequestException as e:
            _logger.error('Error sincronizando reputación: %s', str(e))
            raise UserError(_('Error de conexión: %s') % str(e))

    def _process_reputation_data(self, data):
        """Procesa los datos de reputación del usuario"""
        self.ensure_one()

        seller_rep = data.get('seller_reputation', {}) or {}
        transactions = seller_rep.get('transactions', {}) or {}
        metrics = seller_rep.get('metrics', {}) or {}
        ratings = transactions.get('ratings', {}) or {}

        # Extraer métricas
        sales = metrics.get('sales', {}) or {}
        claims = metrics.get('claims', {}) or {}
        cancellations = metrics.get('cancellations', {}) or {}
        delayed = metrics.get('delayed_handling_time', {}) or {}

        # Extraer excluded (datos reales si está protegido)
        claims_excluded = claims.get('excluded', {}) or {}
        cancellations_excluded = cancellations.get('excluded', {}) or {}
        delayed_excluded = delayed.get('excluded', {}) or {}

        # Determinar site_id y límites
        site_id = data.get('site_id', 'MLM')
        limits = self._get_limits_for_site(site_id)

        vals = {
            'level_id': seller_rep.get('level_id', 'newbie'),
            'power_seller_status': seller_rep.get('power_seller_status') or 'none',
            'real_level': seller_rep.get('real_level'),
            'protection_end_date': self._parse_datetime(seller_rep.get('protection_end_date')),
            'is_protected': bool(seller_rep.get('protection_end_date')),
            # Transacciones
            'transactions_total': transactions.get('total', 0),
            'transactions_completed': transactions.get('completed', 0),
            'transactions_canceled': transactions.get('canceled', 0),
            'transactions_period': transactions.get('period', ''),
            # Ratings
            'rating_positive': (ratings.get('positive', 0) or 0) * 100,
            'rating_neutral': (ratings.get('neutral', 0) or 0) * 100,
            'rating_negative': (ratings.get('negative', 0) or 0) * 100,
            # Métricas
            'metrics_period': sales.get('period', '60 days'),
            'sales_completed': sales.get('completed', 0),
            # Claims
            'claims_rate': (claims.get('rate', 0) or 0) * 100,
            'claims_value': claims.get('value', 0),
            'claims_rate_excluded': (claims_excluded.get('real_rate', 0) or 0) * 100,
            'claims_value_excluded': claims_excluded.get('real_value', 0),
            # Cancelaciones
            'cancellations_rate': (cancellations.get('rate', 0) or 0) * 100,
            'cancellations_value': cancellations.get('value', 0),
            'cancellations_rate_excluded': (cancellations_excluded.get('real_rate', 0) or 0) * 100,
            'cancellations_value_excluded': cancellations_excluded.get('real_value', 0),
            # Despacho tardío
            'delayed_rate': (delayed.get('rate', 0) or 0) * 100,
            'delayed_value': delayed.get('value', 0),
            'delayed_rate_excluded': (delayed_excluded.get('real_rate', 0) or 0) * 100,
            'delayed_value_excluded': delayed_excluded.get('real_value', 0),
            # Site y límites
            'site_id': site_id,
            'claims_limit_green': limits['claims'],
            'cancellations_limit_green': limits['cancellations'],
            'delayed_limit_green': limits['delayed'],
            # Sync
            'last_sync': fields.Datetime.now(),
            'raw_data': json.dumps(seller_rep, indent=2, ensure_ascii=False),
        }

        self.write(vals)

        # Guardar en historial
        self._save_history()

        _logger.info('Reputación sincronizada para cuenta %s', self.account_id.name)

    def _get_limits_for_site(self, site_id):
        """Retorna los límites según el site"""
        # Límites para verde según documentación ML
        limits_by_site = {
            'MLM': {'claims': 1.5, 'cancellations': 1.0, 'delayed': 10.0},
            'MLA': {'claims': 1.5, 'cancellations': 1.0, 'delayed': 10.0},
            'MLB': {'claims': 2.0, 'cancellations': 1.5, 'delayed': 10.0},
            'MCO': {'claims': 3.5, 'cancellations': 2.5, 'delayed': 12.0},
            'MLC': {'claims': 3.5, 'cancellations': 2.5, 'delayed': 12.0},
            'MLU': {'claims': 3.5, 'cancellations': 2.5, 'delayed': 12.0},
            'MPE': {'claims': 2.0, 'cancellations': 2.5, 'delayed': 12.0},
            'MEC': {'claims': 4.0, 'cancellations': 3.0, 'delayed': 12.0},
        }
        return limits_by_site.get(site_id, limits_by_site['MLM'])

    def _save_history(self):
        """Guarda el estado actual en el historial"""
        self.ensure_one()
        self.env['mercadolibre.reputation.history'].create({
            'reputation_id': self.id,
            'account_id': self.account_id.id,
            'date': fields.Date.today(),
            'level_id': self.level_id,
            'claims_rate': self.claims_rate,
            'cancellations_rate': self.cancellations_rate,
            'delayed_rate': self.delayed_rate,
            'sales_completed': self.sales_completed,
        })

    def _parse_datetime(self, dt_string):
        """Parsea fecha/hora de MercadoLibre"""
        if not dt_string:
            return False
        try:
            if 'T' in dt_string:
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

    # =====================================================
    # ACCIONES DE VISTA
    # =====================================================

    def action_view_items_good(self):
        """Ver ítems con experiencia buena"""
        return self._action_view_items_by_color('green', 'Ítems - Experiencia Buena')

    def action_view_items_medium(self):
        """Ver ítems con experiencia media"""
        return self._action_view_items_by_color('orange', 'Ítems - Experiencia Media')

    def action_view_items_bad(self):
        """Ver ítems con experiencia mala"""
        return self._action_view_items_by_color('red', 'Ítems - Experiencia Mala')

    def action_view_items_no_data(self):
        """Ver ítems sin datos"""
        return self._action_view_items_by_color('gray', 'Ítems - Sin Datos')

    def _action_view_items_by_color(self, color, name):
        """Acción genérica para ver ítems filtrados por color"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'mercadolibre.item.experience',
            'view_mode': 'tree,form',
            'domain': [('reputation_id', '=', self.id), ('color', '=', color)],
            'context': {'default_reputation_id': self.id},
        }

    def action_view_history(self):
        """Ver historial de reputación"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Historial de Reputación'),
            'res_model': 'mercadolibre.reputation.history',
            'view_mode': 'tree,graph',
            'domain': [('reputation_id', '=', self.id)],
        }

    @api.model
    def get_or_create_for_account(self, account):
        """Obtiene o crea el registro de reputación para una cuenta"""
        reputation = self.search([('account_id', '=', account.id)], limit=1)
        if not reputation:
            reputation = self.create({'account_id': account.id})
        return reputation
