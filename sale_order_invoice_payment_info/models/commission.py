from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime
from calendar import monthrange
import logging

_logger = logging.getLogger(__name__)


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


class CommissionUserUnified(models.Model):
    _name = 'commission.user.unified'
    _description = 'Vendedores Unificados'
    _order = 'name'

    name = fields.Char(
        string='Nombre del Grupo de Vendedores',
        required=True,
        help='Nombre del grupo de vendedores (ej: Equipo Mercado Libre)'
    )
    user_ids = fields.Many2many(
        'res.users',
        'commission_user_unified_res_users_rel',
        'unified_id',
        'user_id',
        string='Vendedores',
        help='Vendedores que pertenecen a este grupo unificado'
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'El nombre del grupo de vendedores debe ser único.')
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
        help='Vendedor específico (dejar vacío para meta por grupo de vendedores, equipo o general)'
    )
    user_unified_id = fields.Many2one(
        'commission.user.unified',
        string='Grupo de Vendedores',
        help='Grupo de vendedores unificados (dejar vacío si es por vendedor individual, equipo o general)'
    )
    team_unified_id = fields.Many2one(
        'commission.team.unified',
        string='Equipo Unificado',
        help='Equipo específico (dejar vacío si es por vendedor o general)'
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

    @api.depends('period_month', 'period_year', 'user_id', 'user_unified_id', 'team_unified_id', 'goal_amount')
    def _compute_name(self):
        for goal in self:
            month_name = dict(self._fields['period_month'].selection).get(goal.period_month, '')
            if goal.user_id:
                target = goal.user_id.name
            elif goal.user_unified_id:
                target = goal.user_unified_id.name
            elif goal.team_unified_id:
                target = goal.team_unified_id.name
            else:
                target = 'General'
            goal.name = f'{month_name} {goal.period_year} - {target}: ${goal.goal_amount:,.2f}'


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
        help='Vendedor específico (dejar vacío para cálculo por grupo o equipo)'
    )
    user_unified_id = fields.Many2one(
        'commission.user.unified',
        string='Grupo de Vendedores',
        help='Grupo de vendedores unificados para calcular comisiones conjuntas'
    )
    team_unified_id = fields.Many2one(
        'commission.team.unified',
        string='Equipo Unificado',
        help='Equipo para calcular comisiones (se usa si no hay vendedor específico)'
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
        digits=(16, 2),
        help='Porcentaje de alcance de la meta (ej: 128.04 significa 128.04%)'
    )
    reward_percentage = fields.Float(
        string='% Recompensa',
        compute='_compute_commission',
        store=True,
        digits=(16, 2),
        help='Porcentaje de recompensa según reglas (ej: 100 significa 100%)'
    )
    commission_percentage = fields.Float(
        string='% Comisión del Equipo',
        compute='_compute_commission',
        store=True,
        digits=(16, 4),
        help='Porcentaje de comisión del equipo (ej: 0.5 significa 0.5%)'
    )
    commission_amount = fields.Monetary(
        string='Monto de Comisión',
        currency_field='currency_id',
        compute='_compute_commission',
        store=True
    )

    # Campos para mostrar porcentajes con formato
    goal_percentage_display = fields.Char(
        string='Alcance de Meta',
        compute='_compute_percentage_display',
        store=False
    )
    reward_percentage_display = fields.Char(
        string='Recompensa',
        compute='_compute_percentage_display',
        store=False
    )
    commission_percentage_display = fields.Char(
        string='Comisión Equipo',
        compute='_compute_percentage_display',
        store=False
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

    @api.depends('goal_percentage', 'reward_percentage', 'commission_percentage')
    def _compute_percentage_display(self):
        """
        Calcula los campos de visualización de porcentajes con formato legible
        """
        for calc in self:
            calc.goal_percentage_display = f'{calc.goal_percentage:.2f}%' if calc.goal_percentage else '0.00%'
            calc.reward_percentage_display = f'{calc.reward_percentage:.2f}%' if calc.reward_percentage else '0.00%'
            calc.commission_percentage_display = f'{calc.commission_percentage:.4f}%' if calc.commission_percentage else '0.0000%'

    @api.onchange('user_id')
    def _onchange_user_id(self):
        """
        Sugiere el equipo unificado basado en el vendedor (sin recalcular automáticamente)
        """
        if self.user_id and not self.team_unified_id:
            # Buscar el equipo del vendedor en sale.order
            order = self.env['sale.order'].search([
                ('user_id', '=', self.user_id.id)
            ], limit=1)
            if order and order.team_id:
                # Buscar el equipo unificado que contenga este team_id
                unified = self.env['commission.team.unified'].search([
                    ('team_ids', 'in', order.team_id.id)
                ], limit=1)
                if unified:
                    self.team_unified_id = unified

    def _update_goal_amount(self):
        """
        Busca y establece la meta correspondiente
        """
        if self.period_month and self.period_year:
            goal = None

            # 1. Buscar meta específica por vendedor
            if self.user_id:
                goal = self.env['commission.goal'].search([
                    ('period_month', '=', self.period_month),
                    ('period_year', '=', self.period_year),
                    ('user_id', '=', self.user_id.id)
                ], limit=1)

            # 2. Si no hay meta por vendedor, buscar por grupo de vendedores
            if not goal and self.user_unified_id:
                goal = self.env['commission.goal'].search([
                    ('period_month', '=', self.period_month),
                    ('period_year', '=', self.period_year),
                    ('user_unified_id', '=', self.user_unified_id.id),
                    ('user_id', '=', False)
                ], limit=1)

            # 3. Si no hay meta por grupo, buscar por equipo
            if not goal and self.team_unified_id:
                goal = self.env['commission.goal'].search([
                    ('period_month', '=', self.period_month),
                    ('period_year', '=', self.period_year),
                    ('team_unified_id', '=', self.team_unified_id.id),
                    ('user_id', '=', False),
                    ('user_unified_id', '=', False)
                ], limit=1)

            # 4. Si no hay meta por equipo, buscar meta general
            if not goal:
                goal = self.env['commission.goal'].search([
                    ('period_month', '=', self.period_month),
                    ('period_year', '=', self.period_year),
                    ('user_id', '=', False),
                    ('user_unified_id', '=', False),
                    ('team_unified_id', '=', False)
                ], limit=1)

            if goal:
                self.goal_amount = goal.goal_amount

    @api.depends('period_month', 'period_year', 'user_id', 'user_unified_id', 'team_unified_id',
                 'calculation_base', 'team_unified_id.team_ids', 'user_unified_id.user_ids')
    def _compute_sale_orders(self):
        for calc in self:
            if calc.period_month and calc.period_year:
                # Calcular el último día del mes correctamente
                year = int(calc.period_year)
                month = int(calc.period_month)
                last_day = monthrange(year, month)[1]

                date_from = f'{calc.period_year}-{calc.period_month.zfill(2)}-01'
                date_to = f'{calc.period_year}-{calc.period_month.zfill(2)}-{last_day}'

                # Construir dominio base - usar payment_valid_date que se calcula automáticamente
                # basándose en las fechas reales de pago de las facturas
                domain = [
                    ('payment_valid_date', '!=', False),  # Debe tener fecha de pago válida
                    ('payment_valid_date', '>=', date_from),
                    ('payment_valid_date', '<=', date_to),
                    ('state', 'in', ['sale', 'done']),
                    ('invoice_status', 'in', ['invoiced', 'upselling'])  # Debe estar facturado
                ]

                # Agregar filtro con prioridad: team_unified > user_unified > user_id
                # IMPORTANTE: Si hay equipo unificado o grupo de vendedores, esos tienen prioridad
                if calc.team_unified_id:
                    # Filtro por equipo unificado (PRIORIDAD 1)
                    if calc.team_unified_id.team_ids:
                        domain.append(('team_id', 'in', calc.team_unified_id.team_ids.ids))
                    else:
                        # Si el equipo unificado no tiene equipos asignados, no hay órdenes
                        domain.append(('id', '=', False))
                elif calc.user_unified_id:
                    # Filtro por grupo de vendedores unificados (PRIORIDAD 2)
                    if calc.user_unified_id.user_ids:
                        domain.append(('user_id', 'in', calc.user_unified_id.user_ids.ids))
                    else:
                        # Si el grupo no tiene vendedores, no hay órdenes
                        domain.append(('id', '=', False))
                elif calc.user_id:
                    # Filtro por vendedor individual (PRIORIDAD 3 - solo si no hay grupo ni equipo)
                    domain.append(('user_id', '=', calc.user_id.id))

                orders = self.env['sale.order'].search(domain)

                # Filtro adicional: EXCLUIR órdenes que ya tienen commission_paid = True
                # Solo incluir órdenes con facturas pagadas que AÚN NO tienen comisión pagada
                filtered_orders = orders.filtered(
                    lambda o: not o.commission_paid and any(
                        inv.payment_state in ['paid', 'in_payment', 'partial']
                        for inv in o.invoice_ids.filtered(lambda i: i.move_type == 'out_invoice')
                    )
                )
                calc.sale_order_ids = [(6, 0, filtered_orders.ids)]
                calc.sale_order_count = len(filtered_orders)
            else:
                calc.sale_order_ids = [(6, 0, [])]
                calc.sale_order_count = 0

    @api.depends('sale_order_ids', 'sale_order_ids.amount_total', 'sale_order_ids.amount_untaxed',
                 'goal_amount', 'team_unified_id', 'team_unified_id.commission_percentage', 'calculation_base')
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
        for calc in self:
            # Actualizar la meta
            calc._update_goal_amount()
            # Recalcular órdenes y comisiones
            calc._compute_sale_orders()
            calc._compute_commission()
        return True

    def action_confirm(self):
        """
        Confirma el cálculo de comisión y marca todas las órdenes asociadas como commission_paid
        """
        today = fields.Date.today()
        for calc in self:
            calc.state = 'confirmed'

            # Marcar todas las órdenes de venta asociadas como comisión pagada
            # IMPORTANTE: Obtener los IDs y buscar directamente en sale.order
            # para evitar problemas con campos computados
            if calc.sale_order_ids:
                order_ids = calc.sale_order_ids.ids
                _logger.info(f"Marcando commission_paid=True para {len(order_ids)} órdenes: {order_ids}")

                orders = self.env['sale.order'].browse(order_ids)
                orders.write({
                    'commission_paid': True,
                    'commission_paid_date': today
                })

                # Forzar commit para asegurar que se guarden los cambios
                self.env.cr.commit()
                _logger.info(f"Comisiones marcadas como pagadas exitosamente")
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
        Regresa a borrador y desmarca las órdenes como comisión pagada
        """
        for calc in self:
            calc.state = 'draft'

            # Desmarcar todas las órdenes de venta asociadas como comisión NO pagada
            # IMPORTANTE: Obtener los IDs y buscar directamente en sale.order
            # para evitar problemas con campos computados
            if calc.sale_order_ids:
                order_ids = calc.sale_order_ids.ids
                _logger.info(f"Desmarcando commission_paid=False para {len(order_ids)} órdenes: {order_ids}")

                orders = self.env['sale.order'].browse(order_ids)
                orders.write({
                    'commission_paid': False,
                    'commission_paid_date': False
                })

                # Forzar commit para asegurar que se guarden los cambios
                self.env.cr.commit()
                _logger.info(f"Comisiones desmarcadas exitosamente")
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

    @api.model_create_multi
    def create(self, vals_list):
        """
        Al crear, busca la meta y calcula automáticamente
        """
        records = super().create(vals_list)
        for record in records:
            if record.period_month and record.period_year:
                record._update_goal_amount()
        return records

    def write(self, vals):
        """
        Sobrescribe el método write sin recalcular automáticamente.
        El usuario debe usar el botón 'Recalcular' para actualizar los cálculos.
        """
        result = super().write(vals)
        return result
