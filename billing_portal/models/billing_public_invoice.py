# -*- coding: utf-8 -*-
"""
Modelo para tracking de facturas a Público en General.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BillingPublicInvoice(models.Model):
    _name = 'billing.public.invoice'
    _description = 'Factura Público en General'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nueva')
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        readonly=True,
        ondelete='set null',
        tracking=True
    )

    invoice_name = fields.Char(
        related='invoice_id.name',
        string='Número de Factura',
        store=True
    )

    invoice_state = fields.Selection(
        related='invoice_id.state',
        string='Estado Factura',
        store=True
    )

    date_from = fields.Date(
        string='Período Desde',
        required=True,
        tracking=True
    )

    date_to = fields.Date(
        string='Período Hasta',
        required=True,
        tracking=True
    )

    order_ids = fields.Many2many(
        'sale.order',
        'billing_public_invoice_order_rel',
        'public_invoice_id',
        'order_id',
        string='Órdenes Incluidas',
        readonly=True
    )

    order_count = fields.Integer(
        compute='_compute_counts',
        string='# Órdenes',
        store=True
    )

    total_amount = fields.Monetary(
        related='invoice_id.amount_total',
        string='Monto Total',
        store=True
    )

    currency_id = fields.Many2one(
        related='invoice_id.currency_id',
        string='Moneda',
        store=True
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('invoiced', 'Facturado'),
        ('partial', 'Parcialmente Conciliado'),
        ('reconciled', 'Conciliado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True)

    reconciliation_ids = fields.One2many(
        'billing.public.reconciliation',
        'public_invoice_id',
        string='Conciliaciones'
    )

    reconciliation_count = fields.Integer(
        compute='_compute_counts',
        string='# Conciliaciones',
        store=True
    )

    total_reconciled = fields.Monetary(
        compute='_compute_reconciled_amounts',
        string='Monto Conciliado',
        store=True,
        currency_field='currency_id'
    )

    total_pending = fields.Monetary(
        compute='_compute_reconciled_amounts',
        string='Monto Pendiente',
        store=True,
        currency_field='currency_id'
    )

    reconciliation_percent = fields.Float(
        compute='_compute_reconciled_amounts',
        string='% Conciliado',
        store=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company
    )

    user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True
    )

    notes = fields.Text(string='Notas')

    @api.depends('order_ids', 'reconciliation_ids')
    def _compute_counts(self):
        for record in self:
            record.order_count = len(record.order_ids)
            record.reconciliation_count = len(record.reconciliation_ids)

    @api.depends('reconciliation_ids.amount', 'total_amount')
    def _compute_reconciled_amounts(self):
        for record in self:
            total_reconciled = sum(record.reconciliation_ids.mapped('amount'))
            record.total_reconciled = total_reconciled
            record.total_pending = (record.total_amount or 0) - total_reconciled
            if record.total_amount:
                record.reconciliation_percent = (total_reconciled / record.total_amount) * 100
            else:
                record.reconciliation_percent = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nueva')) == _('Nueva'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'billing.public.invoice'
                ) or _('Nueva')
        return super().create(vals_list)

    def action_view_invoice(self):
        """Abre la factura asociada"""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('No hay factura asociada'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_view_orders(self):
        """Abre las órdenes incluidas"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Órdenes'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.order_ids.ids)],
        }

    def action_view_reconciliations(self):
        """Abre las conciliaciones"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Conciliaciones'),
            'res_model': 'billing.public.reconciliation',
            'view_mode': 'tree,form',
            'domain': [('public_invoice_id', '=', self.id)],
        }

    def action_open_reconciliation_wizard(self):
        """Abre el wizard de conciliación"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Conciliación Masiva'),
            'res_model': 'billing.public.reconciliation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_public_invoice_id': self.id,
            }
        }

    def action_cancel(self):
        """Cancela la factura pública"""
        for record in self:
            if record.reconciliation_ids:
                raise UserError(_('No se puede cancelar una factura con conciliaciones. Elimine las conciliaciones primero.'))
            record.state = 'cancelled'

    def _update_state(self):
        """Actualiza el estado basado en las conciliaciones"""
        for record in self:
            if record.state == 'cancelled':
                continue
            if not record.invoice_id:
                record.state = 'draft'
            elif record.reconciliation_percent >= 100:
                record.state = 'reconciled'
            elif record.reconciliation_percent > 0:
                record.state = 'partial'
            else:
                record.state = 'invoiced'
