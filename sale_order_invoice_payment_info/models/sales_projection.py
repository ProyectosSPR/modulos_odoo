from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime
from calendar import monthrange
import logging

_logger = logging.getLogger(__name__)


class SalesProjection(models.Model):
    _name = 'sales.projection'
    _description = 'Proyecciones de Ventas'
    _order = 'year desc, create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre de la Proyección',
        required=True,
        help='Nombre o versión de esta proyección (ej: Proyección Q1 2025 v1)'
    )
    year = fields.Char(
        string='Año',
        required=True,
        default=lambda self: str(datetime.now().year),
        help='Año de la proyección'
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activa'),
        ('closed', 'Cerrada')
    ], string='Estado', default='draft', required=True, tracking=True)

    line_ids = fields.One2many(
        'sales.projection.line',
        'projection_id',
        string='Líneas de Proyección'
    )

    total_projected = fields.Monetary(
        string='Total Proyectado',
        compute='_compute_total_projected',
        store=True,
        currency_field='currency_id',
        help='Suma total de todas las proyecciones mensuales'
    )

    previous_projection_id = fields.Many2one(
        'sales.projection',
        string='Proyección Anterior',
        help='Proyección anterior para calcular la temporalidad'
    )

    temporality = fields.Percentage(
        string='Temporalidad Total (%)',
        compute='_compute_temporality',
        store=True,
        digits=(16, 2),
        help='Porcentaje del total actual vs el total de la proyección anterior. Ej: 120.00 significa que el total actual es un 20% mayor.'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    create_date = fields.Datetime(
        string='Fecha de Creación',
        readonly=True
    )

    notes = fields.Text(
        string='Notas',
        help='Comentarios o notas sobre esta proyección'
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_year_unique', 'unique(name, year)',
         'Ya existe una proyección con ese nombre para este año.')
    ]

    @api.depends('line_ids.projected_amount')
    def _compute_total_projected(self):
        """Calcula el total proyectado de todas las líneas"""
        for projection in self:
            projection.total_projected = sum(projection.line_ids.mapped('projected_amount'))

    @api.depends('total_projected', 'previous_projection_id.total_projected')
    def _compute_temporality(self):
        """Calcula la temporalidad total como un porcentaje del total actual vs el total anterior."""
        for projection in self:
            total_previous = projection.previous_projection_id.total_projected
            if total_previous > 0:
                projection.temporality = (projection.total_projected / total_previous) * 100
            else:
                projection.temporality = 0.0

    def action_activate(self):
        """Activa la proyección y genera los reportes automáticamente"""
        for projection in self:
            projection.state = 'active'
            projection._generate_quarterly_reports()
        return True

    def _generate_quarterly_reports(self):
        """Genera registros de reporte cuatrimestral para todas las líneas de esta proyección"""
        self.ensure_one()
        QuarterlyReport = self.env['quarterly.sales.report'].sudo()
        for line in self.line_ids:
            existing = QuarterlyReport.search([('projection_line_id', '=', line.id)])
            if not existing:
                QuarterlyReport.create({'projection_line_id': line.id})
                _logger.info(f"Reporte creado para {line.team_unified_id.name} - {line.period_month}/{line.year}")
            else:
                _logger.info(f"Reporte ya existe para {line.team_unified_id.name} - {line.period_month}/{line.year}")

    def action_close(self):
        self.state = 'closed'
        return True

    def action_back_to_draft(self):
        self.state = 'draft'
        return True


