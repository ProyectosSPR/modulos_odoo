# -*- coding: utf-8 -*-
"""
Historial de ejecuciones automáticas de facturación Público en General.
"""

from odoo import models, fields, api


class BillingAutoExecution(models.Model):
    _name = 'billing.auto.execution'
    _description = 'Historial de Ejecuciones Automáticas'
    _order = 'execution_date desc'
    _rec_name = 'display_name'

    config_id = fields.Many2one(
        'billing.public.config',
        string='Configuración',
        required=True,
        ondelete='cascade'
    )

    execution_date = fields.Datetime(
        string='Fecha de Ejecución',
        default=fields.Datetime.now,
        readonly=True
    )

    execution_type = fields.Selection([
        ('invoice', 'Facturación'),
        ('reconciliation', 'Conciliación'),
    ], string='Tipo', required=True)

    manual = fields.Boolean(
        string='Ejecución Manual',
        default=False,
        help='Indica si fue ejecutado manualmente o por el cron'
    )

    state = fields.Selection([
        ('running', 'En Progreso'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], string='Estado', default='running')

    result_message = fields.Text(
        string='Resultado',
        readonly=True
    )

    # Estadísticas
    orders_found = fields.Integer(
        string='Órdenes Encontradas',
        default=0
    )

    orders_processed = fields.Integer(
        string='Órdenes Procesadas',
        default=0
    )

    # Referencias a resultados
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura Creada',
        readonly=True
    )

    public_invoice_id = fields.Many2one(
        'billing.public.invoice',
        string='Registro Factura Pública',
        readonly=True
    )

    company_id = fields.Many2one(
        related='config_id.company_id',
        string='Compañía',
        store=True
    )

    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        readonly=True
    )

    duration = fields.Float(
        string='Duración (seg)',
        compute='_compute_duration',
        store=True
    )

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True
    )

    @api.depends('execution_type', 'execution_date', 'state')
    def _compute_display_name(self):
        for record in self:
            type_label = dict(record._fields['execution_type'].selection).get(record.execution_type, '')
            date_str = record.execution_date.strftime('%Y-%m-%d %H:%M') if record.execution_date else ''
            record.display_name = f"{type_label} - {date_str}"

    @api.depends('execution_date', 'write_date', 'state')
    def _compute_duration(self):
        for record in self:
            if record.state in ('done', 'error') and record.execution_date and record.write_date:
                delta = record.write_date - record.execution_date
                record.duration = delta.total_seconds()
            else:
                record.duration = 0

    def action_view_invoice(self):
        """Abre la factura creada."""
        self.ensure_one()
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Factura',
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
            }

    def action_view_public_invoice(self):
        """Abre el registro de factura pública."""
        self.ensure_one()
        if self.public_invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Factura Público en General',
                'res_model': 'billing.public.invoice',
                'res_id': self.public_invoice_id.id,
                'view_mode': 'form',
            }
