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

    temporality = fields.Float(
        string='Temporalidad (%)',
        compute='_compute_temporality',
        store=True,
        digits=(16, 2),
        help='Cambio porcentual respecto a la proyección anterior. '
             'Ej: +15% = aumentó 15%, -10% = disminuyó 10%, 0% = sin cambios'
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

    @api.depends('line_ids', 'line_ids.projected_amount')
    def _compute_total_projected(self):
        """Calcula el total proyectado de todas las líneas"""
        for projection in self:
            projection.total_projected = sum(projection.line_ids.mapped('projected_amount'))

    @api.depends('total_projected', 'previous_projection_id', 'previous_projection_id.total_projected')
    def _compute_temporality(self):
        """Calcula la temporalidad como cambio porcentual vs proyección anterior"""
        for projection in self:
            if projection.previous_projection_id and projection.previous_projection_id.total_projected > 0:
                # Calcular el cambio porcentual: ((Actual - Anterior) / Anterior) * 100
                change = projection.total_projected - projection.previous_projection_id.total_projected
                projection.temporality = (change / projection.previous_projection_id.total_projected) * 100
            else:
                projection.temporality = 0.0

    def action_activate(self):
        """Activa la proyección y genera los reportes automáticamente"""
        for projection in self:
            projection.state = 'active'
            # Generar reportes para cada línea de proyección
            projection._generate_quarterly_reports()
        return True

    def _generate_quarterly_reports(self):
        """Genera registros de reporte cuatrimestral para todas las líneas de esta proyección"""
        self.ensure_one()
        # Usar sudo() porque es una operación del sistema al activar la proyección
        QuarterlyReport = self.env['quarterly.sales.report'].sudo()

        for line in self.line_ids:
            # Verificar si ya existe un reporte para esta línea
            existing = QuarterlyReport.search([('projection_line_id', '=', line.id)])
            if not existing:
                # Crear el reporte usando ORM con sudo
                QuarterlyReport.create({'projection_line_id': line.id})
                _logger.info(f"Reporte creado para {line.team_unified_id.name} - {line.period_month}/{line.year}")
            else:
                _logger.info(f"Reporte ya existe para {line.team_unified_id.name} - {line.period_month}/{line.year}")

    def action_close(self):
        """Cierra la proyección"""
        for projection in self:
            projection.state = 'closed'
        return True

    def action_back_to_draft(self):
        """Regresa la proyección a borrador"""
        for projection in self:
            projection.state = 'draft'
        return True


class SalesProjectionLine(models.Model):
    _name = 'sales.projection.line'
    _description = 'Líneas de Proyección de Ventas Mensual'
    _order = 'projection_id, period_month, team_unified_id'

    projection_id = fields.Many2one(
        'sales.projection',
        string='Proyección',
        required=True,
        ondelete='cascade'
    )

    period_month = fields.Selection([
        ('1', 'Enero'),
        ('2', 'Febrero'),
        ('3', 'Marzo'),
        ('4', 'Abril'),
        ('5', 'Mayo'),
        ('6', 'Junio'),
        ('7', 'Julio'),
        ('8', 'Agosto'),
        ('9', 'Septiembre'),
        ('10', 'Octubre'),
        ('11', 'Noviembre'),
        ('12', 'Diciembre'),
    ], string='Mes', required=True)

    quarter = fields.Selection([
        ('Q1', 'Q1 (Ene-Abr)'),
        ('Q2', 'Q2 (May-Ago)'),
        ('Q3', 'Q3 (Sep-Dic)'),
    ], string='Cuatrimestre', compute='_compute_quarter', store=True)

    team_unified_id = fields.Many2one(
        'commission.team.unified',
        string='Equipo Unificado',
        required=True,
        help='Equipo de ventas unificado (Mercado Libre, Amazon, etc.)'
    )

    projected_amount = fields.Monetary(
        string='Monto Proyectado',
        required=True,
        currency_field='currency_id',
        help='Monto proyectado para este equipo en este mes'
    )

    previous_amount = fields.Monetary(
        string='Proyección Anterior (mismo mes)',
        compute='_compute_monthly_temporality',
        currency_field='currency_id',
        help='Monto proyectado para este mismo mes y equipo en la proyección anterior'
    )

    monthly_temporality = fields.Float(
        string='Temporalidad Mensual (%)',
        compute='_compute_monthly_temporality',
        store=True,
        digits=(16, 2),
        help='Cambio porcentual respecto al mismo mes de la proyección anterior. '
             'Ej: +20% = aumentó 20%, -15% = disminuyó 15%, 0% = sin cambios'
    )

    # Campos de seguimiento de ventas reales
    goal_amount = fields.Monetary(
        string='Objetivo (Meta)',
        compute='_compute_sales_tracking',
        currency_field='currency_id',
        help='Meta configurada para este mes y equipo'
    )

    actual_sales = fields.Monetary(
        string='Venta Real',
        compute='_compute_sales_tracking',
        currency_field='currency_id',
        help='Ventas reales del mes (órdenes con payment_valid_date en este mes)'
    )

    difference = fields.Monetary(
        string='Diferencia',
        compute='_compute_sales_tracking',
        currency_field='currency_id',
        help='Diferencia entre venta real y estimado (proyectado)'
    )

    goal_percentage = fields.Float(
        string='% Objetivo',
        compute='_compute_sales_tracking',
        digits=(16, 2),
        help='Porcentaje de venta real vs objetivo (meta)'
    )

    projected_percentage = fields.Float(
        string='% al Estimado',
        compute='_compute_sales_tracking',
        digits=(16, 2),
        help='Porcentaje de venta real vs estimado (proyección)'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='projection_id.currency_id',
        readonly=True
    )

    year = fields.Char(
        string='Año',
        related='projection_id.year',
        readonly=True,
        store=True
    )

    _sql_constraints = [
        ('projection_month_team_unique',
         'unique(projection_id, period_month, team_unified_id)',
         'Ya existe una proyección para este mes y equipo en esta proyección.')
    ]

    @api.depends('period_month')
    def _compute_quarter(self):
        """Calcula el cuatrimestre basado en el mes"""
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
        """Calcula las ventas reales, meta, diferencias y porcentajes del mes"""
        for line in self:
            if not line.period_month or not line.year or not line.team_unified_id:
                line.goal_amount = 0.0
                line.actual_sales = 0.0
                line.difference = 0.0
                line.goal_percentage = 0.0
                line.projected_percentage = 0.0
                continue

            # Calcular fechas del mes
            year = int(line.year)
            month = int(line.period_month)
            last_day = monthrange(year, month)[1]
            date_from = f'{line.year}-{line.period_month.zfill(2)}-01'
            date_to = f'{line.year}-{line.period_month.zfill(2)}-{last_day}'

            # 1. Buscar la meta configurada para este mes y equipo
            goal = self.env['commission.goal'].search([
                ('team_unified_id', '=', line.team_unified_id.id),
                ('period_year', '=', line.year),
                ('period_month', '=', line.period_month),
                ('user_id', '=', False),
                ('user_unified_id', '=', False)
            ], limit=1)
            line.goal_amount = goal.goal_amount if goal else 0.0

            # 2. Calcular ventas reales del mes usando ORM
            if line.team_unified_id.team_ids:
                domain = [
                    ('payment_valid_date', '>=', date_from),
                    ('payment_valid_date', '<=', date_to),
                    ('state', 'in', ['sale', 'done']),
                    ('invoice_status', 'in', ['invoiced', 'upselling']),
                    ('team_id', 'in', line.team_unified_id.team_ids.ids)
                ]
                orders = self.env['sale.order'].search(domain)
                line.actual_sales = sum(orders.mapped('amount_total'))
            else:
                line.actual_sales = 0.0

            # 3. Calcular diferencia
            line.difference = line.actual_sales - line.projected_amount

            # 4. Calcular % Objetivo (venta real vs meta)
            if line.goal_amount > 0:
                line.goal_percentage = (line.actual_sales / line.goal_amount) * 100
            else:
                line.goal_percentage = 0.0

            # 5. Calcular % al Estimado (venta real vs proyección)
            if line.projected_amount > 0:
                line.projected_percentage = (line.actual_sales / line.projected_amount) * 100
            else:
                line.projected_percentage = 0.0

    @api.depends('projection_id.previous_projection_id', 'period_month', 'team_unified_id', 'projected_amount')
    def _compute_monthly_temporality(self):
        """Calcula la temporalidad mensual comparando con el mismo mes de la proyección anterior"""
        for line in self:
            previous_projection = line.projection_id.previous_projection_id

            if previous_projection and line.period_month and line.team_unified_id:
                # Buscar la línea del mismo mes y equipo en la proyección anterior
                previous_line = self.search([
                    ('projection_id', '=', previous_projection.id),
                    ('period_month', '=', line.period_month),
                    ('team_unified_id', '=', line.team_unified_id.id)
                ], limit=1)

                if previous_line:
                    line.previous_amount = previous_line.projected_amount

                    # Calcular temporalidad como cambio porcentual: ((Actual - Anterior) / Anterior) * 100
                    if previous_line.projected_amount > 0:
                        change = line.projected_amount - previous_line.projected_amount
                        line.monthly_temporality = (change / previous_line.projected_amount) * 100
                    else:
                        # Si anterior era 0 y ahora hay proyección, es crecimiento infinito (mostramos 100%)
                        line.monthly_temporality = 100.0 if line.projected_amount > 0 else 0.0

                    _logger.info(f"Temporalidad mensual calculada para {line.team_unified_id.name} - "
                               f"{line.period_month}/{line.year}: {line.monthly_temporality:+.2f}% "
                               f"(Actual: {line.projected_amount}, Anterior: {line.previous_amount})")
                else:
                    line.previous_amount = 0.0
                    line.monthly_temporality = 0.0
                    _logger.info(f"No hay línea anterior para {line.team_unified_id.name} - {line.period_month}/{line.year}")
            else:
                line.previous_amount = 0.0
                line.monthly_temporality = 0.0


class QuarterlySalesReport(models.Model):
    _name = 'quarterly.sales.report'
    _description = 'Reporte de Ventas por Cuatrimestre'
    _rec_name = 'display_name'
    _order = 'year desc, period_month, team_unified_id'

    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=True
    )

    projection_line_id = fields.Many2one(
        'sales.projection.line',
        string='Línea de Proyección',
        required=True,
        ondelete='cascade',
        index=True
    )

    projection_id = fields.Many2one(
        'sales.projection',
        string='Proyección',
        related='projection_line_id.projection_id',
        store=True,
        readonly=True
    )

    year = fields.Char(
        string='Año',
        related='projection_line_id.year',
        store=True,
        readonly=True
    )

    quarter = fields.Selection([
        ('Q1', 'Q1 (Ene-Abr)'),
        ('Q2', 'Q2 (May-Ago)'),
        ('Q3', 'Q3 (Sep-Dic)'),
    ], string='Cuatrimestre', related='projection_line_id.quarter', store=True, readonly=True)

    period_month = fields.Selection(
        string='Mes', related='projection_line_id.period_month', store=True, readonly=True)

    team_unified_id = fields.Many2one(
        'commission.team.unified',
        string='Equipo de Venta',
        related='projection_line_id.team_unified_id',
        store=True,
        readonly=True
    )

    # Objetivo del cuatrimestre (suma de metas mensuales)
    quarter_goal = fields.Monetary(
        string='Objetivo Cuatrimestre',
        compute='_compute_quarter_goal',
        store=True,
        currency_field='currency_id',
        help='Suma de las metas mensuales del cuatrimestre para este equipo'
    )

    # Estimado (de la proyección)
    projected_amount = fields.Monetary(
        string='Estimado',
        related='projection_line_id.projected_amount',
        store=True,
        readonly=True,
        currency_field='currency_id',
        help='Monto proyectado para este mes y equipo'
    )

    # Venta real (calculado)
    actual_sales = fields.Monetary(
        string='Venta',
        compute='_compute_actual_sales',
        store=True,
        currency_field='currency_id',
        help='Ventas reales del periodo (órdenes pagadas)'
    )

    # Diferencia
    difference = fields.Monetary(
        string='Diferencia',
        compute='_compute_metrics',
        store=True,
        currency_field='currency_id',
        help='Diferencia entre venta real y estimado'
    )

    # Porcentaje vs objetivo
    goal_percentage = fields.Float(
        string='% Objetivo',
        compute='_compute_metrics',
        store=True,
        digits=(16, 2),
        help='Porcentaje de venta real vs objetivo del cuatrimestre'
    )

    # Porcentaje vs estimado
    projected_percentage = fields.Float(
        string='% Estimado',
        compute='_compute_metrics',
        store=True,
        digits=(16, 2),
        help='Porcentaje de venta real vs estimado'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='projection_id.currency_id',
        readonly=True
    )

    @api.depends('year', 'quarter', 'period_month', 'team_unified_id')
    def _compute_display_name(self):
        """Calcula el nombre de visualización"""
        for record in self:
            month_name = dict(self._fields['period_month'].selection).get(record.period_month, '')
            team_name = record.team_unified_id.name if record.team_unified_id else ''
            record.display_name = f'{record.quarter} - {month_name} {record.year} - {team_name}'

    @api.depends('quarter', 'year', 'team_unified_id')
    def _compute_quarter_goal(self):
        """Calcula el objetivo del cuatrimestre sumando las metas mensuales"""
        for record in self:
            if record.quarter and record.year and record.team_unified_id:
                # Determinar los meses del cuatrimestre
                if record.quarter == 'Q1':
                    months = ['1', '2', '3', '4']
                elif record.quarter == 'Q2':
                    months = ['5', '6', '7', '8']
                elif record.quarter == 'Q3':
                    months = ['9', '10', '11', '12']
                else:
                    months = []

                # Buscar las metas mensuales para este equipo y periodo usando ORM
                goals = self.env['commission.goal'].search([
                    ('team_unified_id', '=', record.team_unified_id.id),
                    ('period_year', '=', record.year),
                    ('period_month', 'in', months),
                    ('user_id', '=', False),
                    ('user_unified_id', '=', False)
                ])

                # Sumar las metas usando el ORM
                record.quarter_goal = sum(goals.mapped('goal_amount'))
            else:
                record.quarter_goal = 0.0

    @api.depends('period_month', 'year', 'team_unified_id')
    def _compute_actual_sales(self):
        """Calcula las ventas reales del periodo basado en payment_valid_date usando ORM"""
        for record in self:
            if record.period_month and record.year and record.team_unified_id:
                # Calcular el último día del mes
                year = int(record.year)
                month = int(record.period_month)
                last_day = monthrange(year, month)[1]

                date_from = f'{record.year}-{record.period_month.zfill(2)}-01'
                date_to = f'{record.year}-{record.period_month.zfill(2)}-{last_day}'

                # Buscar órdenes pagadas en el periodo usando solo ORM
                domain = [
                    ('payment_valid_date', '>=', date_from),
                    ('payment_valid_date', '<=', date_to),
                    ('state', 'in', ['sale', 'done']),
                    ('invoice_status', 'in', ['invoiced', 'upselling']),
                    ('team_id', 'in', record.team_unified_id.team_ids.ids)
                ]

                orders = self.env['sale.order'].search(domain)

                # Sumar el total usando ORM
                record.actual_sales = sum(orders.mapped('amount_total'))
            else:
                record.actual_sales = 0.0

    @api.depends('actual_sales', 'projected_amount', 'quarter_goal')
    def _compute_metrics(self):
        """Calcula diferencia y porcentajes"""
        for record in self:
            # Diferencia
            record.difference = record.actual_sales - record.projected_amount

            # % Objetivo
            if record.quarter_goal > 0:
                record.goal_percentage = (record.actual_sales / record.quarter_goal) * 100
            else:
                record.goal_percentage = 0.0

            # % Estimado
            if record.projected_amount > 0:
                record.projected_percentage = (record.actual_sales / record.projected_amount) * 100
            else:
                record.projected_percentage = 0.0

    @api.model
    def _generate_reports_for_active_projections(self):
        """
        Genera automáticamente registros de reporte para todas las líneas de proyecciones activas.
        Este método puede ser llamado manualmente o por un cron job.
        """
        # Buscar proyecciones activas usando ORM
        active_projections = self.env['sales.projection'].search([('state', '=', 'active')])

        for projection in active_projections:
            for line in projection.line_ids:
                # Verificar si ya existe un reporte para esta línea
                existing = self.search([('projection_line_id', '=', line.id)])
                if not existing:
                    # Crear el reporte usando ORM
                    self.create({'projection_line_id': line.id})
                    _logger.info(f"Reporte creado para {line.team_unified_id.name} - {line.period_month}/{line.year}")

        return True