class SalesProjectionLine(models.Model):
    _name = 'sales.projection.line'
    _description = 'Líneas de Proyección de Ventas Mensual'
    _order = 'projection_id, period_month, team_unified_id'

    projection_id = fields.Many2one('sales.projection', string='Proyección', required=True, ondelete='cascade')

    period_month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ], string='Mes', required=True)

    quarter = fields.Selection([
        ('Q1', 'Q1 (Ene-Abr)'), ('Q2', 'Q2 (May-Ago)'), ('Q3', 'Q3 (Sep-Dic)'),
    ], string='Cuatrimestre', compute='_compute_quarter', store=True)

    team_unified_id = fields.Many2one('commission.team.unified', string='Equipo Unificado', required=True)
    projected_amount = fields.Monetary('Monto Proyectado', required=True, currency_field='currency_id')

    previous_amount = fields.Monetary(
        string='Total Proyección Anterior',
        compute='_compute_monthly_temporality',
        currency_field='currency_id',
        help='Monto total proyectado en la proyección anterior de referencia'
    )
    monthly_temporality = fields.Percentage(
        string='Temporalidad Mensual (%)',
        compute='_compute_monthly_temporality',
        store=True,
        digits=(16, 2),
        help='Porcentaje que esta línea representa sobre el total de la proyección anterior. Ej: 2.20 significa 2.20%.'
    )

    goal_amount = fields.Monetary('Objetivo (Meta)', compute='_compute_sales_tracking', currency_field='currency_id')
    actual_sales = fields.Monetary('Venta Real', compute='_compute_sales_tracking', currency_field='currency_id')
    difference = fields.Monetary('Diferencia', compute='_compute_sales_tracking', currency_field='currency_id')
    goal_percentage = fields.Float('% Objetivo', compute='_compute_sales_tracking', digits=(16, 2))
    projected_percentage = fields.Float('% al Estimado', compute='_compute_sales_tracking', digits=(16, 2))

    currency_id = fields.Many2one('res.currency', related='projection_id.currency_id', readonly=True)
    year = fields.Char('Año', related='projection_id.year', readonly=True, store=True)

    _sql_constraints = [
        ('projection_month_team_unique', 'unique(projection_id, period_month, team_unified_id)',
         'Ya existe una proyección para este mes y equipo en esta proyección.')
    ]

    @api.depends('period_month')
    def _compute_quarter(self):
        for line in self:
            month = int(line.period_month) if line.period_month else 0
            if 1 <= month <= 4:
                line.quarter = 'Q1'
            elif 5 <= month <= 8:
                line.quarter = 'Q2'
            elif 9 <= month <= 12:
                line.quarter = 'Q3'
            else:
                line.quarter = False

    @api.depends('period_month', 'year', 'team_unified_id', 'projected_amount')
    def _compute_sales_tracking(self):
        for line in self:
            if not (line.period_month and line.year and line.team_unified_id):
                line.goal_amount = line.actual_sales = line.difference = line.goal_percentage = line.projected_percentage = 0.0
                continue

            year, month = int(line.year), int(line.period_month)
            date_from = f'{year}-{month:02d}-01'
            date_to = f'{year}-{month:02d}-{monthrange(year, month)[1]}'

            goal = self.env['commission.goal'].search([
                ('team_unified_id', '=', line.team_unified_id.id),
                ('period_year', '=', line.year),
                ('period_month', '=', line.period_month),
                ('user_id', '=', False), ('user_unified_id', '=', False)
            ], limit=1)
            line.goal_amount = goal.goal_amount

            if line.team_unified_id.team_ids:
                orders = self.env['sale.order'].search([
                    ('payment_valid_date', '>=', date_from), ('payment_valid_date', '<=', date_to),
                    ('state', 'in', ['sale', 'done']),
                    ('team_id', 'in', line.team_unified_id.team_ids.ids)
                ])
                line.actual_sales = sum(orders.mapped('amount_total'))
            else:
                line.actual_sales = 0.0

            line.difference = line.actual_sales - line.projected_amount
            line.goal_percentage = (line.actual_sales / line.goal_amount) * 100 if line.goal_amount > 0 else 0.0
            line.projected_percentage = (line.actual_sales / line.projected_amount) * 100 if line.projected_amount > 0 else 0.0

    @api.depends('projection_id.previous_projection_id.total_projected', 'projected_amount')
    def _compute_monthly_temporality(self):
        """Calcula el porcentaje que representa la línea respecto al total de la proyección anterior."""
        for line in self:
            total_previous = line.projection_id.previous_projection_id.total_projected
            line.previous_amount = total_previous
            if total_previous > 0:
                line.monthly_temporality = (line.projected_amount / total_previous)
            else:
                line.monthly_temporality = 0.0


