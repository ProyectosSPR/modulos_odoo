# -*- coding: utf-8 -*-

import json
import logging
import requests
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreItemExperience(models.Model):
    _name = 'mercadolibre.item.experience'
    _description = 'Experiencia de Compra por Ítem'
    _order = 'score asc, last_sync desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    reputation_id = fields.Many2one(
        'mercadolibre.seller.reputation',
        string='Reputación',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        related='reputation_id.account_id',
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='reputation_id.company_id',
        store=True,
        readonly=True
    )

    # === IDENTIFICACION DEL ITEM ===
    ml_item_id = fields.Char(
        string='Item ID',
        required=True,
        index=True,
        help='ID de la publicación en MercadoLibre'
    )
    title = fields.Char(
        string='Título',
        readonly=True
    )
    thumbnail = fields.Char(
        string='Imagen URL',
        readonly=True
    )

    # === EXPERIENCIA DE COMPRA ===
    score = fields.Integer(
        string='Score',
        readonly=True,
        help='100=Buena, 65=Media-Alta, 50=Media, 30=Mala, -1=Sin datos',
        tracking=True
    )
    color = fields.Selection([
        ('green', 'Verde (Buena)'),
        ('orange', 'Naranja (Media)'),
        ('red', 'Rojo (Mala)'),
        ('gray', 'Gris (Sin datos)'),
    ], string='Color', readonly=True, tracking=True)

    color_hex = fields.Char(
        string='Color Hex',
        compute='_compute_color_hex',
        store=True
    )

    reputation_text = fields.Char(
        string='Texto Reputación',
        readonly=True,
        help='Buena, Media, Mala'
    )

    # === ESTADO DEL ITEM ===
    status = fields.Selection([
        ('active', 'Activo'),
        ('paused', 'Pausado'),
        ('moderated', 'Moderado'),
    ], string='Estado', readonly=True)

    status_assigned_by = fields.Selection([
        ('reputation', 'Por Reputación'),
        ('other', 'Otro'),
    ], string='Pausado Por', readonly=True)

    status_text = fields.Text(
        string='Texto Estado',
        readonly=True
    )

    # === TITULOS Y DESCRIPCIONES (de la API) ===
    experience_title = fields.Char(
        string='Título Experiencia',
        readonly=True
    )
    subtitle_1 = fields.Text(
        string='Subtítulo 1',
        readonly=True
    )
    subtitle_2 = fields.Text(
        string='Subtítulo 2',
        readonly=True
    )

    # === FREEZE (Protección) ===
    is_frozen = fields.Boolean(
        string='Está Congelado',
        readonly=True,
        help='El ítem está protegido temporalmente'
    )
    freeze_text = fields.Text(
        string='Texto Congelamiento',
        readonly=True
    )

    # === METRICAS ===
    problems_count = fields.Integer(
        string='Cantidad Problemas',
        compute='_compute_problems_count',
        store=True
    )
    claims_count = fields.Integer(
        string='Reclamos',
        readonly=True
    )
    cancellations_count = fields.Integer(
        string='Cancelaciones',
        readonly=True
    )

    # Período de evaluación
    period_from = fields.Date(
        string='Período Desde',
        readonly=True
    )
    period_to = fields.Date(
        string='Período Hasta',
        readonly=True
    )

    # === RELACIONES ===
    problem_ids = fields.One2many(
        'mercadolibre.item.experience.problem',
        'experience_id',
        string='Problemas'
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
        ('item_reputation_uniq', 'unique(ml_item_id, reputation_id)',
         'Este ítem ya existe para esta reputación.')
    ]

    # =====================================================
    # CAMPOS COMPUTADOS
    # =====================================================

    @api.depends('ml_item_id', 'title', 'score')
    def _compute_name(self):
        for record in self:
            title_short = (record.title or '')[:50]
            record.name = f'{record.ml_item_id} - {title_short}' if record.ml_item_id else 'Nuevo Ítem'

    @api.depends('color')
    def _compute_color_hex(self):
        color_map = {
            'green': '#00a650',
            'orange': '#ff7733',
            'red': '#f23d4f',
            'gray': '#999999',
        }
        for record in self:
            record.color_hex = color_map.get(record.color, '#999999')

    @api.depends('problem_ids')
    def _compute_problems_count(self):
        for record in self:
            record.problems_count = len(record.problem_ids)

    # =====================================================
    # METODOS DE SINCRONIZACION
    # =====================================================

    def action_sync_experience(self):
        """Sincroniza la experiencia de compra desde MercadoLibre"""
        self.ensure_one()
        return self._sync_from_api()

    def _sync_from_api(self):
        """Obtiene datos de experiencia de compra desde la API"""
        self.ensure_one()

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token válido'))

        # Determinar locale según site
        site_id = self.reputation_id.site_id or 'MLM'
        locale_map = {
            'MLM': 'es_MX',
            'MLA': 'es_AR',
            'MLB': 'pt_BR',
            'MCO': 'es_CO',
            'MLC': 'es_CL',
            'MLU': 'es_UY',
            'MPE': 'es_PE',
            'MEC': 'es_EC',
        }
        locale = locale_map.get(site_id, 'es_MX')

        url = f'https://api.mercadolibre.com/reputation/items/{self.ml_item_id}/purchase_experience/integrators'
        params = {'locale': locale}
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 404:
                _logger.warning('Ítem %s no tiene datos de experiencia', self.ml_item_id)
                self.write({
                    'score': -1,
                    'color': 'gray',
                    'reputation_text': 'Sin datos',
                    'last_sync': fields.Datetime.now(),
                })
                return True

            if response.status_code != 200:
                raise UserError(_('Error al obtener experiencia: %s') % response.text)

            data = response.json()
            self._process_experience_data(data)

            return True

        except requests.exceptions.RequestException as e:
            _logger.error('Error sincronizando experiencia ítem %s: %s', self.ml_item_id, str(e))
            raise UserError(_('Error de conexión: %s') % str(e))

    def _process_experience_data(self, data):
        """Procesa los datos de experiencia de compra"""
        self.ensure_one()

        reputation = data.get('reputation', {}) or {}
        status = data.get('status', {}) or {}
        freeze = data.get('freeze', {}) or {}
        metrics = data.get('metrics_details', {}) or {}
        distribution = metrics.get('distribution', {}) or {}

        # Extraer subtítulos
        subtitles = data.get('subtitles', []) or []
        subtitle_1 = ''
        subtitle_2 = ''
        for sub in subtitles:
            text = sub.get('text', '')
            # Limpiar placeholders
            placeholders = sub.get('placeholders', [])
            for i, ph in enumerate(placeholders):
                text = text.replace(f'{{{i}}}', ph)
            if sub.get('order', 0) == 0:
                subtitle_1 = text
            elif sub.get('order', 0) == 1:
                subtitle_2 = text

        # Calcular totales de claims y cancelaciones
        total_claims = 0
        total_cancellations = 0
        problems = metrics.get('problems', []) or []
        for problem in problems:
            total_claims += problem.get('claims', 0)
            total_cancellations += problem.get('cancellations', 0)

        # Mapear color
        color_value = reputation.get('color', 'gray')
        color_map = {
            'green': 'green',
            'orange': 'orange',
            'red': 'red',
            'gray': 'gray',
        }

        vals = {
            'score': reputation.get('value', -1),
            'color': color_map.get(color_value, 'gray'),
            'reputation_text': reputation.get('text', ''),
            # Estado
            'status': status.get('id', 'active'),
            'status_assigned_by': status.get('assigned_by'),
            'status_text': status.get('text', ''),
            # Títulos
            'experience_title': data.get('title', {}).get('text', ''),
            'subtitle_1': subtitle_1,
            'subtitle_2': subtitle_2,
            # Freeze
            'is_frozen': bool(freeze.get('text')),
            'freeze_text': freeze.get('text', ''),
            # Métricas
            'claims_count': total_claims,
            'cancellations_count': total_cancellations,
            # Período
            'period_from': self._parse_date(distribution.get('from')),
            'period_to': self._parse_date(distribution.get('to')),
            # Sync
            'last_sync': fields.Datetime.now(),
            'raw_data': json.dumps(data, indent=2, ensure_ascii=False),
        }

        self.write(vals)

        # Procesar problemas
        self._process_problems(problems)

        _logger.info('Experiencia sincronizada para ítem %s: score=%s', self.ml_item_id, vals['score'])

    def _process_problems(self, problems_data):
        """Procesa y crea los problemas del ítem"""
        ProblemModel = self.env['mercadolibre.item.experience.problem']

        # Eliminar problemas existentes
        self.problem_ids.unlink()

        for problem in problems_data:
            level_two = problem.get('level_two', {}) or {}
            level_three = problem.get('level_three', {}) or {}

            ProblemModel.create({
                'experience_id': self.id,
                'order': problem.get('order', 0),
                'level_one_key': problem.get('key', ''),
                'level_one_color': problem.get('color', ''),
                'level_two_key': level_two.get('key', ''),
                'level_two_title': level_two.get('title', {}).get('text', ''),
                'level_three_key': level_three.get('key', ''),
                'level_three_title': level_three.get('title', {}).get('text', ''),
                'remedy': level_three.get('remedy', {}).get('text', ''),
                'claims_count': problem.get('claims', 0),
                'cancellations_count': problem.get('cancellations', 0),
                'quantity_text': problem.get('quantity', ''),
                'is_main_problem': problem.get('tag', '') == 'PROBLEMA PRINCIPAL',
            })

    def _parse_date(self, date_string):
        """Parsea fecha de la API"""
        if not date_string:
            return False
        try:
            # Formato: 2023-07-04T19:08:56Z
            if 'T' in date_string:
                date_string = date_string.split('T')[0]
            return datetime.strptime(date_string, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return False

    # =====================================================
    # ACCIONES
    # =====================================================

    def action_view_problems(self):
        """Ver problemas del ítem"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Problemas del Ítem'),
            'res_model': 'mercadolibre.item.experience.problem',
            'view_mode': 'tree,form',
            'domain': [('experience_id', '=', self.id)],
        }

    def action_open_in_ml(self):
        """Abre el ítem en MercadoLibre"""
        self.ensure_one()
        site_urls = {
            'MLM': 'https://articulo.mercadolibre.com.mx',
            'MLA': 'https://articulo.mercadolibre.com.ar',
            'MLB': 'https://produto.mercadolivre.com.br',
            'MCO': 'https://articulo.mercadolibre.com.co',
            'MLC': 'https://articulo.mercadolibre.cl',
        }
        site_id = self.reputation_id.site_id or 'MLM'
        base_url = site_urls.get(site_id, site_urls['MLM'])

        return {
            'type': 'ir.actions.act_url',
            'url': f'{base_url}/{self.ml_item_id}',
            'target': 'new',
        }

    @api.model
    def create_or_update_for_item(self, reputation, ml_item_id, title=None, thumbnail=None):
        """Crea o actualiza el registro de experiencia para un ítem"""
        experience = self.search([
            ('reputation_id', '=', reputation.id),
            ('ml_item_id', '=', ml_item_id)
        ], limit=1)

        vals = {
            'reputation_id': reputation.id,
            'ml_item_id': ml_item_id,
        }
        if title:
            vals['title'] = title
        if thumbnail:
            vals['thumbnail'] = thumbnail

        if experience:
            experience.write(vals)
        else:
            experience = self.create(vals)

        return experience
