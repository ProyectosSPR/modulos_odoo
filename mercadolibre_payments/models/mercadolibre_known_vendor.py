# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MercadolibreKnownVendor(models.Model):
    _name = 'mercadolibre.known.vendor'
    _description = 'Proveedores Conocidos para Pagos ML'
    _order = 'sequence, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo del proveedor (ej: Google, CFE, Telmex)'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor en Odoo',
        required=True,
        help='Contacto de proveedor en Odoo al que se asignaran los pagos'
    )

    keyword_ids = fields.One2many(
        'mercadolibre.known.vendor.keyword',
        'vendor_id',
        string='Palabras Clave',
        help='Palabras clave para detectar este proveedor en las descripciones de pago'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        default=lambda self: self.env.company
    )

    # Estadisticas
    payment_count = fields.Integer(
        string='Pagos Asignados',
        compute='_compute_payment_count'
    )
    last_payment_date = fields.Date(
        string='Ultimo Pago',
        compute='_compute_payment_count'
    )

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Ya existe un proveedor conocido con este nombre.')
    ]

    @api.depends('partner_id')
    def _compute_payment_count(self):
        Payment = self.env['mercadolibre.payment']
        for record in self:
            payments = Payment.search([
                ('matched_vendor_id', '=', record.id)
            ])
            record.payment_count = len(payments)
            if payments:
                record.last_payment_date = max(payments.mapped('date_created')).date() if payments.mapped('date_created') else False
            else:
                record.last_payment_date = False

    def action_view_payments(self):
        """Ver pagos asignados a este proveedor"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pagos de %s') % self.name,
            'res_model': 'mercadolibre.payment',
            'view_mode': 'tree,form',
            'domain': [('matched_vendor_id', '=', self.id)],
            'context': {'default_matched_vendor_id': self.id},
        }

    @api.model
    def find_vendor_by_description(self, description):
        """
        Busca un proveedor conocido basandose en la descripcion del pago.

        Args:
            description: Texto de descripcion del pago

        Returns:
            mercadolibre.known.vendor record o False
        """
        if not description:
            return False

        description_lower = description.lower().strip()

        # Buscar en todas las palabras clave activas
        keywords = self.env['mercadolibre.known.vendor.keyword'].search([
            ('vendor_id.active', '=', True)
        ], order='vendor_id')

        for keyword in keywords:
            kw = keyword.keyword.lower().strip()
            match = False

            if keyword.match_type == 'exact':
                match = description_lower == kw
            elif keyword.match_type == 'starts':
                match = description_lower.startswith(kw)
            else:  # contains (default)
                match = kw in description_lower

            if match:
                return keyword.vendor_id

        return False


class MercadolibreKnownVendorKeyword(models.Model):
    _name = 'mercadolibre.known.vendor.keyword'
    _description = 'Palabra Clave de Proveedor Conocido'
    _order = 'sequence, id'

    vendor_id = fields.Many2one(
        'mercadolibre.known.vendor',
        string='Proveedor',
        required=True,
        ondelete='cascade'
    )
    keyword = fields.Char(
        string='Palabra Clave',
        required=True,
        help='Texto a buscar en la descripcion del pago (ej: "google", "cfe")'
    )
    match_type = fields.Selection([
        ('contains', 'Contiene'),
        ('starts', 'Empieza con'),
        ('exact', 'Exacto'),
    ], string='Tipo de Busqueda', default='contains', required=True,
       help='Como se buscara esta palabra clave en la descripcion')

    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )

    # Relacionado para mostrar en vistas
    partner_id = fields.Many2one(
        related='vendor_id.partner_id',
        string='Proveedor Odoo',
        store=True
    )

    _sql_constraints = [
        ('keyword_vendor_uniq', 'unique(keyword, vendor_id)',
         'Esta palabra clave ya existe para este proveedor.')
    ]

    @api.constrains('keyword')
    def _check_keyword(self):
        for record in self:
            if not record.keyword or len(record.keyword.strip()) < 2:
                raise ValidationError(_('La palabra clave debe tener al menos 2 caracteres.'))