class QuarterlySalesReport(models.Model):
    _name = 'quarterly.sales.report'
    _description = 'Reporte de Ventas por Cuatrimestre'
    _rec_name = 'display_name'
    _order = 'year desc, period_month, team_unified_id'

    display_name = fields.Char(string='Nombre', compute='_compute_display_name', store=True)
    projection_line_id = fields.Many2one('sales.projection.line', string='Línea de Proyección', required=True, ondelete='cascade', index=True)
    projection_id = fields.Many2one('sales.projection', string='Proyección', related='projection_line_id.projection_id', store=True, readonly=True)
    year = fields.Char(string='Año', related='projection_line_id.year', store=True, readonly=True)
    quarter = fields.Selection(string='Cuatrimestre', related='projection_line_id.quarter', store=True, readonly=True)
    period_month = fields.Selection(string='Mes', related='projection_line_id.period_month', store=True, readonly=True)
    team_unified_id = fields.Many2one('commission.team.unified', string='Equipo de Venta', related='projection_line_id.team_unified_id', store=True, readonly=True)
    quarter_goal = fields.Monetary('Objetivo Cuatrimestre', compute='_compute_quarter_goal', store=True, currency_field='currency_id')
    projected_amount = fields.Monetary('Estimado', related='projection_line_id.projected_amount', store=True, readonly=True, currency_field='currency_id')
    actual_sales = fields.Monetary('Venta', compute='_compute_actual_sales', store=True, currency_field='currency_id')
    difference = fields.Monetary('Diferencia', compute='_compute_metrics', store=True, currency_field='currency_id')
    goal_percentage = fields.Float('% Objetivo', compute='_compute_metrics', store=True, digits=(16, 2))
    projected_percentage = fields.Float('% Estimado', compute='_compute_metrics', store=True, digits=(16, 2))
    currency_id = fields.Many2one('res.currency', string='Moneda', related='projection_id.currency_id', readonly=True)

    @api.depends('year', 'quarter', 'period_month', 'team_unified_id')
    def _compute_display_name(self):
        selection = self.env['sales.projection.line']._fields['period_month'].selection
        for record in self:
            month_name = dict(selection).get(record.period_month, '')
            team_name = record.team_unified_id.name if record.team_unified_id else ''
            record.display_name = f'{record.quarter} - {month_name} {record.year} - {team_name}'

    @api.depends('quarter', 'year', 'team_unified_id')
    def _compute_quarter_goal(self):
        for record in self:
            if record.quarter and record.year and record.team_unified_id:
                if record.quarter == 'Q1': months = ['1', '2', '3', '4']
                elif record.quarter == 'Q2': months = ['5', '6', '7', '8']
                else: months = ['9', '10', '11', '12']

                goals = self.env['commission.goal'].search([
                    ('team_unified_id', '=', record.team_unified_id.id),
                    ('period_year', '=', record.year), ('period_month', 'in', months),
                    ('user_id', '=', False), ('user_unified_id', '=', False)
                ])
                record.quarter_goal = sum(goals.mapped('goal_amount'))
            else:
                record.quarter_goal = 0.0

    @api.depends('period_month', 'year', 'team_unified_id')
    def _compute_actual_sales(self):
        for record in self:
            if record.period_month and record.year and record.team_unified_id:
                year, month = int(record.year), int(record.period_month)
                date_from = f'{year}-{month:02d}-01'
                date_to = f'{year}-{month:02d}-{monthrange(year, month)[1]}'

                orders = self.env['sale.order'].search([
                    ('payment_valid_date', '>=', date_from), ('payment_valid_date', '<=', date_to),
                    ('state', 'in', ['sale', 'done']),
                    ('team_id', 'in', record.team_unified_id.team_ids.ids)
                ])
                record.actual_sales = sum(orders.mapped('amount_total'))
            else:
                record.actual_sales = 0.0

    @api.depends('actual_sales', 'projected_amount', 'quarter_goal')
    def _compute_metrics(self):
        for record in self:
            record.difference = record.actual_sales - record.projected_amount
            record.goal_percentage = (record.actual_sales / record.quarter_goal) * 100 if record.quarter_goal > 0 else 0.0
            record.projected_percentage = (record.actual_sales / record.projected_amount) * 100 if record.projected_amount > 0 else 0.0

    @api.model
    def _generate_reports_for_active_projections(self):
        active_projections = self.env['sales.projection'].search([('state', '=', 'active')])
        for projection in active_projections:
            for line in projection.line_ids:
                if not self.search([('projection_line_id', '=', line.id)]):
                    self.create({'projection_line_id': line.id})
        return True