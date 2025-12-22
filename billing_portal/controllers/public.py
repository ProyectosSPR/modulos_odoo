# -*- coding: utf-8 -*-
"""
Controlador PÚBLICO del portal de facturación.
Solo permite BUSCAR órdenes sin login.
Para FACTURAR se requiere autenticación en Odoo.
"""

from odoo import http, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class BillingPortalPublic(http.Controller):
    """
    Rutas públicas - No requieren autenticación.
    Solo búsqueda de órdenes.
    """

    @http.route('/portal/billing', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def billing_search(self, **kwargs):
        """
        Página principal de búsqueda de órdenes.
        PÚBLICO - No requiere login.

        GET: Muestra formulario de búsqueda
        POST: Busca orden por client_order_ref o name
        """
        error = None
        order = None
        order_ref = kwargs.get('order_ref', '').strip()

        # Verificar si el usuario está logueado
        is_logged_in = request.env.user.id != request.env.ref('base.public_user').id

        if request.httprequest.method == 'POST' and order_ref:
            _logger.info("Búsqueda de orden: '%s'", order_ref)

            # Buscar por múltiples campos:
            # - client_order_ref: Referencia del cliente
            # - name: Nombre de la orden (ej: DML00123)
            # - ml_order_id: ID de orden de MercadoLibre
            # - ml_pack_id: ID de pack de MercadoLibre
            domain = [
                '|', '|', '|',
                ('client_order_ref', 'ilike', order_ref),
                ('name', 'ilike', order_ref),
                ('ml_order_id', '=', order_ref),
                ('ml_pack_id', '=', order_ref),
            ]

            order = request.env['sale.order'].sudo().search(domain, limit=1)

            if order:
                _logger.info("Orden encontrada: %s (ID: %d)", order.name, order.id)
            else:
                error = _('No se encontró ningún pedido con esa referencia: %s') % order_ref
                _logger.info("Orden NO encontrada para: '%s'", order_ref)

        return request.render('billing_portal.portal_search', {
            'order': order,
            'order_ref': order_ref,
            'error': error,
            'is_logged_in': is_logged_in,
            'page_title': _('Portal de Facturación'),
        })

    @http.route('/portal/billing/view/<int:order_id>', type='http', auth='public', website=True)
    def billing_view_order(self, order_id, **kwargs):
        """
        Ver detalles de una orden (público).
        Para facturar debe loguearse.
        """
        order = request.env['sale.order'].sudo().browse(order_id)

        if not order.exists():
            return request.render('billing_portal.portal_error', {
                'error_title': _('Orden no encontrada'),
                'error_message': _('La orden especificada no existe.')
            })

        # Verificar si usuario está logueado
        is_logged_in = request.env.user.id != request.env.ref('base.public_user').id

        # Verificar si es facturable
        is_billable = getattr(order, 'is_portal_billable', True)
        not_billable_reason = None

        if not is_billable:
            if order.invoice_status == 'invoiced':
                not_billable_reason = _('Esta orden ya está completamente facturada.')
            elif order.state not in ('sale', 'done'):
                not_billable_reason = _('La orden aún no está confirmada.')
            else:
                not_billable_reason = _('Esta orden no puede facturarse actualmente.')

        return request.render('billing_portal.portal_order_view', {
            'order': order,
            'is_logged_in': is_logged_in,
            'is_billable': is_billable,
            'not_billable_reason': not_billable_reason,
            'page_title': _('Orden %s') % order.name,
        })
