# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Campos de MercadoLibre
    ml_order_id = fields.Char(
        string='Order ID (ML)',
        index=True
    )

    ml_pack_id = fields.Char(
        string='Pack ID (ML)',
        index=True
    )

    ml_receiver_id = fields.Char(
        string='Receiver ID (ML)',
        index=True
    )

    # Estado de entrega ML
    ml_shipment_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('shipped', 'Enviado'),
        ('delivered', 'Entregado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado Envío ML')

    # Estado de pago ML
    ml_payment_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('released', 'Liberado'),
    ], string='Estado Pago ML')

    # Solicitudes de facturación relacionadas
    billing_request_ids = fields.Many2many(
        'billing.request',
        'billing_request_sale_order_rel',
        'order_id',
        'request_id',
        string='Solicitudes de Facturación'
    )

    billing_request_count = fields.Integer(
        compute='_compute_billing_request_count',
        string='# Solicitudes'
    )

    # Indica si es facturable desde portal
    is_portal_billable = fields.Boolean(
        compute='_compute_is_portal_billable',
        string='Facturable desde Portal',
        store=True
    )

    def _compute_billing_request_count(self):
        for order in self:
            order.billing_request_count = len(order.billing_request_ids)

    @api.depends('state', 'invoice_status', 'ml_shipment_status')
    def _compute_is_portal_billable(self):
        """
        Una orden es facturable desde el portal si:
        - Estado de la orden es 'sale' o 'done'
        - No está completamente facturada
        - El envío está entregado (si tiene envío ML)
        """
        for order in self:
            is_billable = (
                order.state in ('sale', 'done') and
                order.invoice_status != 'invoiced'
            )

            # Si tiene estado de envío ML, debe estar entregado
            if order.ml_shipment_status:
                is_billable = is_billable and order.ml_shipment_status == 'delivered'

            order.is_portal_billable = is_billable

    def action_view_billing_requests(self):
        """Ver solicitudes de facturación de esta orden"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Solicitudes de Facturación',
            'res_model': 'billing.request',
            'view_mode': 'tree,form',
            'domain': [('order_ids', 'in', self.id)],
        }

    @api.model
    def find_order_by_ref_flexible(self, ref):
        """
        Búsqueda flexible de orden por referencia.
        Busca en múltiples campos sin filtros de facturabilidad.
        Usado por el portal de invitados.
        """
        if not ref:
            return self.browse()

        # Búsqueda flexible en múltiples campos
        order = self.search([
            '|', '|', '|', '|',
            ('client_order_ref', '=', ref),
            ('client_order_ref', 'ilike', ref),
            ('name', 'ilike', ref),
            ('ml_order_id', '=', ref),
            ('ml_pack_id', '=', ref),
        ], limit=1)

        return order

    @api.model
    def search_for_billing_portal(self, search_term, receiver_id=None, limit=50):
        """
        Busca órdenes para el portal de facturación.
        Busca en client_order_ref, name, ml_order_id, ml_pack_id
        Retorna TODAS las órdenes encontradas con su estado de facturabilidad
        """
        _logger.warning("=" * 60)
        _logger.warning("BILLING PORTAL - Búsqueda de órdenes")
        _logger.warning("Término de búsqueda: '%s'", search_term)
        _logger.warning("Receiver ID: %s", receiver_id)

        # Validar término de búsqueda mínimo
        if not search_term or len(search_term.strip()) < 2:
            _logger.warning("Término de búsqueda muy corto o vacío, retornando lista vacía")
            return []

        search_term = search_term.strip()

        # Buscar en múltiples campos
        search_domain = [
            '|', '|', '|', '|',
            ('client_order_ref', 'ilike', search_term),
            ('name', 'ilike', search_term),
            ('ml_order_id', 'ilike', search_term),
            ('ml_pack_id', 'ilike', search_term),
            ('partner_id.email', 'ilike', search_term),
        ]

        if receiver_id:
            search_domain = ['&', ('ml_receiver_id', '=', receiver_id)] + search_domain

        _logger.warning("Dominio de búsqueda: %s", search_domain)

        # Buscar todas las órdenes que coincidan (sin filtrar por facturabilidad)
        all_orders = self.search(search_domain, limit=limit, order='date_order desc')
        _logger.warning("Órdenes encontradas: %d", len(all_orders))

        result = []
        for order in all_orders:
            # Determinar si es facturable y por qué no
            is_billable, not_billable_reason = order._check_billing_eligibility()

            # Log detallado solo en modo debug para evitar saturar logs
            _logger.debug(
                "  -> Orden: %s | Ref: %s | Facturable: %s | Razón: %s",
                order.name,
                order.client_order_ref or 'N/A',
                is_billable,
                not_billable_reason or 'OK'
            )

            result.append({
                'id': order.id,
                'name': order.name,
                'client_order_ref': order.client_order_ref or '',
                'ml_order_id': order.ml_order_id or '',
                'amount_total': order.amount_total,
                'date_order': order.date_order.strftime('%Y-%m-%d') if order.date_order else '',
                'invoice_status': order.invoice_status,
                'ml_shipment_status': order.ml_shipment_status or '',
                'is_billable': is_billable,
                'not_billable_reason': not_billable_reason or '',
                'partner_name': order.partner_id.name if order.partner_id else '',
            })

        _logger.warning("Retornando %d órdenes", len(result))
        _logger.warning("=" * 60)
        return result

    def _check_billing_eligibility(self):
        """
        Verifica si una orden es elegible para facturación.
        Retorna: (is_billable: bool, reason: str or None)
        """
        self.ensure_one()

        # Verificar estado de la orden
        if self.state not in ('sale', 'done'):
            state_labels = dict(self._fields['state'].selection)
            return False, f"La orden está en estado '{state_labels.get(self.state, self.state)}'"

        # Verificar si ya está facturada
        if self.invoice_status == 'invoiced':
            return False, "La orden ya está completamente facturada"

        # Verificar estado de envío (OBLIGATORIO para ML)
        if self.ml_shipment_status and self.ml_shipment_status != 'delivered':
            shipment_labels = {
                'pending': 'pendiente',
                'shipped': 'en camino',
                'cancelled': 'cancelado',
            }
            status_text = shipment_labels.get(self.ml_shipment_status, self.ml_shipment_status)
            return False, f"El envío aún no ha sido entregado (estado: {status_text})"

        # Verificar si no tiene nada que facturar
        if self.invoice_status == 'no':
            return False, "No hay nada que facturar en esta orden"

        return True, None
