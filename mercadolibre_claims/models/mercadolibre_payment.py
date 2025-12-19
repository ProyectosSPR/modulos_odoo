# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MercadolibrePayment(models.Model):
    _inherit = 'mercadolibre.payment'

    # === RELACION CON CLAIMS ===
    claim_ids = fields.One2many(
        'mercadolibre.claim',
        'ml_payment_id',
        string='Reclamos'
    )
    claim_count = fields.Integer(
        string='Num. Reclamos',
        compute='_compute_claim_count'
    )
    has_active_claim = fields.Boolean(
        string='Tiene Reclamo Activo',
        compute='_compute_claim_count',
        store=True
    )

    # === ESTADO DE MEDIACION ===
    mediation_status = fields.Selection([
        ('none', 'Sin Mediacion'),
        ('in_mediation', 'En Mediacion'),
        ('resolved_buyer', 'Resuelto - Comprador'),
        ('resolved_seller', 'Resuelto - Vendedor'),
        ('resolved_other', 'Resuelto - Otro'),
    ], string='Estado Mediacion', default='none', tracking=True)

    mediation_date = fields.Datetime(
        string='Fecha Entrada Mediacion',
        readonly=True
    )
    mediation_resolution_date = fields.Datetime(
        string='Fecha Resolucion Mediacion',
        readonly=True
    )

    # === ACCIONES EJECUTADAS ===
    mediation_action_taken = fields.Selection([
        ('none', 'Ninguna'),
        ('payment_cancelled', 'Pago Cancelado'),
        ('payment_created_cancelled', 'Pago Creado (No Confirmado)'),
        ('payment_reversed', 'Pago Revertido'),
        ('pending_review', 'Pendiente Revision'),
    ], string='Accion Mediacion', default='none', tracking=True)

    @api.depends('claim_ids', 'claim_ids.status')
    def _compute_claim_count(self):
        for record in self:
            record.claim_count = len(record.claim_ids)
            record.has_active_claim = any(c.status == 'opened' for c in record.claim_ids)

    @api.model
    def create_from_mp_data(self, data, account):
        """Sobrescribe para detectar mediaciones"""
        payment, is_new = super().create_from_mp_data(data, account)

        if not payment:
            return payment, is_new

        # Detectar si entro en mediacion
        current_status = data.get('status', '')

        if current_status == 'in_mediation':
            if payment.mediation_status == 'none':
                # Primera vez que entra en mediacion
                payment._process_mediation_entry()
            elif payment.mediation_status != 'in_mediation':
                # Re-entro en mediacion
                payment._process_mediation_entry()

        elif current_status == 'approved' and payment.mediation_status == 'in_mediation':
            # Salio de mediacion con aprobacion (a favor vendedor)
            payment._process_mediation_resolution('seller')

        elif current_status in ('refunded', 'charged_back') and payment.mediation_status == 'in_mediation':
            # Salio de mediacion con reembolso (a favor comprador)
            payment._process_mediation_resolution('buyer')

        elif current_status == 'cancelled' and payment.mediation_status == 'in_mediation':
            # Cancelado durante mediacion
            payment._process_mediation_resolution('other')

        return payment, is_new

    def _process_mediation_entry(self):
        """Procesa la entrada de un pago a mediacion"""
        self.ensure_one()

        _logger.info('Pago %s entro en mediacion', self.mp_payment_id)

        self.write({
            'mediation_status': 'in_mediation',
            'mediation_date': fields.Datetime.now(),
        })

        # Buscar configuracion de claims activa
        ClaimConfig = self.env['mercadolibre.claim.config']
        config = ClaimConfig.search([
            ('account_id', '=', self.account_id.id),
            ('state', '=', 'active'),
            ('auto_process_mediation', '=', True),
        ], limit=1)

        if config:
            config.process_payment_in_mediation(self)

    def _process_mediation_resolution(self, benefited):
        """Procesa la resolucion de una mediacion"""
        self.ensure_one()

        _logger.info('Pago %s resolucion mediacion: %s', self.mp_payment_id, benefited)

        status_map = {
            'seller': 'resolved_seller',
            'buyer': 'resolved_buyer',
            'other': 'resolved_other',
        }

        self.write({
            'mediation_status': status_map.get(benefited, 'resolved_other'),
            'mediation_resolution_date': fields.Datetime.now(),
        })

    def action_view_claims(self):
        """Abre la lista de claims asociados"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reclamos'),
            'res_model': 'mercadolibre.claim',
            'view_mode': 'tree,form',
            'domain': [('ml_payment_id', '=', self.id)],
            'context': {'default_ml_payment_id': self.id},
        }

    def action_search_claims(self):
        """Busca claims asociados a este pago en MercadoLibre"""
        self.ensure_one()

        ClaimModel = self.env['mercadolibre.claim']

        # Buscar por order_id
        if self.mp_order_id:
            claims = ClaimModel.search([
                ('ml_order_id', '=', self.mp_order_id),
                ('account_id', '=', self.account_id.id),
            ])

            if claims:
                for claim in claims:
                    if not claim.ml_payment_id:
                        claim.ml_payment_id = self.id

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': _('Se encontraron %d reclamo(s) asociados.') % len(claims),
                        'type': 'success',
                        'sticky': False,
                    }
                }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('No se encontraron reclamos asociados.'),
                'type': 'warning',
                'sticky': False,
            }
        }
