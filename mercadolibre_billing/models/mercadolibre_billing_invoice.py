# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadoliBillingInvoice(models.Model):
    _name = 'mercadolibre.billing.invoice'
    _description = 'Factura de MercadoLibre/MercadoPago'
    _order = 'legal_document_number desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Número de Factura',
        compute='_compute_name',
        store=True
    )

    # Relaciones
    period_id = fields.Many2one(
        'mercadolibre.billing.period',
        string='Periodo',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML/MP',
        related='period_id.account_id',
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='period_id.company_id',
        store=True,
        readonly=True
    )
    billing_group = fields.Selection(
        related='period_id.billing_group',
        store=True,
        readonly=True
    )

    # Información de la factura
    legal_document_number = fields.Char(
        string='Número de Factura Legal',
        required=True,
        index=True
    )
    ml_document_id = fields.Char(
        string='Document ID ML',
        index=True
    )
    legal_document_status = fields.Char(
        string='Estado del Documento'
    )

    # Detalles de la factura
    detail_ids = fields.One2many(
        'mercadolibre.billing.detail',
        'invoice_group_id',
        string='Detalles'
    )

    # Contadores
    detail_count = fields.Integer(
        string='Cantidad de Detalles',
        compute='_compute_counts',
        store=True
    )

    # Montos
    total_amount = fields.Monetary(
        string='Total',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )

    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('complete', 'Completo'),
        ('processing', 'Procesando'),
        ('done', 'Procesado')
    ], string='Estado', default='draft', tracking=True)

    # Factura de proveedor generada
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Factura de Proveedor',
        ondelete='restrict'
    )

    _sql_constraints = [
        ('legal_document_number_period_uniq',
         'unique(legal_document_number, period_id)',
         'Esta factura ya existe en el periodo.')
    ]

    @api.depends('legal_document_number')
    def _compute_name(self):
        for record in self:
            record.name = record.legal_document_number or 'Nueva Factura'

    @api.depends('detail_ids')
    def _compute_counts(self):
        for record in self:
            record.detail_count = len(record.detail_ids)

    @api.depends('detail_ids.detail_amount')
    def _compute_totals(self):
        for record in self:
            record.total_amount = sum(record.detail_ids.mapped('detail_amount'))

    def action_mark_complete(self):
        """Marca la factura como completa (todos los detalles descargados)"""
        self.write({'state': 'complete'})

    def action_view_details(self):
        """Ver detalles de la factura"""
        self.ensure_one()
        return {
            'name': _('Detalles de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.billing.detail',
            'view_mode': 'tree,form',
            'domain': [('invoice_group_id', '=', self.id)],
            'context': {'default_invoice_group_id': self.id}
        }
