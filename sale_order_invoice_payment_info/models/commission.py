from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class CommissionTeamUnified(models.Model):
    _name = 'commission.team.unified'
    _description = 'Equipos de Ventas Unificados'
    _order = 'name'

    name = fields.Char(
        string='Nombre del Equipo Unificado',
        required=True,
        help='Nombre del equipo unificado (ej: Mercado Libre)'
    )
    team_ids = fields.Many2many(
        'crm.team',
        'commission_team_unified_crm_team_rel',
        'unified_id',
        'team_id',
        string='Equipos de Ventas',
        help='Equipos que pertenecen a este grupo unificado'
    )
    commission_percentage = fields.Float(
        string='Porcentaje de Comisión (%)',
        digits=(5, 2),
        required=True,
        default=0.0,
        help='Porcentaje de comisión para este equipo (ej: 0.5 para 0.5%)'
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'El nombre del equipo unificado debe ser único.')
    ]


class CommissionGoalRule(models.Model):
    _name = 'commission.goal.rule'
    _description = 'Reglas de Alcance de Meta vs Recompensa'
    _order = 'goal_percentage desc'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    goal_percentage = fields.Float(
        string='Alcance de Meta (%)',
        required=True,
        help='Porcentaje de alcance de la meta (ej: 100, 90, 80)'
    )
    reward_percentage = fields.Float(
        string='Porcentaje de Recompensa (%)',
        required=True,
        help='Porcentaje de recompensa que se obtiene al alcanzar este nivel'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    active = fields.Boolean(default=True)

    @api.depends('goal_percentage', 'reward_percentage')
    def _compute_name(self):
        for rule in self:
            rule.name = f'{rule.goal_percentage}% Meta → {rule.reward_percentage}% Recompensa'

    @api.constrains('goal_percentage', 'reward_percentage')
    def _check_percentages(self):
        for rule in self:
            if rule.goal_percentage < 0 or rule.goal_percentage > 200:
                raise ValidationError('El porcentaje de alcance de meta debe estar entre 0 y 200.')
            if rule.reward_percentage < 0 or rule.reward_percentage > 100:
                raise ValidationError('El porcentaje de recompensa debe estar entre 0 y 100.')


class CommissionGoal(models.Model):
    _name = 'commission.goal'
    _description = 'Metas de Ventas por Vendedor/Periodo'
    _order = 'period_year desc, period_month desc, user_id'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
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
    period_year = fields.Char(
        string='Año',
        required=True,
        default=lambda self: str(datetime.now().year)
    )
    user_id = fields.Many2one(
        'res.users',
        string='Vendedor',
        help='Vendedor específico (dejar vacío para meta general)'
    )
    goal_amount = fields.Monetary(
        string='Meta en Pesos',
        required=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    active = fields.Boolean(default=True)

    @api.depends('period_month', 'period_year', 'user_id', 'goal_amount')
    def _compute_name(self):
        for goal in self:
            month_name = dict(self._fields['period_month'].selection).get(goal.period_month, '')
            user_name = goal.user_id.name if goal.user_id else 'General'
            goal.name = f'{month_name} {goal.period_year} - {user_name}: ${goal.goal_amount:,.2f}'

    _sql_constraints = [
        ('unique_goal_period_user',
         'unique(period_month, period_year, user_id)',
         'Ya existe una meta para este vendedor en este periodo.')
    ]


class CommissionCalculation(models.Model):
    _name = 'commission.calculation'
    _description = 'Cálculo de Comisiones de Vendedores'
    _order = 'period_year desc, period_month desc, user_id'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
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
    ], string='Mes', required=True, default=lambda self: str(datetime.now().month))
    period_year = fields.Char(
        string='Año',
        required=True,
        default=lambda self: str(datetime.now().year)
    )
    user_id = fields.Many2one(
        'res.users',
        string='Vendedor',
        required=True
    )
    team_unified_id = fields.Many2one(
        'commission.team.unified',
        string='Equipo Unificado',
        compute='_compute_team_unified',
        store=True
    )

    # Configuración del cálculo
    calculation_base = fields.Selection([
        ('subtotal', 'Subtotal (sin impuestos)'),
        ('total', 'Total (con impuestos)')
    ], string='Base de Cálculo', default='total', required=True)

    # Montos
    total_sales = fields.Monetary(
        string='Total Vendido',
        currency_field='currency_id',
        compute='_compute_commission',
        store=True
    )
    goal_amount = fields.Monetary(
        string='Meta del Periodo',
        currency_field='currency_id'
    )
    goal_percentage = fields.Float(
        string='% Alcance de Meta',
        compute='_compute_commission',
        store=True,
        digits=(5, 2)
    )
    reward_percentage = fields.Float(
        string='% Recompensa',
        compute='_compute_commission',
        store=True,
        digits=(5, 2)
    )
    commission_percentage = fields.Float(
        string='% Comisión del Equipo',
        compute='_compute_commission',
        store=True,
        digits=(5, 2)
    )
    commission_amount = fields.Monetary(
        string='Monto de Comisión',
        currency_field='currency_id',
        compute='_compute_commission',
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Estado y fechas
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('paid', 'Pagado')
    ], string='Estado', default='draft', required=True)
    paid_date = fields.Date(string='Fecha de Pago')

    # Detalle de órdenes
    sale_order_ids = fields.Many2many(
        'sale.order',
        'commission_calculation_sale_order_rel',
        'commission_id',
        'order_id',
        string='Órdenes de Venta',
        compute='_compute_sale_orders',
        store=True
    )
    sale_order_count = fields.Integer(
        string='Número de Órdenes',
        compute='_compute_sale_orders',
        store=True
    )

    @api.depends('period_month', 'period_year', 'user_id', 'commission_amount')
    def _compute_name(self):
        for calc in self:
            month_name = dict(self._fields['period_month'].selection).get(calc.period_month, '')
            user_name = calc.user_id.name if calc.user_id else ''
            calc.name = f'{month_name} {calc.period_year} - {user_name}: ${calc.commission_amount:,.2f}'

    @api.depends('user_id')
    def _compute_team_unified(self):
        for calc in self:
            if calc.user_id:
                # Buscar el equipo del vendedor en sale.order
                order = self.env['sale.order'].search([
                    ('user_id', '=', calc.user_id.id)
                ], limit=1)
                if order and order.team_id:
                    # Buscar el equipo unificado que contenga este team_id
                    unified = self.env['commission.team.unified'].search([
                        ('team_ids', 'in', order.team_id.id)
                    ], limit=1)
                    calc.team_unified_id = unified.id if unified else False
                else:
                    calc.team_unified_id = False
            else:
                calc.team_unified_id = False

    @api.depends('period_month', 'period_year', 'user_id', 'calculation_base')
    def _compute_sale_orders(self):
        for calc in self:
            if calc.period_month and calc.period_year and calc.user_id:
                # Buscar órdenes del vendedor en el periodo con commission_paid = True
                orders = self.env['sale.order'].search([
                    ('user_id', '=', calc.user_id.id),
                    ('commission_paid', '=', True),
                    ('commission_paid_date', '>=', f'{calc.period_year}-{calc.period_month.zfill(2)}-01'),
                    ('commission_paid_date', '<=', f'{calc.period_year}-{calc.period_month.zfill(2)}-31'),
                    ('state', 'in', ['sale', 'done'])
                ])
                calc.sale_order_ids = [(6, 0, orders.ids)]
                calc.sale_order_count = len(orders)
            else:
                calc.sale_order_ids = [(6, 0, [])]
                calc.sale_order_count = 0

    @api.depends('sale_order_ids', 'goal_amount', 'team_unified_id', 'calculation_base')
    def _compute_commission(self):
        for calc in self:
            # Calcular total vendido según la base de cálculo
            total_sales = 0.0
            for order in calc.sale_order_ids:
                if calc.calculation_base == 'subtotal':
                    total_sales += order.amount_untaxed
                else:  # total
                    total_sales += order.amount_total

            calc.total_sales = total_sales

            # Calcular porcentaje de alcance de meta
            if calc.goal_amount > 0:
                calc.goal_percentage = (total_sales / calc.goal_amount) * 100
            else:
                calc.goal_percentage = 0.0

            # Buscar el porcentaje de recompensa según las reglas
            reward_pct = 0.0
            rules = self.env['commission.goal.rule'].search([
                ('active', '=', True)
            ], order='goal_percentage desc')
            for rule in rules:
                if calc.goal_percentage >= rule.goal_percentage:
                    reward_pct = rule.reward_percentage
                    break
            calc.reward_percentage = reward_pct

            # Obtener porcentaje de comisión del equipo unificado
            commission_pct = 0.0
            if calc.team_unified_id:
                commission_pct = calc.team_unified_id.commission_percentage
            calc.commission_percentage = commission_pct

            # Calcular comisión final
            if total_sales > 0 and commission_pct > 0 and reward_pct > 0:
                calc.commission_amount = total_sales * (commission_pct / 100) * (reward_pct / 100)
            else:
                calc.commission_amount = 0.0

    def action_calculate_commission(self):
        """
        Fuerza el recálculo de la comisión
        """
        self._compute_sale_orders()
        self._compute_commission()
        return True

    def action_confirm(self):
        """
        Confirma el cálculo de comisión
        """
        for calc in self:
            calc.state = 'confirmed'
        return True

    def action_mark_paid(self):
        """
        Marca la comisión como pagada
        """
        for calc in self:
            calc.write({
                'state': 'paid',
                'paid_date': fields.Date.today()
            })
        return True

    def action_back_to_draft(self):
        """
        Regresa a borrador
        """
        for calc in self:
            calc.state = 'draft'
        return True

    def action_view_sale_orders(self):
        """
        Abre las órdenes de venta relacionadas
        """
        self.ensure_one()
        return {
            'name': 'Órdenes de Venta',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.sale_order_ids.ids)],
        }
