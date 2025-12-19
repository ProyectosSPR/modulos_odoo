# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MercadolibreClaimActionLog(models.Model):
    _name = 'mercadolibre.claim.action.log'
    _description = 'Log de Acciones de Reclamo MercadoLibre'
    _order = 'date_created desc'

    claim_id = fields.Many2one(
        'mercadolibre.claim',
        string='Reclamo',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta',
        related='claim_id.account_id',
        store=True
    )

    # === ACCION ===
    action_name = fields.Char(
        string='Accion',
        readonly=True
    )
    action_label = fields.Char(
        string='Etiqueta Accion',
        compute='_compute_action_label'
    )

    # === QUIEN EJECUTO ===
    player_role = fields.Selection([
        ('complainant', 'Comprador'),
        ('respondent', 'Vendedor'),
        ('mediator', 'Mediador'),
        ('system', 'Sistema'),
    ], string='Ejecutado Por (Rol)', readonly=True)

    user_id = fields.Many2one(
        'res.users',
        string='Usuario Odoo',
        readonly=True,
        help='Usuario de Odoo que ejecuto la accion (si aplica)'
    )

    # === CONTEXTO ===
    claim_stage = fields.Selection([
        ('claim', 'Reclamo'),
        ('dispute', 'Mediacion'),
        ('recontact', 'Recontacto'),
    ], string='Etapa', readonly=True)

    claim_status = fields.Selection([
        ('opened', 'Abierto'),
        ('closed', 'Cerrado'),
    ], string='Estado', readonly=True)

    action_reason_id = fields.Char(
        string='Reason ID',
        readonly=True
    )

    # === DETALLES ===
    detail = fields.Text(
        string='Detalle',
        readonly=True
    )
    source = fields.Selection([
        ('ml_api', 'API MercadoLibre'),
        ('odoo_manual', 'Odoo Manual'),
        ('odoo_auto', 'Odoo Automatico'),
    ], string='Origen', readonly=True, default='odoo_manual')

    # === FECHAS ===
    date_created = fields.Datetime(
        string='Fecha',
        readonly=True,
        default=fields.Datetime.now
    )

    display_name = fields.Char(
        compute='_compute_display_name'
    )

    ACTION_LABELS = {
        'open_claim': 'Reclamo Abierto',
        'open_dispute': 'Disputa Abierta',
        'send_message_to_complainant': 'Mensaje a Comprador',
        'send_message_to_respondent': 'Mensaje a Vendedor',
        'send_message_to_mediator': 'Mensaje a Mediador',
        'refund': 'Reembolso Total',
        'partial_refund': 'Reembolso Parcial',
        'allow_return': 'Devolucion Permitida',
        'allow_return_label': 'Etiqueta Devolucion',
        'add_shipping_evidence': 'Evidencia de Envio',
        'send_potential_shipping': 'Promesa de Envio',
        'generate_return': 'Devolucion Generada',
        'return_review_ok': 'Revision OK',
        'return_review_fail': 'Revision Fallida',
        'close_claim': 'Reclamo Cerrado',
    }

    @api.depends('action_name')
    def _compute_action_label(self):
        for rec in self:
            rec.action_label = self.ACTION_LABELS.get(rec.action_name, rec.action_name or '')

    @api.depends('action_label', 'date_created')
    def _compute_display_name(self):
        for rec in self:
            date_str = rec.date_created.strftime('%d/%m %H:%M') if rec.date_created else ''
            rec.display_name = f'{rec.action_label} - {date_str}'

    @api.model
    def create_from_ml_data(self, data, claim):
        """Crea un log de accion desde datos de la API (actions-history)"""
        vals = {
            'claim_id': claim.id,
            'action_name': data.get('action_name', ''),
            'player_role': data.get('player_role', ''),
            'claim_stage': data.get('claim_stage', ''),
            'claim_status': data.get('claim_status', ''),
            'action_reason_id': data.get('action_reason_id', ''),
            'date_created': claim._parse_datetime(data.get('date_created')),
            'source': 'ml_api',
        }

        return self.create(vals)
